"""Stage: edit. Time-warps the single capture into one screen track per video.

Usage: python tools/edit.py <slug> [--video ID]

For each video V in tutorial.yaml writes proyectos/<slug>/edit/V/{screen.mp4, timeline.json}
(timeline v2, odd/tasks/reglas-video.md L4; all times are absolute seconds in the final video).

Opening, requirements and closing are cards drawn by compose; screen.mp4 only covers
screen_start..screen_end. Each step is a piecewise warp of its capture span:
- typing runs at 13.5 chars/s, and texts over 30 chars go 3x after the first 15 (C6);
- blank frames (page loads: no ink but a spinner) are cut (C4); sparse screens are content;
- result/highlight events hold 1.5 s in TUT (TUT4), and results never less than 0.8 s (R2);
- idle spans speed up (never past 3x; RED starts faster, RED3), but the pointer target
  gets at least PRE_CLICK seconds before each click, PRE_TYPE before typing (C3);
- idle is squeezed further while the step outlasts its voice by more than 1.0 s (A2);
- when the voice is longer than the actions, the step's last frame is held;
- each voice is placed inside its step so the longest silence between voices is as short as
  possible (A2), keeping the LEAD when nothing needs to move.
Every action event is remapped through the warp so zooms, cursor and captions land exactly; a click
that changes the screen also gets `screen_at`, the output time of the new screen (compose cuts there).
"""
from __future__ import annotations

import argparse
import bisect

import numpy as np
from PIL import Image

from common import (PipelineError, ffmpeg, is_secret_ref, load_tutorial, main_guard, project_dir,
                    read_json, videos, write_json)

LEAD = 0.3         # voice starts this long after the step's first frame
TAIL = 0.4         # breathing room after the voice ends
GAP = 1.0          # A2: longest silence between voice clips
FOCUS = 0.25       # click into the field before typing
TYPE_CPS = 13.5    # C6: 12-15 chars/s
TYPE_FAST_AFTER = 15
TYPE_LONG = 30
PRE_CLICK = 0.6    # C3: target in frame >= 500 ms before the click
PRE_TYPE = 0.3     # C3 for typing: compose frames the field 0.3 s ahead, the focus click comes FOCUS later
CLICK_LAG = 0.15   # the recorder logs clicks/selects once they return: the page changed ~0.05-0.1 s earlier
IDLE_LONG = 1.0    # idle spans longer than this always run at max speed (waits, pauses)
MAX_SPEED = 3.0
FPS = 30
POINTER_EVENTS = ("click", "type", "select", "hover")
# C4: a load is a frame with (almost) no ink off the page colour; a spinner is < 0.1 %, while a sparse
# but real screen (a short list, a toast in a corner) keeps ~1 % of small text at 1/4 scale.
BLANK_SIZE = (480, 270)
BLANK_INK = 0.003
BLANK_DIST = 18
# A click changed the screen when this share of a 64x36 thumbnail moved by more than CHANGE_DIFF levels
# within CHANGE_WINDOW seconds (a modal, a new page); a checkbox or a typed letter does not.
CHANGE_SIZE = (64, 36)
CHANGE_DIFF, CHANGE_SHARE, CHANGE_WINDOW = 24, 0.3, 1.5
SCREEN_EVENTS = ("click", "select", "press", "goto")

PACES = {  # per video type (reglas-video.md Parte 3)
    "TUT": {"pref": 1.0, "hold": {"result": 1.5, "highlight": 1.5}},   # TUT4 pausado
    "RED": {"pref": 2.0, "hold": {"result": 0.8, "highlight": 0.8}},   # RED3 rápido
    "PRO": {"pref": 1.5, "hold": {"result": 0.8, "highlight": 0.8}},   # dinámico
    "NOV": {"pref": 1.2, "hold": {"result": 1.0, "highlight": 1.0}},   # directo
}
CARD_LIMITS = {  # (min, max) seconds; E1, TUT1, RED1, A2
    "opening": {"TUT": (2.0, 3.0), "RED": (1.5, 2.0), "PRO": (2.0, 3.0), "NOV": (2.0, 3.0)},
    "requirements": {"TUT": (1.5, 5.0)},
    "closing": {"TUT": (2.0, 2.5), "RED": (2.0, 2.5), "PRO": (2.0, 2.5), "NOV": (2.0, 2.5)},
}
CARD_LEAD = {"opening": 0.2, "requirements": 0.2, "closing": 0.1}
CARD_TAIL = 0.2


def pace(vtype: str) -> dict:
    return {"type": vtype, "max": MAX_SPEED, **PACES[vtype]}


def typing_seconds(chars: int) -> float:
    if chars <= TYPE_LONG:
        return chars / TYPE_CPS
    return TYPE_FAST_AFTER / TYPE_CPS + (chars - TYPE_FAST_AFTER) / (TYPE_CPS * 3)


# --- blank frames (C4) -------------------------------------------------------------------

def is_blank_image(img: Image.Image) -> bool:
    img.draft("RGB", BLANK_SIZE)
    small = img.convert("RGB").resize(BLANK_SIZE)
    px = np.asarray(small, dtype=np.int16).reshape(-1, 3)
    keys = (px // 16) @ np.array([256, 16, 1])
    dom = int(np.bincount(keys).argmax())
    ref = np.array([dom // 256, dom // 16 % 16, dom % 16], dtype=np.int16) * 16 + 8
    ink = (np.abs(px - ref).max(axis=1) > BLANK_DIST).mean()
    return ink < BLANK_INK


def blank_flags(frames: list[dict], frames_dir) -> list[bool]:
    flags = []
    for f in frames:
        with Image.open(frames_dir / f["file"]) as img:
            flags.append(is_blank_image(img))
    return flags


def _thumb(path) -> np.ndarray:
    with Image.open(path) as img:
        img.draft("L", (240, 135))
        return np.asarray(img.convert("L").resize(CHANGE_SIZE), dtype=np.int16)


def screen_change(frames: list[dict], flags: list[bool], frames_dir, c: float) -> float | None:
    """Capture time of the first frame after `c` that shows another screen, or None."""
    times = [f["t"] for f in frames]
    k = bisect.bisect_right(times, c) - 1
    while k >= 0 and flags[k]:
        k -= 1
    if k < 0:
        return None
    ref = _thumb(frames_dir / frames[k]["file"])
    for i in range(k + 1, len(frames)):
        if times[i] > c + CHANGE_WINDOW:
            break
        if not flags[i] and (np.abs(_thumb(frames_dir / frames[i]["file"]) - ref) > CHANGE_DIFF).mean() >= CHANGE_SHARE:
            return times[i]
    return None


def mark_screen_changes(actions: dict, frames: list[dict], flags: list[bool], frames_dir) -> int:
    """Adds `screen_c` (capture time of the new screen) to the events that changed it."""
    found = 0
    for step in actions["steps"]:
        for ev in step["events"]:
            if ev["type"] in SCREEN_EVENTS:
                lag = CLICK_LAG if ev["type"] in ("click", "select") else 0.0
                at = screen_change(frames, flags, frames_dir, ev["t"] - lag)
                if at is not None:
                    ev["screen_c"] = at
                    found += 1
    return found


def blank_spans(frames: list[dict], flags: list[bool]) -> list[tuple[float, float]]:
    """Capture intervals covered by runs of blank frames (each frame lasts until the next)."""
    spans, start = [], None
    for i, f in enumerate(frames):
        if flags[i] and start is None:
            start = f["t"]
        elif not flags[i] and start is not None:
            spans.append((start, f["t"]))
            start = None
    if start is not None:
        spans.append((start, frames[-1]["t"] + 0.1))
    return spans


# --- warp ----------------------------------------------------------------------------------

def warp(pieces: list[dict], c: float) -> float:
    """Output offset (from the step start) of capture time c. Freezes at c count as before c."""
    o = 0.0
    for p in pieces:
        if p["c0"] == p["c1"]:
            if p["c0"] <= c:
                o += p["d"]
                continue
            break
        if c >= p["c1"]:
            o += p["d"]
        elif c > p["c0"]:
            o += p["d"] * (c - p["c0"]) / (p["c1"] - p["c0"])
            break
        else:
            break
    return o


def _end_of(ev: dict, pc: dict) -> float:
    if ev["type"] == "type":
        return ev.get("t_end", ev["t"])
    if ev["type"] in pc["hold"]:
        return ev["t"] + pc["hold"][ev["type"]]
    return ev["t"]


def build_pieces(a: float, b: float, events: list[dict], blanks, pc: dict, speed: float) -> list[dict]:
    """Piecewise warp of capture span [a, b]: [{c0, c1, d, kind}] with kind
    type | hold | idle | cut | freeze (c0 == c1: show the frame at c0 for d seconds)."""
    clamp = lambda t: min(max(t, a), b)  # noqa: E731
    evs = sorted(({**e, "t": clamp(e["t"])} for e in events), key=lambda e: e["t"])
    fixed = []
    for i, ev in enumerate(evs):
        nxt = evs[i + 1]["t"] if i + 1 < len(evs) else b
        if ev["type"] == "type" and "t_end" in ev:
            fixed.append([ev["t"], clamp(ev["t_end"]), "type", FOCUS + typing_seconds(ev.get("chars", 0))])
        elif ev["type"] in pc["hold"]:
            hold = pc["hold"][ev["type"]]
            fixed.append([ev["t"], min(ev["t"] + hold, nxt, b), "hold", hold])
    cuts = [(max(c0, a), min(c1, b)) for c0, c1 in blanks if c1 > a and c0 < b]
    marks = sorted({e["t"] for e in evs} | {t for span in cuts for t in span})
    pieces: list[dict] = []

    def idle(x: float, y: float) -> None:
        bounds = [x] + [m for m in marks if x < m < y] + [y]
        for c0, c1 in zip(bounds, bounds[1:]):
            if c1 - c0 <= 1e-9:
                continue
            if any(s0 <= c0 and c1 <= s1 for s0, s1 in cuts):
                pieces.append({"c0": c0, "c1": c1, "d": 0.0, "kind": "cut"})
                continue
            rate = pc["max"] if c1 - c0 > IDLE_LONG else min(speed, pc["max"])
            pieces.append({"c0": c0, "c1": c1, "d": (c1 - c0) / rate, "kind": "idle"})

    cursor = a
    for c0, c1, kind, d in sorted(fixed, key=lambda f: f[0]):
        c0 = max(c0, cursor)
        c1 = max(c1, c0)
        idle(cursor, c0)
        if kind == "hold":
            played = c1 - c0
            if played > 0:
                pieces.append({"c0": c0, "c1": c1, "d": played, "kind": "hold"})
            if d - played > 1e-9:
                pieces.append({"c0": c1, "c1": c1, "d": d - played, "kind": "freeze"})
        else:
            pieces.append({"c0": c0, "c1": c1, "d": d, "kind": kind})
        cursor = c1
    idle(cursor, b)

    prev_end = a
    for ev in evs:
        if ev["type"] in POINTER_EVENTS:
            pre = PRE_TYPE if ev["type"] == "type" else PRE_CLICK
            deficit = pre - (warp(pieces, ev["t"]) - warp(pieces, prev_end))
            if deficit > 1e-9:
                at = next((i for i, p in enumerate(pieces) if p["c0"] >= ev["t"]), len(pieces))
                pieces.insert(at, {"c0": ev["t"], "c1": ev["t"], "d": deficit, "kind": "freeze"})
        prev_end = max(prev_end, clamp(_end_of(ev, pc)))
    return pieces


def plan_step(a: float, b: float, events: list[dict], blanks, voice: float, pc: dict) -> dict:
    """Pick the slowest idle speed that keeps the step within voice + GAP (A2), then pad."""
    speed = pc["pref"]
    while True:
        pieces = build_pieces(a, b, events, blanks, pc, speed)
        actions = sum(p["d"] for p in pieces)
        if voice <= 0 or actions <= voice + GAP or speed >= pc["max"]:
            break
        speed = min(round(speed + 0.1, 3), pc["max"])
    need = voice + LEAD + TAIL if voice > 0 else 0.0
    duration = max(actions, need)
    if duration - actions > 1e-9:
        pieces.append({"c0": b, "c1": b, "d": duration - actions, "kind": "freeze"})
    offset = LEAD + max(0.0, duration - voice - GAP) / 2 if voice > 0 else 0.0
    return {"pieces": pieces, "duration": duration, "voice_offset": offset, "speed": speed}


def place_voices(items: list[tuple[float, float, float, float]]) -> list[float]:
    """A2: voice starts for [(earliest, latest, wanted, voice length)] in order, with the longest silence
    between consecutive voices as short as possible (GAP when it fits), each start nearest to `wanted`."""
    def tops(g):
        out = []
        for i, (lo, hi, _, _) in enumerate(items):
            top = hi if i == 0 else min(hi, out[-1] + items[i - 1][3] + g)
            if top < lo - 1e-9:
                return None
            out.append(top)
        return out

    g = GAP
    if tops(g) is None:
        low, high = GAP, max(GAP, items[-1][1] - items[0][0])
        for _ in range(40):
            mid = (low + high) / 2
            low, high = (mid, high) if tops(mid) is None else (low, mid)
        g = high
    top = tops(g)
    starts = [0.0] * len(items)
    nxt = None
    for i in reversed(range(len(items))):
        lo, _, want, voice = items[i]
        floor = lo if nxt is None else max(lo, nxt - voice - g)
        starts[i] = min(max(want, floor), top[i])
        nxt = starts[i]
    return starts


def plan_card(name: str, vtype: str, voice: float) -> dict:
    lo, hi = CARD_LIMITS[name][vtype]
    lead = CARD_LEAD[name]
    need = voice + lead + CARD_TAIL
    duration = min(max(need, lo), hi)
    warning = None
    if need > hi + 1e-6:
        duration = need
        warning = (f"{name} dura {duration:.1f} s y el máximo para {vtype} es {hi:.1f} s: "
                   "acorta la narración")
    # Opening and requirements end close to the voice so the first step follows without a gap.
    start = lead if name == "closing" else max(lead, duration - CARD_TAIL - voice)
    return {"duration": duration, "voice_start": start, "warning": warning}


# --- timeline --------------------------------------------------------------------------------

def _chars(ev: dict, yaml_text) -> int:
    if "chars" in ev:
        return int(ev["chars"])
    if isinstance(yaml_text, str) and not yaml_text.startswith("env:"):
        return len(yaml_text)
    # Captures made before the recorder logged chars: ~0.19 s per keystroke.
    return max(1, round((ev.get("t_end", ev["t"]) - ev["t"] - 0.4) / 0.19))


def _capture_events(cap: dict, step: dict) -> list[dict]:
    texts = [next(iter(a.values())).get("text") for a in step.get("actions", [])
             if isinstance(a, dict) and "type" in a]
    events, typed, prev_end = [], 0, cap["t0"]
    for ev in cap["events"]:
        ev = dict(ev)
        if ev["type"] in ("click", "select"):
            # Logged after the action returned: frames from the last CLICK_LAG already show its effect.
            ev["t"] = max(ev["t"] - CLICK_LAG, prev_end)
        prev_end = max(prev_end, ev.get("t_end", ev["t"]))
        if ev["type"] == "type":
            ev["chars"] = _chars(ev, texts[typed] if typed < len(texts) else None)
            if typed < len(texts) and is_secret_ref(texts[typed]):
                ev["secret"] = True
            typed += 1
        events.append(ev)
    return events


def _r(x: float) -> float:
    return round(x, 3)


def plan_video(tut: dict, video: dict, actions: dict, blanks, durations: dict) -> dict:
    vtype = video["type"]
    pc = pace(vtype)
    captured = {s["id"]: s for s in actions["steps"]}
    warnings = []

    def card(name: str, start: float):
        spec = video.get(name)
        if not spec:
            return None
        voice = float(durations.get(name, 0.0))
        plan = plan_card(name, vtype, voice)
        if plan["warning"]:
            warnings.append(plan["warning"])
        return {"start": _r(start), "duration": _r(plan["duration"]), "text": spec.get("text", ""),
                "narration": (spec.get("narration") or "").strip(),
                "voice_start": _r(start + plan["voice_start"]), "voice_duration": _r(voice)}

    opening = card("opening", 0.0)
    t = opening["duration"]
    requirements = card("requirements", t)
    if requirements:
        t += requirements["duration"]
    screen_start = t
    steps = []
    for step in video["steps"]:
        cap = captured.get(step["id"])
        if cap is None:
            raise PipelineError(f"El paso '{step['id']}' no está en la captura. Repite capture.py.")
        voice = float(durations.get(step["id"], 0.0))
        events = _capture_events(cap, step)
        plan = plan_step(cap["t0"], cap["t1"], events, blanks, voice, pc)
        pieces = plan["pieces"]
        out_events = []
        for ev in sorted(events, key=lambda e: e["t"]):
            at = t + warp(pieces, min(max(ev["t"], cap["t0"]), cap["t1"]))
            if ev["type"] == "type":
                end = t + warp(pieces, min(ev.get("t_end", ev["t"]), cap["t1"]))
            elif ev["type"] in pc["hold"]:
                end = at + pc["hold"][ev["type"]]
            else:
                end = at
            item = {"type": ev["type"], "t": _r(at), "t_end": _r(end), "selector": ev.get("selector"),
                    "box": ev.get("box"), "point": ev.get("point"), "chars": ev.get("chars", 0),
                    "secret": bool(ev.get("secret"))}
            item.update({k: ev[k] for k in ("key", "dy") if k in ev})
            if "screen_c" in ev:
                item["screen_at"] = _r(max(at, t + warp(pieces, min(max(ev["screen_c"], cap["t0"]), cap["t1"]))))
            out_events.append(item)
        warped, o = [], t
        for p in pieces:
            warped.append({"kind": p["kind"], "c0": _r(p["c0"]), "c1": _r(p["c1"]),
                           "o0": _r(o), "o1": _r(o + p["d"])})
            o += p["d"]
        steps.append({
            "id": step["id"], "number": step["number"], "chapter": step.get("chapter"),
            "title": step.get("title"), "narration": step["narration"],
            "start": _r(t), "duration": _r(plan["duration"]),
            "voice_start": _r(t + plan["voice_offset"]) if voice > 0 else _r(t), "voice_duration": _r(voice),
            "speed": plan["speed"], "events": out_events, "warp": warped,
        })
        t += plan["duration"]
    screen_end = t
    closing = card("closing", t)
    total = t + closing["duration"]
    blocks = [("opening", opening), ("requirements", requirements)] + \
        [(s["id"], s) for s in steps] + [("closing", closing)]
    voiced = [(name, b) for name, b in blocks if b and b["voice_duration"] > 0]
    # Cards keep their voice; a step's voice may slide anywhere inside the step (A2).
    windows = [(b["voice_start"], b["voice_start"]) if "events" not in b else
               (b["start"], b["start"] + b["duration"] - b["voice_duration"]) for _, b in voiced]
    starts = place_voices([(lo, hi, b["voice_start"], b["voice_duration"])
                           for (lo, hi), (_, b) in zip(windows, voiced)]) if voiced else []
    for (_, b), start in zip(voiced, starts):
        b["voice_start"] = _r(start)
    for (name_a, a), (name_b, b) in zip(voiced, voiced[1:]):
        gap = b["voice_start"] - (a["voice_start"] + a["voice_duration"])
        if gap > GAP + 1e-3:
            warnings.append(f"{gap:.1f} s de silencio entre {name_a} y {name_b} (A2 pide como máximo "
                            f"{GAP:.1f} s): alarga la narración o quita acciones")
    source = list(actions.get("viewport", tut.get("viewport", [1920, 1080])))
    output = [1920, 1080] if video["format"] == "16:9" else [1080, 1920]
    return {
        "video": video["id"], "type": vtype, "format": video["format"], "source": source, "output": output,
        "total": _r(total), "product": tut.get("product", ""), "title": tut["title"],
        "opening": opening, "requirements": requirements, "closing": closing,
        "screen_start": _r(screen_start), "screen_end": _r(screen_end), "steps": steps,
        "warnings": warnings,
    }


# --- video -----------------------------------------------------------------------------------

def build_video(frames: list[dict], flags: list[bool], frames_dir, timeline: dict, out_path) -> None:
    """Concat-demuxer list: each frame shown until the next entry's output time."""
    times = [f["t"] for f in frames]
    good = [i for i, blank in enumerate(flags) if not blank] or list(range(len(frames)))
    good_times = [times[i] for i in good]

    def frame_at(c: float) -> str:
        k = bisect.bisect_right(good_times, c) - 1
        return frames[good[max(k, 0)]]["file"]

    base = timeline["screen_start"]
    entries = []  # (file, output time from screen_start)
    for step in timeline["steps"]:
        for p in step["warp"]:
            o0, o1, c0, c1 = p["o0"] - base, p["o1"] - base, p["c0"], p["c1"]
            if o1 - o0 <= 0:
                continue
            entries.append((frame_at(c0), o0))
            if c1 > c0:
                lo, hi = bisect.bisect_right(times, c0), bisect.bisect_left(times, c1)
                for i in range(lo, hi):
                    if not flags[i]:
                        entries.append((frames[i]["file"], o0 + (times[i] - c0) * (o1 - o0) / (c1 - c0)))
    end = timeline["screen_end"] - base
    lines = []
    for (name, t), nxt in zip(entries, [e[1] for e in entries[1:]] + [end]):
        if nxt - t <= 0:
            continue
        lines.append(f"file '{(frames_dir / name).as_posix()}'\nduration {nxt - t:.4f}")
    lines.append(f"file '{(frames_dir / entries[-1][0]).as_posix()}'")
    listing = out_path.with_suffix(".txt")
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(listing), "-vf", f"fps={FPS},format=yuv420p",
           "-t", f"{end:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
           "-movflags", "+faststart", str(out_path))
    listing.unlink()


def edit(slug: str, video: str | None = None) -> dict:
    tut = load_tutorial(slug)
    pdir = project_dir(slug)
    chosen = videos(tut, video)
    actions = read_json(pdir / "capture" / "actions.json")
    frames = read_json(pdir / "capture" / "frames.json")["frames"]
    frames_dir = pdir / "capture" / "frames"
    flags = blank_flags(frames, frames_dir)
    blanks = blank_spans(frames, flags)
    if blanks:
        print(f"[edit] corto {len(blanks)} cargas en blanco ({sum(b - a for a, b in blanks):.1f} s, C4)")
    mark_screen_changes(actions, frames, flags, frames_dir)
    result = {}
    for v in chosen:
        dur_file = pdir / "audio" / "voice" / v["id"] / "durations.json"
        if not dur_file.exists():
            raise PipelineError(f"Primero corre tts.py: el corte de '{v['id']}' se ajusta a la duración de la voz.")
        timeline = plan_video(tut, v, actions, blanks, read_json(dur_file))
        out_dir = pdir / "edit" / v["id"]
        out_dir.mkdir(parents=True, exist_ok=True)
        build_video(frames, flags, frames_dir, timeline, out_dir / "screen.mp4")
        write_json(out_dir / "timeline.json", timeline)
        result[v["id"]] = timeline
        for w in timeline["warnings"]:
            print(f"[edit] aviso ({v['id']}): {w}")
        print(f"[edit] {v['id']} ({v['type']} {v['format']}): {len(timeline['steps'])} pasos, "
              f"{timeline['total']:.1f} s en total")
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug")
    ap.add_argument("--video", help="solo este video (id de tutorial.yaml)")
    a = ap.parse_args()
    edit(a.slug, a.video)


if __name__ == "__main__":
    main_guard(main)
