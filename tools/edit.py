"""Stage: edit. Cuts the capture into per-step segments sized to the narration.

Usage: python tools/edit.py <slug>

For each variant (full = every step, short = steps with summary: true) writes
proyectos/<slug>/edit/<variant>/{screen.mp4, timeline.json}.

Each step keeps its real action span; long waits and slow typing are sped up (max 3x),
and when the voice is longer than the action the last frame is held. Every action
event is remapped to output time so zooms, cursor and captions land exactly.
"""
from __future__ import annotations

import argparse

from common import (PipelineError, ffmpeg, load_tutorial, main_guard, project_dir, read_json,
                    write_json)

LEAD = 0.35        # voice starts this long after the step's first frame
TAIL = 0.45        # breathing room after the voice ends
MAX_SPEED = 3.0
FPS = 30


def plan_segments(tut: dict, actions: dict, durations: dict, step_ids: list[str], intro: float) -> list[dict]:
    by_id = {s["id"]: s for s in actions["steps"]}
    tut_steps = {s["id"]: s for s in tut["steps"]}
    out_t = 0.0
    segments = []
    for sid in step_ids:
        cap = by_id.get(sid)
        if cap is None:
            raise PipelineError(f"El paso '{sid}' no está en la captura. Repetí capture.py.")
        a, b = max(cap["t0"] - 0.15, 0.0), cap["t1"]
        voice = durations.get(sid, 0.0)
        need = voice + LEAD + TAIL
        span = b - a
        speed = min(MAX_SPEED, span / (need + 1.0)) if span > need + 2.0 else 1.0
        length = max(span / speed, need)
        to_out = lambda t, a=a, speed=speed, o=out_t: intro + o + (t - a) / speed
        events = []
        for ev in cap["events"]:
            mapped = {**ev, "t": round(to_out(ev["t"]), 3)}
            if "t_end" in ev:
                mapped["t_end"] = round(to_out(ev["t_end"]), 3)
            events.append(mapped)
        segments.append({
            "id": sid,
            "title": tut_steps[sid].get("title"),
            "narration": (tut_steps[sid].get("narration") or "").strip(),
            "cap_a": a, "cap_b": b, "speed": round(speed, 3),
            "start": round(intro + out_t, 3), "duration": round(length, 3),
            "voice_start": round(intro + out_t + LEAD, 3), "voice_duration": round(voice, 3),
            "events": events,
        })
        out_t += length
    return segments


def build_video(frames: list[dict], frames_dir, segments: list[dict], intro: float, out_path) -> None:
    """Concat-demuxer list: each frame shown until the next frame's output time."""
    times = [f["t"] for f in frames]
    entries = []  # (file, out_time)
    for seg in segments:
        a, b, speed = seg["cap_a"], seg["cap_b"], seg["speed"]
        base = seg["start"] - intro
        prior = [i for i, t in enumerate(times) if t <= a]
        first = prior[-1] if prior else 0
        entries.append((frames[first]["file"], base))
        for i, t in enumerate(times):
            if a < t < b:
                entries.append((frames[i]["file"], base + (t - a) / speed))
    end = segments[-1]["start"] - intro + segments[-1]["duration"]
    lines = []
    for (name, t), nxt in zip(entries, [e[1] for e in entries[1:]] + [end]):
        if nxt - t <= 0:
            continue
        lines.append(f"file '{(frames_dir / name).as_posix()}'\nduration {nxt - t:.4f}")
    lines.append(f"file '{(frames_dir / entries[-1][0]).as_posix()}'")
    listing = out_path.with_suffix(".txt")
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(listing), "-vf", f"fps={FPS},format=yuv420p",
           "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-movflags", "+faststart", str(out_path))
    listing.unlink()


def variants(tut: dict) -> dict[str, list[str]]:
    all_ids = [s["id"] for s in tut["steps"]]
    short = [s["id"] for s in tut["steps"] if s.get("summary")]
    return {"full": all_ids, "short": short or all_ids}


def edit(slug: str) -> dict:
    tut = load_tutorial(slug)
    pdir = project_dir(slug)
    actions = read_json(pdir / "capture" / "actions.json")
    frames = read_json(pdir / "capture" / "frames.json")["frames"]
    dur_file = pdir / "audio" / "voice" / "durations.json"
    if not dur_file.exists():
        raise PipelineError("Primero corré tts.py: el corte se ajusta a la duración de la voz.")
    durations = read_json(dur_file)
    intro = float(tut.get("intro", {}).get("seconds", 3))
    outro = float(tut.get("outro", {}).get("seconds", 3))
    result = {}
    for name, ids in variants(tut).items():
        out_dir = pdir / "edit" / name
        out_dir.mkdir(parents=True, exist_ok=True)
        segments = plan_segments(tut, actions, durations, ids, intro)
        screen = segments[-1]["start"] + segments[-1]["duration"] - intro
        build_video(frames, pdir / "capture" / "frames", segments, intro, out_dir / "screen.mp4")
        timeline = {
            "variant": name, "source": actions["viewport"], "intro": intro, "outro": outro,
            "screen_duration": round(screen, 3), "total": round(intro + screen + outro, 3),
            "steps": segments,
        }
        write_json(out_dir / "timeline.json", timeline)
        result[name] = timeline
        print(f"[edit] {name}: {len(segments)} pasos, {timeline['total']:.1f} s en total")
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug")
    edit(ap.parse_args().slug)


if __name__ == "__main__":
    main_guard(main)
