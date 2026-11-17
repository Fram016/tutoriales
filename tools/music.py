"""Stage: music. One Lyria background track long enough for the longest variant.

Usage: python tools/music.py <slug> [--offline] [--force]

Writes proyectos/<slug>/audio/music.mp3 (Lyria) or music.wav (--offline placeholder pad).
Runs after edit.py, which knows the final length. Reuses an existing track unless --force,
because every Lyria call is billed.
"""
from __future__ import annotations

import argparse
import base64

from common import (PipelineError, env, ffmpeg, load_tutorial, main_guard, project_dir,
                    read_json, require_env)

DEFAULT_PROMPT = ("Modern corporate ambient background for a software tutorial, soft synth pads, "
                  "light percussion, positive and calm, steady energy")


def target_seconds(slug: str) -> float:
    edit_dir = project_dir(slug) / "edit"
    totals = [read_json(p)["total"] for p in edit_dir.glob("*/timeline.json")]
    if not totals:
        raise PipelineError("Primero corré edit.py: la música necesita saber la duración final.")
    return max(totals)


def music(slug: str, offline: bool = False, force: bool = False):
    tut = load_tutorial(slug)
    audio_dir = project_dir(slug) / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    existing = [p for p in (audio_dir / "music.mp3", audio_dir / "music.wav") if p.exists()]
    if existing and not force:
        print(f"[music] reutilizo {existing[0].name} (--force para regenerar)")
        return existing[0]
    seconds = int(target_seconds(slug)) + 5
    if offline:
        out = audio_dir / "music.wav"
        # Soft Am-F-C-G style pad as a stand-in so ducking and loudness can be verified.
        expr = ("0.08*sin(2*PI*220*t)+0.06*sin(2*PI*261.6*t)+0.05*sin(2*PI*329.6*t)"
                "+0.04*sin(2*PI*110*t)*(0.6+0.4*sin(2*PI*0.25*t))")
        ffmpeg("-f", "lavfi", "-i", f"aevalsrc={expr}:s=48000:c=stereo", "-t", str(seconds), str(out))
        print(f"[music] offline: pad de prueba de {seconds} s")
        return out
    from google import genai
    client = genai.Client(api_key=require_env("GEMINI_API_KEY"))
    cfg = tut.get("music", {})
    model = cfg.get("model", env("MUSIC_MODEL", "lyria-3.5"))
    prompt = (f"{cfg.get('prompt', DEFAULT_PROMPT)}. Instrumental only, no vocals, no lyrics. "
              f"Duration about {seconds} seconds, consistent energy, gentle ending.")
    print(f"[music] {model}: {prompt[:90]}...")
    interaction = client.interactions.create(model=model, input=prompt)
    if not interaction.output_audio or not interaction.output_audio.data:
        raise PipelineError("Lyria no devolvió audio")
    out = audio_dir / "music.mp3"
    out.write_bytes(base64.b64decode(interaction.output_audio.data))
    print(f"[music] ok: {out.name}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    music(a.slug, a.offline, a.force)


if __name__ == "__main__":
    main_guard(main)
