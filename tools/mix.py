"""Stage: mix. Places each voice clip, ducks the music under it, normalizes loudness.

Usage: python tools/mix.py <slug>

Writes proyectos/<slug>/audio/<variant>/mix.wav (48 kHz stereo), measured to
LOUDNESS_TARGET LUFS (default -14, the social-media standard) with a -1.5 dBTP ceiling.
"""
from __future__ import annotations

import argparse
import json
import re

from common import (PipelineError, env, ffmpeg, load_tutorial, main_guard, project_dir,
                    read_json, run, which)

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


def mix_variant(pdir, variant: str, music) -> dict:
    timeline = read_json(pdir / "edit" / variant / "timeline.json")
    total = timeline["total"]
    out_dir = pdir / "audio" / variant
    out_dir.mkdir(parents=True, exist_ok=True)
    clips = [s for s in timeline["steps"] if s["voice_duration"] > 0]
    inputs, chains = [], []
    for i, step in enumerate(clips):
        inputs += ["-i", str(pdir / "audio" / "voice" / f"{step['id']}.wav")]
        ms = int(step["voice_start"] * 1000)
        chains.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[v{i}]")
    n = len(clips)
    if n == 0:
        raise PipelineError("No hay narración para mezclar")
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
    # ourselves and re-correct once for the loudness the limiter shaved off.
    target = float(env("LOUDNESS_TARGET", "-14"))
    out = out_dir / "mix.wav"
    gain = target - float(measure(premix)["input_i"])
    for _ in range(3):
        ffmpeg("-i", str(premix), "-af",
               f"volume={gain:.2f}dB,alimiter=limit=0.79:attack=5:release=60:level=disabled,"
               "aresample=48000", "-ar", "48000", "-ac", "2", str(out))
        final = measure(out)
        miss = target - float(final["input_i"])
        if abs(miss) <= 0.3:
            break
        gain += miss
    premix.unlink()
    print(f"[mix] {variant}: {float(final['input_i']):.1f} LUFS, pico {float(final['input_tp']):.1f} dBTP"
          f"{'' if music else ' (sin música)'}")
    return final


def mix(slug: str) -> dict:
    load_tutorial(slug)
    pdir = project_dir(slug)
    music = find_music(pdir / "audio")
    return {v.name: mix_variant(pdir, v.name, music) for v in sorted((pdir / "edit").iterdir()) if v.is_dir()}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug")
    mix(ap.parse_args().slug)


if __name__ == "__main__":
    main_guard(main)
