"""Stage: voice. One Gemini TTS clip per narration of every video.

Usage: python tools/tts.py <slug> [--offline]

For each video V writes proyectos/<slug>/audio/voice/V/{opening,requirements?,<step>,closing}.wav
and V/durations.json {name: seconds}. The raw API audio is cached in audio/voice/_cache/ by
text+voice+style hash, so the same text in two videos is synthesized once and editing one
narration only re-synthesizes that clip. Every clip is trimmed of its leading/trailing silence
(keeping TRIM_PAD) into _cache/trim-v<TRIM_VERSION>/ before it is measured, so edit and lint work
with the real speech length; a new trim version re-derives from the raw cache, never re-billing.
--offline writes silent clips of estimated length (smoke tests without an API key; not trimmed).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import shutil
from pathlib import Path

from common import (env, ffmpeg, load_tutorial, main_guard, media_duration, project_dir,
                    require_env, videos, write_json)


TRIM_VERSION = 1
TRIM_DB = -45       # below this a sample is silence
TRIM_PAD = 0.06     # silence kept before and after the speech


def trim_silence(raw: Path, out: Path) -> Path:
    """Writes `raw` without its leading/trailing silence (TRIM_PAD kept). Falls back to the raw clip
    when nothing would remain (a silent clip)."""
    edge = f"silenceremove=start_periods=1:start_threshold={TRIM_DB}dB:start_silence={TRIM_PAD}:detection=peak"
    out.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg("-i", str(raw), "-af", f"{edge},areverse,{edge},areverse", "-c:a", "pcm_s16le", str(out))
    if media_duration(out) < 0.1:
        shutil.copyfile(raw, out)
    return out


def make_client():
    from google import genai
    return genai.Client(api_key=require_env("GEMINI_API_KEY"), http_options={"api_version": "v1beta"})


def estimate_seconds(text: str) -> float:
    # ~2.6 words/s is a brisk commercial Spanish read.
    return max(1.5, len(text.split()) / 2.6)


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
    client = None
    seconds = {}  # cache key -> clip length, shared by every video
    result = {}
    for video in videos(tut):
        vdir = voice_root / video["id"]
        vdir.mkdir(parents=True, exist_ok=True)
        durations = {}
        for name, text in clips(video):
            if not text:
                durations[name] = 0.0
                continue
            key = hashlib.sha256(f"{'offline' if offline else model}|{voice}|{style}|{text}".encode()).hexdigest()
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
            out = vdir / f"{name}.wav"
            if not out.exists() or out.read_bytes() != clip.read_bytes():
                shutil.copyfile(clip, out)
            if key not in seconds:
                seconds[key] = media_duration(clip)
            durations[name] = seconds[key]
        write_json(vdir / "durations.json", durations)
        result[video["id"]] = durations
        print(f"[tts] {video['id']}: {len(durations)} clips, {sum(durations.values()):.1f} s de voz"
              f"{' (offline: silencio)' if offline else ''}")
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug")
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    tts(a.slug, a.offline)


if __name__ == "__main__":
    main_guard(main)
