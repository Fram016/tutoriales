"""Mode B: prepares an existing video for replication (transcript + keyframes).

Usage: python tools/transcribe.py <video> --slug <slug> [--model small] [--language es]

Writes proyectos/<slug>/replica/:
  audio.wav        16 kHz mono extracted with FFmpeg
  transcript.json  faster-whisper (CPU) segments with start/end/text and word timestamps
  transcript.txt   one "[mm:ss] text" line per segment
  frames/*.jpg     keyframes on scene changes plus at least one every 5 s (max width 1280)
  frames.json      [{file, t}]
The agent then reads transcript + frames to write proyectos/<slug>/tutorial.yaml.
Model and compute type default to WHISPER_MODEL (small) and WHISPER_COMPUTE (int8).
"""
from __future__ import annotations

import argparse
import re
import time
import wave
from pathlib import Path

from common import (PROJECTS, ROOT, PipelineError, env, ffmpeg, main_guard, media_duration, run,
                    which, write_json)

SCENE_THRESHOLD = 0.3
MAX_GAP = 5.0
MAX_WIDTH = 1280


def stamp(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def extract_audio(video: Path, out: Path) -> None:
    ffmpeg("-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(out))


def load_samples(audio: Path):
    """16 kHz mono PCM -> float32 array. Bypasses faster-whisper's PyAV decoder, whose
    keyword arguments do not match every installed PyAV version."""
    import numpy as np
    with wave.open(str(audio), "rb") as wav:
        pcm = wav.readframes(wav.getnframes())
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0


def transcribe_audio(audio: Path, model_name: str, language: str) -> dict:
    from faster_whisper import WhisperModel
    compute = env("WHISPER_COMPUTE", "int8")
    print(f"[transcribe] whisper {model_name} ({compute}, CPU), idioma {language}...")
    model = WhisperModel(model_name, device="cpu", compute_type=compute)
    segments, info = model.transcribe(load_samples(audio), language=language, word_timestamps=True, vad_filter=True)
    out = []
    for seg in segments:
        out.append({
            "start": round(float(seg.start), 3), "end": round(float(seg.end), 3), "text": seg.text.strip(),
            "words": [{"start": round(float(w.start), 3), "end": round(float(w.end), 3), "word": w.word.strip(),
                       "probability": round(float(w.probability), 3)} for w in (seg.words or [])],
        })
    return {"model": model_name, "language": info.language, "duration": round(info.duration, 3),
            "segments": out}


def extract_frames(video: Path, frames_dir: Path) -> list[dict]:
    frames_dir.mkdir(parents=True, exist_ok=True)
    for old in frames_dir.glob("frame_*.jpg"):
        old.unlink()
    select = (f"select='isnan(prev_selected_t)+gt(scene,{SCENE_THRESHOLD})"
              f"+gte(t-prev_selected_t,{MAX_GAP})'")
    vf = f"{select},scale='min({MAX_WIDTH},iw)':-2,showinfo"
    res = run([which("ffmpeg"), "-hide_banner", "-y", "-i", str(video), "-vf", vf, "-fps_mode", "vfr",
               "-q:v", "3", str(frames_dir / "frame_%04d.jpg")], quiet=True)
    times = [float(t) for t in re.findall(r"pts_time:\s*([0-9.]+)", res.stderr)]
    files = sorted(frames_dir.glob("frame_*.jpg"))
    if not files:
        raise PipelineError("FFmpeg no extrajo ningún cuadro del video")
    return [{"file": f.name, "t": round(t, 3)} for f, t in zip(files, times)]


def transcribe(video: Path, slug: str, model_name: str | None = None, language: str = "es") -> dict:
    if not video.exists():
        raise PipelineError(f"No existe el video {video}")
    model_name = model_name or env("WHISPER_MODEL", "small")
    out_dir = PROJECTS / slug / "replica"
    out_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    duration = media_duration(video)
    print(f"[transcribe] {video.name}: {duration:.1f} s → {out_dir.relative_to(ROOT)}")
    audio = out_dir / "audio.wav"
    extract_audio(video, audio)
    transcript = transcribe_audio(audio, model_name, language)
    write_json(out_dir / "transcript.json", transcript)
    lines = [f"[{stamp(s['start'])}] {s['text']}" for s in transcript["segments"]]
    (out_dir / "transcript.txt").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    frames = extract_frames(video, out_dir / "frames")
    write_json(out_dir / "frames.json", frames)
    print(f"[transcribe] ok en {time.monotonic() - started:.1f} s: {duration:.1f} s de video, "
          f"{len(transcript['segments'])} segmentos, {len(frames)} cuadros clave")
    print(f"  leé {(out_dir / 'transcript.txt').relative_to(ROOT)} y {(out_dir / 'frames').relative_to(ROOT)}/ "
          f"para escribir proyectos/{slug}/tutorial.yaml")
    return {"duration": duration, "segments": len(transcript["segments"]), "frames": len(frames)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--model", help="tiny | base | small | medium (default: WHISPER_MODEL o small)")
    ap.add_argument("--language", default="es")
    a = ap.parse_args()
    transcribe(a.video.resolve(), a.slug, a.model, a.language)


if __name__ == "__main__":
    main_guard(main)
