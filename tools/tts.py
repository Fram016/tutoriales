"""Stage: voice. One Gemini TTS clip per narration of every video.

Usage: python tools/tts.py <slug> [--offline]

For each video V writes proyectos/<slug>/audio/voice/V/{opening,requirements?,<step>,closing}.wav
and V/durations.json {name: seconds}. Clips are cached in audio/voice/_cache/ by
text+voice+style hash, so the same text in two videos is synthesized once and editing one
narration only re-synthesizes that clip.
--offline writes silent clips of estimated length (smoke tests without an API key).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import shutil

from common import (env, ffmpeg, load_tutorial, main_guard, media_duration, project_dir,
                    require_env, videos, write_json)


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
    """(name, text) in video order: opening, requirements?, each step, closing."""
    out = [("opening", video["opening"].get("narration", ""))]
    if video.get("requirements"):
        out.append(("requirements", video["requirements"].get("narration", "")))
    out += [(step["id"], step["narration"]) for step in video["steps"]]
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
                        from google import genai
                        client = genai.Client(api_key=require_env("GEMINI_API_KEY"),
                                              http_options={"api_version": "v1beta"})
                    print(f"[tts] {video['id']}/{name}: {text[:60]}")
                    cached.write_bytes(synthesize(client, model, text, voice, style))
            out = vdir / f"{name}.wav"
            if not out.exists() or out.read_bytes() != cached.read_bytes():
                shutil.copyfile(cached, out)
            if key not in seconds:
                seconds[key] = media_duration(cached)
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
