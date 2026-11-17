"""Stage: voice. One Gemini TTS clip per step narration.

Usage: python tools/tts.py <slug> [--offline]

Writes proyectos/<slug>/audio/voice/<step>.wav and durations.json. Clips are cached by
text+voice+style hash, so editing one narration only re-synthesizes that step.
--offline writes silent clips of estimated length (smoke tests without an API key).
"""
from __future__ import annotations

import argparse
import base64
import hashlib

from common import (env, ffmpeg, load_tutorial, main_guard, media_duration, project_dir,
                    read_json, require_env, write_json)


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


def tts(slug: str, offline: bool = False) -> dict:
    tut = load_tutorial(slug)
    voice_dir = project_dir(slug) / "audio" / "voice"
    voice_dir.mkdir(parents=True, exist_ok=True)
    cfg = tut.get("voice", {})
    model = cfg.get("model", env("TTS_MODEL", "gemini-3.8-flash-tts"))
    voice = cfg.get("voice", env("TTS_VOICE", "Kore"))
    style = cfg.get("style", env("TTS_STYLE", "voz comercial cálida, español latinoamericano neutro"))
    cache_file = voice_dir / "cache.json"
    cache = read_json(cache_file) if cache_file.exists() else {}
    client = None
    durations = {}
    for step in tut["steps"]:
        text = (step.get("narration") or "").strip()
        out = voice_dir / f"{step['id']}.wav"
        if not text:
            durations[step["id"]] = 0.0
            continue
        key = hashlib.sha256(f"{'offline' if offline else model}|{voice}|{style}|{text}".encode()).hexdigest()
        if out.exists() and cache.get(step["id"]) == key:
            durations[step["id"]] = media_duration(out)
            continue
        if offline:
            ffmpeg("-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", f"{estimate_seconds(text):.2f}", str(out))
        else:
            if client is None:
                from google import genai
                client = genai.Client(api_key=require_env("GEMINI_API_KEY"),
                                      http_options={"api_version": "v1beta"})
            print(f"[tts] {step['id']}: {text[:60]}")
            out.write_bytes(synthesize(client, model, text, voice, style))
        cache[step["id"]] = key
        durations[step["id"]] = media_duration(out)
    write_json(cache_file, cache)
    write_json(voice_dir / "durations.json", durations)
    total = sum(durations.values())
    print(f"[tts] ok: {len(durations)} clips, {total:.1f} s de voz{' (offline: silencio)' if offline else ''}")
    return durations


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug")
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    tts(a.slug, a.offline)


if __name__ == "__main__":
    main_guard(main)
