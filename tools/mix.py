"""Stage: mix. Places each voice clip, ducks the music under it, normalizes loudness.

Usage: python tools/mix.py <slug> [--video ID]

For each video V writes proyectos/<slug>/audio/V/mix.wav (48 kHz stereo, 0..total), measured
to LOUDNESS_TARGET LUFS (default -14, the social-media standard) with the true peak strictly
below -1 dBTP (A1). Voice clips come from audio/voice/V/ at the times in edit/V/timeline.json.
"""
from __future__ import annotations

import argparse
import json
import re

from common import (PipelineError, env, ffmpeg, load_tutorial, main_guard, project_dir,
                    read_json, run, videos, which)

MAX_TRUE_PEAK = -1.2  # dBTP; margin under the A1 limit of -1 dBTP
DUCK = "sidechaincompress=threshold=0.025:ratio=10:attack=40:release=600:makeup=1"


def find_music(audio_dir):
    for name in ("music.mp3", "music.wav"):
        if (audio_dir / name).exists():
            return audio_dir / name
    return None


def measure(path) -> dict:
    target = env("LOUDNESS_TARGET", "-14")
    res = run([which("ffmpeg"), "-hide_banner", "-i", str(path), "-af",
               f"loudnorm=I={target}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"], quiet=True)
    block = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", res.stderr, re.S)
    if not block:
        raise PipelineError("No pude medir la sonoridad (loudnorm)")
    return json.loads(block.group(0))


def voice_clips(timeline: dict) -> list[tuple[str, float]]:
    """(clip name, absolute start) of every narrated block: cards and steps."""
    clips = []
    for name in ("opening", "requirements"):
        block = timeline.get(name)
        if block and block["voice_duration"] > 0:
            clips.append((name, block["voice_start"]))
    clips += [(s["id"], s["voice_start"]) for s in timeline["steps"] if s["voice_duration"] > 0]
    closing = timeline.get("closing")
    if closing and closing["voice_duration"] > 0:
        clips.append(("closing", closing["voice_start"]))
    return clips


def mix_video(pdir, video: str, music) -> dict:
    timeline = read_json(pdir / "edit" / video / "timeline.json")
    total = timeline["total"]
    out_dir = pdir / "audio" / video
    out_dir.mkdir(parents=True, exist_ok=True)
    clips = voice_clips(timeline)
    inputs, chains = [], []
    for i, (name, start) in enumerate(clips):
        inputs += ["-i", str(pdir / "audio" / "voice" / video / f"{name}.wav")]
        ms = int(start * 1000)
        chains.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[v{i}]")
    n = len(clips)
    if n == 0:
        raise PipelineError(f"No hay narración para mezclar en '{video}'")
    voice_mix = "".join(f"[v{i}]" for i in range(n)) + \
        f"amix=inputs={n}:normalize=0:dropout_transition=0,apad,atrim=0:{total}[voice]"
    graph = chains + [voice_mix]
    if music:
        level = env("MUSIC_LEVEL_DB", "-16")
        fade_out = max(total - 2.5, 0)
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        graph += [
            "[voice]asplit=2[vkey][vout]",
            f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{total},"
            f"volume={level}dB,afade=t=in:d=1.2,afade=t=out:st={fade_out}:d=2.5[bed]",
            f"[bed][vkey]{DUCK}[ducked]",
            "[vout][ducked]amix=inputs=2:normalize=0[pre]",
        ]
    else:
        graph += ["[voice]anull[pre]"]
    premix = out_dir / "premix.wav"
    ffmpeg(*inputs, "-filter_complex", ";".join(graph), "-map", "[pre]", "-t", f"{total}",
           "-ar", "48000", "-ac", "2", str(premix))
    # Measured gain + true-peak limiter. loudnorm's linear mode gives up on speech with
    # high peaks (falls back to dynamic mode and lands ~1.5 LU off), so we normalize
    # ourselves, re-correct for the loudness the limiter shaved off and lower the ceiling
    # until the true peak is strictly below -1 dBTP (A1).
    target = float(env("LOUDNESS_TARGET", "-14"))
    out = out_dir / "mix.wav"
    gain = target - float(measure(premix)["input_i"])
    ceiling = -2.0
    for _ in range(5):
        ffmpeg("-i", str(premix), "-af",
               f"volume={gain:.2f}dB,alimiter=limit={10 ** (ceiling / 20):.4f}:attack=5:release=60:"
               "level=disabled,aresample=48000", "-ar", "48000", "-ac", "2", str(out))
        final = measure(out)
        miss = target - float(final["input_i"])
        peak = float(final["input_tp"])
        if abs(miss) <= 0.3 and peak < MAX_TRUE_PEAK:
            break
        gain += miss
        if peak >= MAX_TRUE_PEAK:
            ceiling -= peak - MAX_TRUE_PEAK + 0.3
    premix.unlink()
    if float(final["input_tp"]) >= -1.0:
        raise PipelineError(f"{video}: el pico quedó en {float(final['input_tp']):.1f} dBTP; A1 pide menos de -1 dBTP")
    print(f"[mix] {video}: {float(final['input_i']):.1f} LUFS, pico {float(final['input_tp']):.1f} dBTP"
          f"{'' if music else ' (sin música)'}")
    return final


def mix(slug: str, video: str | None = None) -> dict:
    tut = load_tutorial(slug)
    pdir = project_dir(slug)
    result = {}
    for v in videos(tut, video):
        music = None if v["music"].get("none") else find_music(pdir / "audio" / v["id"])
        result[v["id"]] = mix_video(pdir, v["id"], music)
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug")
    ap.add_argument("--video", help="solo este video (id de tutorial.yaml)")
    a = ap.parse_args()
    mix(a.slug, a.video)


if __name__ == "__main__":
    main_guard(main)
