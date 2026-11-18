"""Stage: music. One Lyria background track per video, long enough for that video.

Usage: python tools/music.py <slug> [--video ID] [--offline] [--force]

Writes proyectos/<slug>/audio/<video>/music.mp3 (Lyria) or music.wav (--offline placeholder
pad). Runs after edit.py, which knows each video's length (total + 5 s is requested). The
style follows the video type (reglas-video.md, Tabla de decisión: TUT soft, RED rhythmic,
PRO marked, NOV soft) unless videos[].music.prompt or the global music.prompt says otherwise;
videos[].music.none: true leaves the video without music. Reuses an existing track unless
--force, because every Lyria call is billed. A track shorter than the video is extended
with crossfaded repeats, so the mix never restarts it audibly.
"""
from __future__ import annotations

import argparse
import base64

from common import (PipelineError, env, ffmpeg, load_tutorial, main_guard, media_duration,
                    project_dir, read_json, require_env, videos)

DEFAULT_PROMPTS = {
    "TUT": ("Soft corporate ambient background for a software tutorial, warm synth pads, "
            "very light percussion, calm and focused, steady low energy"),
    "RED": ("Rhythmic upbeat electronic pop for a short social media clip, punchy drums, "
            "bright plucks, energetic and catchy, steady tempo"),
    "PRO": ("Marked energetic corporate pop for a product promo, strong beat, confident synths, "
            "clear accents every bar, optimistic"),
    "NOV": ("Soft friendly background for a product update announcement, light pads and "
            "gentle plucks, positive and calm"),
}
CROSSFADE = 3.0
TAIL = 5


def target_seconds(pdir, video: str) -> float:
    path = pdir / "edit" / video / "timeline.json"
    if not path.exists():
        raise PipelineError(f"Primero corre edit.py: la música de '{video}' necesita saber la duración final.")
    return float(read_json(path)["total"])


def extend_track(path, need: float) -> float:
    """Repeat the track with a crossfade until it lasts at least `need` seconds."""
    length = media_duration(path)
    if length >= need:
        return length
    if length <= CROSSFADE * 2:
        raise PipelineError(f"{path.name} dura {length:.1f} s: es muy corta para extenderla")
    tmp = path.with_name(f"{path.stem}.extended{path.suffix}")
    while length < need:
        ffmpeg("-i", str(path), "-i", str(path), "-filter_complex",
               f"[0:a][1:a]acrossfade=d={CROSSFADE}:c1=tri:c2=tri", str(tmp))
        tmp.replace(path)
        length = media_duration(path)
    print(f"[music] {path.parent.name}: pista extendida a {length:.1f} s (cruce de {CROSSFADE:.0f} s)")
    return length


def music_video(tut: dict, pdir, video: dict, offline: bool, force: bool):
    vid = video["id"]
    cfg = video["music"]
    audio_dir = pdir / "audio" / vid
    audio_dir.mkdir(parents=True, exist_ok=True)
    if cfg.get("none"):
        print(f"[music] {vid}: sin música (music.none)")
        return None
    need = target_seconds(pdir, vid)
    seconds = int(need) + TAIL
    # music.wav is only ever the offline placeholder: an online run must replace it.
    out = audio_dir / ("music.wav" if offline else "music.mp3")
    if out.exists() and not force:
        print(f"[music] {vid}: reutilizo {out.name} (--force para regenerar)")
        extend_track(out, need)
        return out
    if offline:
        # Soft Am-F-C-G style pad as a stand-in so ducking and loudness can be verified.
        expr = ("0.08*sin(2*PI*220*t)+0.06*sin(2*PI*261.6*t)+0.05*sin(2*PI*329.6*t)"
                "+0.04*sin(2*PI*110*t)*(0.6+0.4*sin(2*PI*0.25*t))")
        ffmpeg("-f", "lavfi", "-i", f"aevalsrc={expr}:s=48000:c=stereo", "-t", str(seconds), str(out))
        print(f"[music] {vid}: offline, pad de prueba de {seconds} s")
        return out
    from google import genai
    # Lyria is only served by the v1beta Interactions API (v1 answers 404).
    client = genai.Client(api_key=require_env("GEMINI_API_KEY"), http_options={"api_version": "v1beta"})
    model = cfg.get("model", tut.get("music", {}).get("model", env("MUSIC_MODEL", "lyria-3.5")))
    style = cfg.get("prompt") or tut.get("music", {}).get("prompt") or DEFAULT_PROMPTS[video["type"]]
    prompt = (f"{style}. Instrumental only, no vocals, no lyrics. "
              f"Duration about {seconds} seconds, consistent energy, gentle ending.")
    print(f"[music] {vid} {model}: {prompt[:90]}...")
    interaction = client.interactions.create(model=model, input=prompt)
    if not interaction.output_audio or not interaction.output_audio.data:
        raise PipelineError("Lyria no devolvió audio")
    out.write_bytes(base64.b64decode(interaction.output_audio.data))
    (audio_dir / "music.wav").unlink(missing_ok=True)
    extend_track(out, need)
    print(f"[music] {vid}: ok, {out.name}")
    return out


def music(slug: str, offline: bool = False, force: bool = False, video: str | None = None) -> dict:
    tut = load_tutorial(slug)
    pdir = project_dir(slug)
    return {v["id"]: music_video(tut, pdir, v, offline, force) for v in videos(tut, video)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug")
    ap.add_argument("--video", help="solo este video (id de tutorial.yaml)")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    music(a.slug, a.offline, a.force, a.video)


if __name__ == "__main__":
    main_guard(main)
