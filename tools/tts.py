"""Stage: voice. One Gemini TTS clip per narration of every video.

Usage: python tools/tts.py <slug> [--offline]

For each video V writes proyectos/<slug>/audio/voice/V/{opening,requirements?,<step>,closing}.wav
and V/durations.json {name: seconds}. The raw API audio is cached in audio/voice/_cache/ by
text+voice+style hash, so the same text in two videos is synthesized once and editing one
narration only re-synthesizes that clip. Every clip is trimmed of its leading/trailing silence
(keeping TRIM_PAD) into _cache/trim-v<TRIM_VERSION>/ before it is measured, so edit and lint work
with the real speech length; a new trim version re-derives from the raw cache, never re-billing.
P2 (`pace: fast`): the trimmed clip is sped up by the video's tempo (ffmpeg atempo, no pitch change; default
common.FAST_TEMPO, x1.05, also the most P4 allows under fast) into _cache/tempo-<factor>/ before it is measured;
the raw API audio stays shared.
D3: the API reads common.spoken_text(narration, tutorial.yaml `pronunciation`) (RIDE -> "ri de"); captions keep the
written text. D5 (one voice tone): the clips of a video are one batch: every cache key carries the batch signature
(model + voice + style + tempo + pronunciation map + the video's ordered narrations), so changing one narration
re-synthesizes the whole video and clips of earlier runs are never mixed in. The batch is ONE request (one line per
clip, _cache/batch-<signature>.wav) cut at its pauses into the clips (split_batch: the pauses nearest to where each
clip should end by its characters); only when the cut is not trustworthy each clip is asked for alone (warned).
Every clip is then leveled to VOICE_LUFS (one gain per clip, ffmpeg volume) into _cache/level-v<LEVEL_VERSION>/
before it is measured.
--offline writes silent clips of estimated length (smoke tests without an API key; not trimmed).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import shutil
import time
from pathlib import Path

from common import (PipelineError, env, ffmpeg, load_tutorial, main_guard, measure_loudness, media_duration, project_dir,
                    require_env, run, spoken_text, videos, which, write_json)


TRIM_VERSION = 1
TRIM_DB = -45       # below this a sample is silence
TRIM_PAD = 0.06     # silence kept before and after the speech
LEVEL_VERSION = 1
BATCH_VERSION = 1   # D5: one request per video, cut at its pauses (a new version never reuses older clips)
VOICE_LUFS = -20.0  # D5: every clip of a video at the same loudness (mix normalizes the whole track after)
LEVEL_PEAK = -1.5   # dBTP a leveled clip never goes over


def trim_silence(raw: Path, out: Path) -> Path:
    """Writes `raw` without its leading/trailing silence (TRIM_PAD kept). Falls back to the raw clip
    when nothing would remain (a silent clip)."""
    edge = f"silenceremove=start_periods=1:start_threshold={TRIM_DB}dB:start_silence={TRIM_PAD}:detection=peak"
    out.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg("-i", str(raw), "-af", f"{edge},areverse,{edge},areverse", "-c:a", "pcm_s16le", str(out))
    if media_duration(out) < 0.1:
        shutil.copyfile(raw, out)
    return out


def with_tempo(src: Path, out: Path, tempo: float) -> Path:
    """P2: `src` played `tempo` times faster without changing the pitch (ffmpeg atempo)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg("-i", str(src), "-af", f"atempo={tempo:g}", "-c:a", "pcm_s16le", str(out))
    return out


def level_clip(src: Path, out: Path, target: float = VOICE_LUFS) -> Path:
    """D5: `src` with one gain so its integrated loudness is `target` (its true peak kept under LEVEL_PEAK). A
    silent clip is copied as it is."""
    out.parent.mkdir(parents=True, exist_ok=True)
    lufs, peak = measure_loudness(src)
    if not lufs > -70:
        shutil.copyfile(src, out)
        return out
    gain = min(target - lufs, LEVEL_PEAK - peak)
    ffmpeg("-i", str(src), "-af", f"volume={gain:.2f}dB", "-c:a", "pcm_s16le", str(out))
    return out


def batch_signature(model: str, voice: str, style: str, tempo: float, pronunciation: dict | None,
                    texts: list[str]) -> str:
    """D5: what makes a video's clips one batch; any change re-synthesizes all of them together."""
    data = [BATCH_VERSION, model, voice, style, f"{tempo:g}", sorted((pronunciation or {}).items()), texts]
    return hashlib.sha256(json.dumps(data, ensure_ascii=False).encode()).hexdigest()


SPLIT_DB, SPLIT_MIN = -40, 0.12   # D5: a pause between two clips of the batch (dB, seconds)
SPLIT_RATIO = 3.0                  # a cut clip lasts between 1/3 and 3 times its share of the batch by characters


def pauses(path: Path) -> list[tuple[float, float]]:
    """(start, end) of the silences inside an audio file (ffmpeg silencedetect)."""
    res = run([which("ffmpeg"), "-hide_banner", "-nostats", "-i", str(path), "-af",
               f"silencedetect=noise={SPLIT_DB}dB:d={SPLIT_MIN}", "-f", "null", "-"], quiet=True)
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", res.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", res.stderr)]
    return list(zip(starts, ends))


def split_points(found: list[tuple[float, float]], total: float, texts: list[str]) -> list[float] | None:
    """D5: where to cut a batch of `texts` (one line each) lasting `total` s: one pause per boundary, in order, each
    nearest to where its clip ends by characters (dynamic programming). None when there are not enough pauses or a
    cut clip would be far from its share."""
    k = len(texts) - 1
    if k <= 0:
        return []
    inner = [(a, b) for a, b in found if a > 0.05 and b < total - 0.05]
    if len(inner) < k:
        return None
    chars = [max(1, len(t)) for t in texts]
    want = [total * sum(chars[:i + 1]) / sum(chars) for i in range(k)]
    mids = [(a + b) / 2 for a, b in inner]
    inf = float("inf")
    cost = [[inf] * len(mids) for _ in range(k)]
    back = [[-1] * len(mids) for _ in range(k)]
    for j, m in enumerate(mids):
        cost[0][j] = abs(m - want[0])
    for i in range(1, k):
        best, arg = inf, -1
        for j in range(len(mids)):
            if j > 0 and cost[i - 1][j - 1] < best:
                best, arg = cost[i - 1][j - 1], j - 1
            if arg >= 0:
                cost[i][j] = best + abs(mids[j] - want[i])
                back[i][j] = arg
    j = min(range(len(mids)), key=lambda x: cost[k - 1][x])
    if cost[k - 1][j] == inf:
        return None
    picks = [j]
    for i in range(k - 1, 0, -1):
        j = back[i][j]
        picks.append(j)
    cuts = [mids[x] for x in reversed(picks)]
    edges = [0.0] + cuts + [total]
    for i, text in enumerate(texts):
        share = total * chars[i] / sum(chars)
        got = edges[i + 1] - edges[i]
        if not share / SPLIT_RATIO <= got <= share * SPLIT_RATIO:
            return None
    return cuts


def split_batch(raw: Path, texts: list[str], outs: list[Path]) -> bool:
    """D5: cuts the batch audio `raw` into one file per text (outs, in order). False when the cut is not trustworthy
    (nothing is written then)."""
    total = media_duration(raw)
    cuts = split_points(pauses(raw), total, texts)
    if cuts is None:
        return False
    edges = [0.0] + cuts + [total]
    for i, out in enumerate(outs):
        out.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg("-i", str(raw), "-ss", f"{edges[i]:.3f}", "-to", f"{edges[i + 1]:.3f}", "-c:a", "pcm_s16le", str(out))
    return True


def make_client():
    from google import genai
    return genai.Client(api_key=require_env("GEMINI_API_KEY"), http_options={"api_version": "v1beta"})


def estimate_seconds(text: str) -> float:
    # ~2.6 words/s is a brisk commercial Spanish read.
    return max(1.5, len(text.split()) / 2.6)


BATCH_RETRIES = (5.0, 15.0)   # waits before the 2nd and 3rd attempt of one batch request
BATCH_SPLIT = 3               # when a whole-video batch keeps failing: this many smaller batches

class BatchDropped(RuntimeError):
    """The server dropped a batch request on every attempt."""


def synthesize_retry(client, model: str, text: str, voice: str, style: str, sleep=time.sleep) -> bytes:
    """synthesize with retries on connection drops (the server may cut a long request). Other errors raise."""
    for attempt, wait in enumerate((0.0, *BATCH_RETRIES)):
        if wait:
            print(f"[tts] la API cortó la conexión; reintento en {wait:.0f} s")
            sleep(wait)
        try:
            return synthesize(client, model, text, voice, style)
        except Exception as exc:   # noqa: BLE001 - only connection drops are retried
            name = type(exc).__name__
            if "Connection" not in name and "Protocol" not in name and "disconnected" not in str(exc):
                raise
            if attempt == len(BATCH_RETRIES):
                raise BatchDropped(name) from exc
    raise RuntimeError("unreachable")


def batch_groups(voiced: list, split: bool = False) -> list[list]:
    """The whole video as one batch (D5); after repeated server drops, BATCH_SPLIT contiguous batches."""
    if not split or len(voiced) < 2 * BATCH_SPLIT:
        return [list(voiced)]
    size = -(-len(voiced) // BATCH_SPLIT)
    return [list(voiced[i:i + size]) for i in range(0, len(voiced), size)]


def synthesize(client, model: str, text: str, voice: str, style: str) -> bytes:
    interaction = client.interactions.create(
        model=model,
        input=[{
            "type": "user_input",
            "content": [{
                "type": "text",
                "text": text,
                "annotations": [{"type": "speech_metadata", "style": style}],
            }],
        }],
        response_format={"type": "audio"},
        generation_config={"speech_config": [{"voice": voice}]},
    )
    if not interaction.output_audio or not interaction.output_audio.data:
        raise RuntimeError("Gemini TTS no devolvió audio")
    return base64.b64decode(interaction.output_audio.data)


def clips(video: dict) -> list[tuple[str, str]]:
    """(name, text) in video order: opening, requirements?, each step, closing? (optional, N27)."""
    out = [("opening", video["opening"].get("narration", ""))]
    if video.get("requirements"):
        out.append(("requirements", video["requirements"].get("narration", "")))
    out += [(step["id"], step["narration"]) for step in video["steps"]]
    if video.get("closing"):
        out.append(("closing", video["closing"].get("narration", "")))
    return [(name, (text or "").strip()) for name, text in out]


def tts(slug: str, offline: bool = False) -> dict:
    tut = load_tutorial(slug)
    voice_root = project_dir(slug) / "audio" / "voice"
    cache_dir = voice_root / "_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cfg = tut.get("voice", {})
    model = cfg.get("model", env("TTS_MODEL", "gemini-3.8-flash-tts"))
    voice = cfg.get("voice", env("TTS_VOICE", "Kore"))
    style = cfg.get("style", env("TTS_STYLE", "voz comercial cálida, español latinoamericano neutro"))
    pronunciation = tut.get("pronunciation") or {}
    client = None
    seconds = {}  # cache key -> clip length
    result = {}
    for video in videos(tut):
        vdir = voice_root / video["id"]
        vdir.mkdir(parents=True, exist_ok=True)
        tempo = video["tempo"]
        durations = {}
        spoken = [(name, spoken_text(text, pronunciation)) for name, text in clips(video)]
        batch = batch_signature("offline" if offline else model, voice, style, tempo, pronunciation,
                                [text for _, text in spoken])
        keys = {name: hashlib.sha256(f"{batch}|{text}".encode()).hexdigest() for name, text in spoken if text}
        voiced = [(name, text) for name, text in spoken if text]
        missing = [(name, text) for name, text in voiced if not (cache_dir / f"{keys[name][:32]}.wav").exists()]
        if missing and not offline:
            # D5: the whole video in one request, cut at its pauses.
            if client is None:
                client = make_client()
            # A long batch can be dropped by the server ("Server disconnected"): retry it, then fall back to the
            # fewest smaller batches (same voice, style and tempo), never to one request per clip at once.
            for split in (False, True):
                groups = batch_groups(voiced, split)
                if split and len(groups) == 1:
                    raise PipelineError("La API de voz corta la conexión con la tanda completa y no se puede dividir")
                if split:
                    print(f"[tts] aviso (D5) {video['id']}: divido la lectura en {len(groups)} tandas "
                          "(misma voz, estilo y tempo)")
                try:
                    for k, group in enumerate(groups):
                        raw = cache_dir / (f"batch-{batch[:32]}.wav" if len(groups) == 1
                                           else f"batch-{batch[:32]}-{k + 1}of{len(groups)}.wav")
                        if not raw.exists():
                            print(f"[tts] {video['id']}: una tanda de {len(group)} frases (D5)")
                            text = "\n\n".join(t.replace("\n", " ") for _, t in group)
                            raw.write_bytes(synthesize_retry(client, model, text, voice, style))
                        if not split_batch(raw, [t for _, t in group],
                                           [cache_dir / f"{keys[n][:32]}.wav" for n, _ in group]):
                            print(f"[tts] aviso (D5) {video['id']}: no pude cortar la tanda en sus pausas; "
                                  "pido cada frase aparte")
                    break
                except BatchDropped:
                    if split:
                        raise PipelineError("La API de voz sigue cortando la conexión; reintenta más tarde")
        for name, text in spoken:
            if not text:
                durations[name] = 0.0
                continue
            key = keys[name]
            cached = cache_dir / f"{key[:32]}.wav"
            if not cached.exists():
                if offline:
                    ffmpeg("-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t",
                           f"{estimate_seconds(text):.2f}", str(cached))
                else:
                    if client is None:
                        client = make_client()
                    print(f"[tts] {video['id']}/{name}: {text[:60]}")
                    cached.write_bytes(synthesize(client, model, text, voice, style))
            clip = cached
            if not offline:
                clip = cache_dir / f"trim-v{TRIM_VERSION}" / cached.name
                if not clip.exists():
                    trim_silence(cached, clip)
            if tempo != 1.0:
                # The tempo is part of the derived clip's key: same text, other tempo = another file, same raw audio.
                sped = cache_dir / f"tempo-{tempo:g}" / f"{clip.parent.name}-{clip.name}"
                if not sped.exists():
                    with_tempo(clip, sped, tempo)
                clip = sped
            if not offline:
                leveled = cache_dir / f"level-v{LEVEL_VERSION}" / f"{clip.parent.name}-{clip.name}"
                if not leveled.exists():
                    level_clip(clip, leveled)
                clip = leveled
            out = vdir / f"{name}.wav"
            if not out.exists() or out.read_bytes() != clip.read_bytes():
                shutil.copyfile(clip, out)
            if (key, tempo) not in seconds:
                seconds[(key, tempo)] = media_duration(clip)
            durations[name] = seconds[(key, tempo)]
        write_json(vdir / "durations.json", durations)
        result[video["id"]] = durations
        print(f"[tts] {video['id']}: {len(durations)} clips, {sum(durations.values()):.1f} s de voz"
              f"{f' (tempo x{tempo:g})' if tempo != 1.0 else ''}{' (offline: silencio)' if offline else ''}")
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug")
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    tts(a.slug, a.offline)


if __name__ == "__main__":
    main_guard(main)
