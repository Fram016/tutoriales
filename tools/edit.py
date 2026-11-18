"""Stage: edit. Time-warps the single capture into one screen track per video.

Usage: python tools/edit.py <slug> [--video ID]

For each video V in tutorial.yaml writes proyectos/<slug>/edit/V/{screen.mp4, timeline.json}
(timeline v2, odd/tasks/reglas-video.md L4; all times are absolute seconds in the final video).

Opening, requirements and closing are cards drawn by compose; screen.mp4 only covers
screen_start..screen_end. Each step is a piecewise warp of its capture span:
- typing runs at 13.5 chars/s, and texts over 30 chars go 3x after the first 15 (C6);
- blank frames (page loads: no ink but a spinner, also under a header bar like the SRI shell) are cut (C4, N26);
  sparse screens are content;
- mixed frames (a screenshot caught mid-navigation: part old view, part new view, between two large changes
  within MIXED_WINDOW) are cut (N26);
- result/highlight events hold 1.5 s in TUT (TUT4), and results never less than 0.8 s (R2); every toast
  holds at 1.0x until compose's camera has landed on it (after a screen change, or after the pan from the
  previous target) plus R2's 0.8 s and a margin, in every video type (N6, S1b);
- a toast that follows a screen change is reached at once: the idle frames of the new screen before it are
  cut, so screen_at is the toast's time and compose's cut to the toast framing never shows an empty
  corner (C4, C10);
- C7: the frame before the first pointer action of every new screen is held until compose has room
  for the establishing shot and the zoom (compose.establish_room);
- idle spans speed up (never past 3x; RED starts faster, RED3), but the pointer target
  gets at least PRE_CLICK seconds before each click, PRE_TYPE before typing (C3);
- idle is squeezed further while the step outlasts its voice by more than 1.0 s (A2);
- when the voice is longer than the actions, the step's last frame is held;
- N1: a step's main action (its first click/select, or its single action) waits for the narration:
  when the instruction sentence would end more than SYNC_AFTER after it, the frame before the action
  is held so the voice (starting LEAD into the step) ends in time; the voice never slides past it, and
  the step records that end as `instruction_end` (absolute), the time qa checks;
- N14: when the sentence after the instruction describes its effect ("Haz clic en Consultar. Aparece la lista"),
  the click waits for the end of the instruction (no SYNC_AFTER) and the frame before the effect (the click's
  first visible change, `effect_c`) is held until the effect sentence starts: `effect_t` / `effect_start`;
- videos[].omit: typing/select on those selectors is cut from that video (the step and its number stay);
- each voice is placed inside its step so the longest silence between voices is as short as
  possible (A2), keeping the LEAD when nothing needs to move.
Every action event is remapped through the warp so zooms, cursor and captions land exactly; a click
that changes the screen also gets `screen_at`, the output time of the new screen (compose cuts there).

Surfaces (perseo-xml S5, an extension popup recorded next to the tab): their frames go through the same
warp into edit/V/surface-<name>.mp4, and timeline `surfaces.<name>.windows` says when each is open (output
times). Events inside a surface keep `surface` (boxes in surface CSS px); `open` is the click on the
toolbar icon, so it is a pointer action (C3 lead, N1 main action). The censor regions of a followed tab
(actions.json `censor_regions`, N25) go through the same warp into timeline `censor_regions` (output times).
"""
from __future__ import annotations

import argparse
import bisect
import re

import numpy as np
from PIL import Image

from common import (PipelineError, ffmpeg, is_secret_ref, load_tutorial, main_guard, project_dir,
                    read_json, videos, write_json)
from compose import HOLD, MOVE, R2_CLEAN, establish_room

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
POINTER_EVENTS = ("click", "type", "select", "hover", "open")
# C4: a load is a frame with (almost) no ink off the page colour; a spinner is < 0.1 %, while a sparse
# but real screen (a short list, a toast in a corner) keeps ~1 % of small text at 1/4 scale.
BLANK_SIZE = (480, 270)
BLANK_INK = 0.003
BLANK_DIST = 18
# N26: a header bar (a run of rows >= HEADER_INK ink, starting in the top HEADER_START and ending in the top
# HEADER_MAX of the frame) is not content: a white page under the SRI header is a load.
HEADER_INK, HEADER_START, HEADER_MAX = 0.3, 0.1, 0.25
# A click changed the screen when this share of a 64x36 thumbnail moved by more than CHANGE_DIFF levels
# within CHANGE_WINDOW seconds (a modal, a new page); a checkbox or a typed letter does not.
CHANGE_SIZE = (64, 36)
CHANGE_DIFF, CHANGE_SHARE, CHANGE_WINDOW = 24, 0.3, 1.5
SCREEN_EVENTS = ("click", "select", "press", "goto")
# N14: the visible effect of an action is its first change of >= EFFECT_SHARE of the thumbnail (a list appearing
# under the form), searched until the step's next event and at most EFFECT_WINDOW seconds.
EFFECT_SHARE, EFFECT_WINDOW = 0.05, 4.0
EFFECT_EPS = 0.001   # the hold before the effect shows the frame just before it
# N26: a frame between two changes of >= MIXED_SHARE less than MIXED_WINDOW apart, made of the two views around
# it, is a screenshot caught mid-navigation. Made of: what matches neither view is at most MIXED_NEITHER of the
# smaller change (a scroll shifts everything, so most of what changed matches neither).
MIXED_SHARE, MIXED_WINDOW, MIXED_NEITHER = 0.1, 0.3, 0.2
# Carried to the timeline as they are (target_ok / target_text: N13; censor: the N25 path of a followed tab).
EVENT_KEYS = ("key", "dy", "frame_box", "form_box", "surface", "tab", "target_ok", "target_text", "censor")
SYNC_AFTER = 0.3   # N1: the instruction ends at most this long after its action
ACTION_EVENTS = ("click", "select", "type", "hover", "press")   # a step's single action (N1)
OMIT_BEFORE = 0.5  # omit: the pointer reaching an omitted field is cut too
R2_MARGIN = 0.1    # N6: the toast hold covers R2_CLEAN plus this (frame rounding)
# N1: the sentence that asks for the action. Imperatives of the tutorials ("Haz clic", "Toca", ...);
# qa uses the same pattern.
INSTRUCTION = re.compile(r"\b(haz|hacer|clic|click|toca|tocar|pulsa|presiona|selecciona|elige|escoge|abre|"
                         r"guarda|ingresa|entra|escribe|completa|marca|busca|llena|agrega|añade|pega|copia|"
                         r"ve a|da clic|dale)\b", re.I)

PACES = {  # per video type (reglas-video.md Parte 3)
    "TUT": {"pref": 1.0, "hold": {"result": 1.5, "highlight": 1.5}},   # TUT4 pausado
    "RED": {"pref": 2.0, "hold": {"result": 0.8, "highlight": 0.8}},   # RED3 rápido
    "PRO": {"pref": 1.5, "hold": {"result": 0.8, "highlight": 0.8}},   # dinámico
    "NOV": {"pref": 1.2, "hold": {"result": 1.0, "highlight": 1.0}},   # directo
}
CARD_LIMITS = {  # (min, max) seconds; E1, TUT1, RED1, A2
    "opening": {"TUT": (2.0, 3.0), "RED": (1.5, 2.0), "PRO": (2.0, 3.0), "NOV": (2.0, 3.0)},
    "requirements": {"TUT": (1.5, 5.0)},
    # Closing = its voice + <= 0.3 s (A2): no padding up to a minimum.
    "closing": {"TUT": (1.0, 2.5), "RED": (1.0, 2.5), "PRO": (1.0, 2.5), "NOV": (1.0, 2.5)},
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

def header_rows(row_ink: np.ndarray) -> int:
    """Rows of the header bar at the top (0 without one): the first run of heavy rows starting near the top."""
    h = len(row_ink)
    band = 0
    for r in range(int(h * HEADER_MAX)):
        if row_ink[r] >= HEADER_INK:
            if band == 0 and r >= h * HEADER_START:
                break
            band = r + 1
        elif band:
            break
    return band


def is_blank_image(img: Image.Image) -> bool:
    img.draft("RGB", BLANK_SIZE)
    small = img.convert("RGB").resize(BLANK_SIZE)
    px = np.asarray(small, dtype=np.int16)
    flat = px.reshape(-1, 3)
    keys = (flat // 16) @ np.array([256, 16, 1])
    dom = int(np.bincount(keys).argmax())
    ref = np.array([dom // 256, dom // 16 % 16, dom % 16], dtype=np.int16) * 16 + 8
    ink = np.abs(px - ref).max(axis=2) > BLANK_DIST
    # N26: content is measured below the header band.
    return ink[header_rows(ink.mean(axis=1)):].mean() < BLANK_INK


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


def screen_change(frames: list[dict], flags: list[bool], frames_dir, c: float, share: float = CHANGE_SHARE,
                  window: float = CHANGE_WINDOW) -> float | None:
    """Capture time of the first frame after `c` that shows another screen (>= `share` of the thumbnail moved
    within `window` seconds), or None."""
    times = [f["t"] for f in frames]
    k = bisect.bisect_right(times, c) - 1
    while k >= 0 and flags[k]:
        k -= 1
    if k < 0:
        return None
    ref = _thumb(frames_dir / frames[k]["file"])
    for i in range(k + 1, len(frames)):
        if times[i] > c + window:
            break
        if not flags[i] and (np.abs(_thumb(frames_dir / frames[i]["file"]) - ref) > CHANGE_DIFF).mean() >= share:
            return times[i]
    return None


def mark_screen_changes(actions: dict, frames: list[dict], flags: list[bool], frames_dir) -> int:
    """Adds `screen_c` (capture time of the new screen) to the events that changed it, and `effect_c` (their
    first visible change, N14) to those that changed something."""
    found = 0
    for step in actions["steps"]:
        events = step["events"]
        for k, ev in enumerate(events):
            # A click inside a surface changes the surface, not the recorded tab.
            if ev["type"] in SCREEN_EVENTS and not ev.get("surface"):
                lag = CLICK_LAG if ev["type"] in ("click", "select") else 0.0
                at = screen_change(frames, flags, frames_dir, ev["t"] - lag)
                if at is not None:
                    ev["screen_c"] = at
                    found += 1
                # The effect is searched until the step's next event (a later change is not this action's).
                until = min([e["t"] for e in events[k + 1:] if e["t"] > ev["t"]] + [step.get("t1", ev["t"] + EFFECT_WINDOW)])
                effect = at if at is not None else screen_change(
                    frames, flags, frames_dir, ev["t"] - lag, EFFECT_SHARE,
                    max(0.0, min(EFFECT_WINDOW, until - (ev["t"] - lag))))
                if effect is not None:
                    ev["effect_c"] = effect
    return found


def mixed_flags(frames: list[dict], flags: list[bool], frames_dir) -> list[bool]:
    """N26: frames caught mid-navigation (two views in one frame, “Cr / usu”). Blank frames are skipped."""
    good = [i for i, blank in enumerate(flags) if not blank]
    thumbs = {i: _thumb(frames_dir / frames[i]["file"]) for i in good}
    out = [False] * len(frames)
    for prev, i, nxt in zip(good, good[1:], good[2:]):
        if frames[nxt]["t"] - frames[i]["t"] > MIXED_WINDOW:
            continue
        from_prev = np.abs(thumbs[i] - thumbs[prev]) > CHANGE_DIFF
        from_next = np.abs(thumbs[i] - thumbs[nxt]) > CHANGE_DIFF
        change = min(from_prev.mean(), from_next.mean())
        if change < MIXED_SHARE:
            continue
        out[i] = (from_prev & from_next).mean() <= MIXED_NEITHER * change
    return out


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


def hold_of(ev: dict, pc: dict) -> float:
    """Hold of a result/highlight: the pace's, or longer when the toast needs it (N6, leave_room)."""
    return max(pc["hold"][ev["type"]], ev.get("hold", 0.0))


def _end_of(ev: dict, pc: dict) -> float:
    if ev["type"] == "type":
        return ev.get("t_end", ev["t"])
    if ev["type"] in pc["hold"]:
        return ev["t"] + hold_of(ev, pc)
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
            hold = hold_of(ev, pc)
            fixed.append([ev["t"], min(ev["t"] + hold, nxt, b), "hold", hold])
    cuts = [(max(c0, a), min(c1, b)) for c0, c1 in blanks if c1 > a and c0 < b]
    for ev, nxt in zip(evs, evs[1:]):
        if "screen_c" in ev and nxt["type"] == "result":
            s = clamp(max(ev["t"], ev["screen_c"]))
            if nxt["t"] > s:
                cuts.append((s, nxt["t"]))
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


def _freeze_before(pieces: list[dict], c: float, d: float) -> None:
    k = next((i for i, p in enumerate(pieces) if p["c0"] >= c), len(pieces))
    pieces.insert(k, {"c0": c, "c1": c, "d": d, "kind": "freeze"})


def leave_room(pieces: list[dict], events: list[dict], a: float, b: float, carry: float | None):
    """C7/N6, the contract with compose's camera (compose.establish_room): on every new screen
    - the frame before its first pointer action is held until the establishing shot and the zoom fit;
    - a toast is held until the camera has surely landed on it, plus R2_CLEAN (sets ev["hold"]): on a new
      screen by establish_room, else once the previous target's framing (compose.HOLD) and the pan are over.
    `carry`: output seconds the screen shown at `a` has been on before this step, or None when it already
    had its first action. Returns (same for the next step, whether a hold grew: rebuild the pieces)."""
    clamp = lambda t: min(max(t, a), b)  # noqa: E731
    screen = (a, carry) if carry is not None else None   # (capture start, output seconds before it)
    since = (a, carry or 0.0)
    free = None   # warp offset where compose's camera may leave the previous target of this screen
    grew = False
    for ev in sorted(events, key=lambda e: e["t"]):
        t = clamp(ev["t"])
        kind = camera_kind(ev)
        lands = 0.0
        if ev["type"] in POINTER_EVENTS and screen:
            s, before = screen
            deficit = establish_room(kind) - (before + warp(pieces, t) - warp(pieces, s))
            if deficit > 1e-9:
                _freeze_before(pieces, t, deficit)
            screen = None
        if ev["type"] == "result":
            s, before = since
            elapsed = before + warp(pieces, t) - warp(pieces, s)
            lands = max(0.0, establish_room(None) - elapsed)
            if free is not None:
                lands = max(lands, free + MOVE - warp(pieces, t))
            need = lands + R2_CLEAN + R2_MARGIN
            if need > ev.get("hold", 0.0) + 1e-3:
                ev["hold"] = need
                grew = True
        if kind in HOLD:
            end = clamp(ev.get("t_end", ev["t"])) if ev["type"] == "type" else t
            free = max(free or 0.0, warp(pieces, end) + lands + HOLD[kind])
        if "screen_c" in ev:
            s = clamp(max(t, ev["screen_c"]))
            screen = since = (s, 0.0)
            free = None
    return screen, grew


def camera_kind(ev: dict) -> str:
    """The event as compose's camera sees it: opening a surface is a click on its toolbar icon."""
    return "click" if ev["type"] == "open" else ev["type"]


def instruction_share(narration: str) -> float:
    """Share of the narration (by characters) up to the end of the sentence that asks for the action
    (N1): the first sentence with an imperative, else the whole narration."""
    text = (narration or "").strip()
    sentences = re.findall(r"[^.!?…]+[.!?…]*\s*", text)
    if len(sentences) <= 1:
        return 1.0
    upto = 0
    for sentence in sentences:
        upto += len(sentence)
        if INSTRUCTION.search(sentence):
            return min(1.0, len(text[:upto].rstrip()) / len(text))
    return 1.0


def _sentences(narration: str) -> tuple[str, list[str]]:
    text = (narration or "").strip()
    return text, re.findall(r"[^.!?…]+[.!?…]*\s*", text)


def effect_share(narration: str) -> float | None:
    """N14: share of the narration (by characters) before the sentence that describes the action's visible
    effect ("Aparece la lista"): the sentence right after the instruction, when it asks for nothing. None
    without one."""
    text, sentences = _sentences(narration)
    upto = 0
    for k, sentence in enumerate(sentences):
        upto += len(sentence)
        if INSTRUCTION.search(sentence):
            if k + 1 < len(sentences) and not INSTRUCTION.search(sentences[k + 1]):
                return upto / len(text)
            return None
    return None


def _split(pieces: list[dict], c: float) -> None:
    """Cuts the piece running over capture time c in two (same speed), so a freeze can go exactly at c."""
    for k, p in enumerate(pieces):
        if p["c0"] < c < p["c1"]:
            share = (c - p["c0"]) / (p["c1"] - p["c0"])
            pieces[k:k + 1] = [{**p, "c1": c, "d": p["d"] * share}, {**p, "c0": c, "d": p["d"] * (1 - share)}]
            return


def main_action(events: list[dict]) -> dict | None:
    """N1: the action the narration asks for: the step's first click/select/open, or its single action."""
    ordered = sorted(events, key=lambda e: e["t"])
    first = next((e for e in ordered if e["type"] in ("click", "select", "open")), None)
    if first is None and len(ordered) == 1 and ordered[0]["type"] in ACTION_EVENTS:
        first = ordered[0]
    return first


def plan_step(a: float, b: float, events: list[dict], blanks, voice: float, pc: dict,
              instruction: float | None = None, action=..., carry: float | None = None,
              effect: float | None = None) -> dict:
    """Pick the slowest idle speed that keeps the step within voice + GAP (A2), leave compose room on
    new screens and toasts (C7/N6, leave_room; `carry` as there), hold the frame before the main action
    (default main_action(events)) until the instruction (`instruction` seconds into the voice, default
    all of it) ends at most SYNC_AFTER after it (N1), then pad. `carry` of the result: for the next step.
    N14 `effect`: seconds into the voice where the effect sentence starts; then the instruction ends before
    the action and the frame before the action's `effect_c` is held until that sentence starts."""
    if action is ...:
        action = main_action(events)
    action = action if voice > 0 else None
    at = min(max(action["t"], a), b) if action else None
    instruction = voice if instruction is None else instruction
    effect = effect if action else None
    sync = SYNC_AFTER if effect is None else 0.0
    effect_c = action.get("effect_c", action.get("screen_c")) if effect is not None else None
    ce = max(at, min(effect_c - EFFECT_EPS, b)) if effect_c is not None else None
    speed = pc["pref"]
    while True:
        pieces = build_pieces(a, b, events, blanks, pc, speed)
        screen, grew = leave_room(pieces, events, a, b, carry)
        if grew:
            pieces = build_pieces(a, b, events, blanks, pc, speed)
            screen, _ = leave_room(pieces, events, a, b, carry)
        if action:
            deficit = LEAD + instruction - (warp(pieces, at) + sync)
            if deficit > 1e-9:
                k = next((i for i, p in enumerate(pieces) if p["c0"] >= at), len(pieces))
                pieces.insert(k, {"c0": at, "c1": at, "d": deficit, "kind": "freeze"})
        if ce is not None:
            deficit = LEAD + effect - warp(pieces, ce)
            if deficit > 1e-9:
                _split(pieces, ce)
                _freeze_before(pieces, ce, deficit)
        actions = sum(p["d"] for p in pieces)
        if voice <= 0 or actions <= voice + GAP or speed >= pc["max"]:
            break
        speed = min(round(speed + 0.1, 3), pc["max"])
    # With a main action the voice ends before it and what follows the action is the breathing room:
    # padding a TAIL after it would only add silence (A2).
    need = voice + LEAD + (0.0 if action else TAIL) if voice > 0 else 0.0
    duration = max(actions, need)
    if duration - actions > 1e-9:
        pieces.append({"c0": b, "c1": b, "d": duration - actions, "kind": "freeze"})
    if action:
        offset = LEAD
    else:
        offset = LEAD + max(0.0, duration - voice - GAP) / 2 if voice > 0 else 0.0
    carry_out = screen[1] + warp(pieces, b) - warp(pieces, screen[0]) if screen else None
    return {"pieces": pieces, "duration": duration, "voice_offset": offset, "speed": speed,
            "action_offset": warp(pieces, at) if action else None, "instruction": instruction,
            "effect": effect, "effect_offset": warp(pieces, ce + EFFECT_EPS) if ce is not None else None,
            "carry": carry_out}


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
    # The tail gives way to the cap; only a voice that does not fit by itself overruns it (and warns).
    if voice + lead > hi + 1e-6:
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


def omit_events(events: list[dict], omit, t0: float) -> tuple[list[dict], list[tuple[float, float]]]:
    """videos[].omit: (kept events, capture spans to cut). An omitted type/select loses its whole span:
    the pointer reaching the field (up to OMIT_BEFORE), the focus click and the typing."""
    if not omit:
        return events, []
    kept, spans, prev_end = [], [], t0
    for ev in sorted(events, key=lambda e: e["t"]):
        end = ev.get("t_end", ev["t"])
        if ev["type"] in ("type", "select") and ev.get("selector") in omit:
            spans.append((max(prev_end, ev["t"] - OMIT_BEFORE), end))
        else:
            kept.append(ev)
        prev_end = max(prev_end, end)
    return kept, spans


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
    carry = 0.0   # C7: the first screen starts at screen_start
    for step in video["steps"]:
        cap = captured.get(step["id"])
        if cap is None:
            raise PipelineError(f"El paso '{step['id']}' no está en la captura. Repite capture.py.")
        voice = float(durations.get(step["id"], 0.0))
        captured_events = _capture_events(cap, step)
        events, omitted = omit_events(captured_events, video.get("omit"), cap["t0"])
        # The narration was written for the whole step: its main action is chosen before omit.
        action = main_action(captured_events)
        action = action if action is None or any(e is action for e in events) else None
        instruction = voice * instruction_share(step["narration"])
        share = effect_share(step["narration"])
        plan = plan_step(cap["t0"], cap["t1"], events, list(blanks) + omitted, voice, pc, instruction, action,
                         carry, voice * share if share is not None else None)
        carry = plan["carry"]
        pieces = plan["pieces"]
        out_events = []
        for ev in sorted(events, key=lambda e: e["t"]):
            at = t + warp(pieces, min(max(ev["t"], cap["t0"]), cap["t1"]))
            if ev["type"] == "type":
                end = t + warp(pieces, min(ev.get("t_end", ev["t"]), cap["t1"]))
            elif ev["type"] in pc["hold"]:
                end = at + hold_of(ev, pc)
            else:
                end = at
            item = {"type": ev["type"], "t": _r(at), "t_end": _r(end), "selector": ev.get("selector"),
                    "box": ev.get("box"), "point": ev.get("point"), "chars": ev.get("chars", 0),
                    "secret": bool(ev.get("secret"))}
            item.update({k: ev[k] for k in EVENT_KEYS if k in ev})
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
            "part": step.get("part"), "context": step.get("context"),
            "title": step.get("title"), "narration": step["narration"],
            "start": _r(t), "duration": _r(plan["duration"]),
            "voice_start": _r(t + plan["voice_offset"]) if voice > 0 else _r(t), "voice_duration": _r(voice),
            # N1: output time of the main action and how much of the voice asks for it.
            "action_t": _r(t + plan["action_offset"]) if plan["action_offset"] is not None else None,
            "instruction_duration": _r(plan["instruction"]),
            # N14: seconds into the voice where the effect sentence starts, and when the effect shows.
            "effect_voice": _r(plan["effect"]) if plan["effect"] is not None else None,
            "effect_t": _r(t + plan["effect_offset"]) if plan["effect_offset"] is not None else None,
            "speed": plan["speed"], "events": out_events, "warp": warped,
        })
        t += plan["duration"]
    screen_end = t
    closing = card("closing", t)   # N27: None when the TUT has no closing card
    total = t + (closing["duration"] if closing else 0.0)
    blocks = [("opening", opening), ("requirements", requirements)] + \
        [(s["id"], s) for s in steps] + [("closing", closing)]
    voiced = [(name, b) for name, b in blocks if b and b["voice_duration"] > 0]
    # Cards keep their voice; a step's voice may slide anywhere inside the step (A2), but its instruction
    # never ends later than SYNC_AFTER past the main action (N1).
    def window(b):
        if "events" not in b:
            return b["voice_start"], b["voice_start"]
        hi = b["start"] + b["duration"] - b["voice_duration"]
        if b["action_t"] is not None:
            sync = SYNC_AFTER if b["effect_voice"] is None else 0.0
            hi = min(hi, b["action_t"] + sync - b["instruction_duration"])
        if b["effect_t"] is not None:
            hi = min(hi, b["effect_t"] - b["effect_voice"])
        return b["start"], max(hi, b["start"])
    windows = [window(b) for _, b in voiced]
    starts = place_voices([(lo, hi, b["voice_start"], b["voice_duration"])
                           for (lo, hi), (_, b) in zip(windows, voiced)]) if voiced else []
    for (_, b), start in zip(voiced, starts):
        b["voice_start"] = _r(start)
        if "events" in b:
            # N1: the exact end of the instruction this plan used (qa checks this, it does not re-estimate).
            b["instruction_end"] = _r(start + b["instruction_duration"])
            if b["effect_voice"] is not None:
                b["effect_start"] = _r(start + b["effect_voice"])
    for (name_a, a), (name_b, b) in zip(voiced, voiced[1:]):
        gap = b["voice_start"] - (a["voice_start"] + a["voice_duration"])
        if gap > GAP + 1e-3:
            warnings.append(f"{gap:.1f} s de silencio entre {name_a} y {name_b} (A2 pide como máximo "
                            f"{GAP:.1f} s): alarga la narración o quita acciones")
    source = list(actions.get("viewport", tut.get("viewport", [1920, 1080])))
    output = [1920, 1080] if video["format"] == "16:9" else [1080, 1920]
    timeline = {
        "video": video["id"], "type": vtype, "format": video["format"], "source": source, "output": output,
        "total": _r(total), "product": tut.get("product", ""), "title": tut["title"],
        "opening": opening, "requirements": requirements, "closing": closing,
        "screen_start": _r(screen_start), "screen_end": _r(screen_end), "steps": steps,
        "warnings": warnings,
    }
    if tut.get("parts"):
        timeline["parts"] = [dict(p) for p in tut["parts"]]   # N16: compose draws separators and "Parte N · Paso M"
    surfaces = surface_specs(tut, actions, steps)
    if surfaces:
        timeline["surfaces"] = surfaces
    # N25: text boxes of a followed tab where the censor script could not run, blurred by compose:
    # [{t0, t1, box}] in output time (a region cut in two by the warp gives two items).
    regions = [{"t0": o0, "t1": o1, "box": r["box"]} for r in actions.get("censor_regions") or []
               for o0, o1 in surface_windows(steps, [(r["t0"], r["t1"])])]
    if regions:
        timeline["censor_regions"] = regions
    return timeline


# --- surfaces (perseo-xml S5) ------------------------------------------------------------------

def surface_windows(steps: list[dict], windows) -> list[list[float]]:
    """Output intervals during which a surface open over the capture `windows` [(c0, c1)] is on screen, through
    the steps' warp. A freeze at c counts as before c (like warp): one at the opening is still closed, one
    at the closing still open. Cut pieces show nothing."""
    out: list[list[float]] = []

    def add(o0: float, o1: float) -> None:
        if o1 - o0 <= 1e-9:
            return
        if out and o0 - out[-1][1] <= 1e-3:
            out[-1][1] = _r(o1)
        else:
            out.append([_r(o0), _r(o1)])

    for step in steps:
        for p in step["warp"]:
            c0, c1, o0, o1 = p["c0"], p["c1"], p["o0"], p["o1"]
            if o1 - o0 <= 1e-9:
                continue
            for w0, w1 in windows:
                if c0 == c1:
                    if w0 < c0 <= w1:
                        add(o0, o1)
                    continue
                a, b = max(c0, w0), min(c1, w1)
                if b > a:
                    rate = (o1 - o0) / (c1 - c0)
                    add(o0 + (a - c0) * rate, o0 + (b - c0) * rate)
    return out


def surface_specs(tut: dict, actions: dict, steps: list[dict]) -> dict:
    """timeline `surfaces`: {name: {size, dpr, anchor, icon, file, windows}} for surfaces shown in this video."""
    out = {}
    for name, cap in (actions.get("surfaces") or {}).items():
        windows = surface_windows(steps, [(w["t0"], w["t1"]) for w in cap.get("windows", [])])
        if not windows:
            continue
        spec = (tut.get("surfaces") or {}).get(name) or {}
        out[name] = {"size": list(cap["size"]), "dpr": cap.get("dpr", 1), "anchor": cap.get("anchor", "top-right"),
                     "icon": spec.get("icon"), "file": f"surface-{name}.mp4", "windows": windows}
    return out


# --- video -----------------------------------------------------------------------------------

def frame_entries(frames: list[dict], flags: list[bool], timeline: dict) -> tuple[list[tuple[str, float]], float]:
    """([(frame file, output time from screen_start)], screen length): the warp applied to a frames list
    (the main capture or a surface: same clock). Blank frames are never shown."""
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
    return entries, timeline["screen_end"] - base


def build_video(frames: list[dict], flags: list[bool], frames_dir, timeline: dict, out_path, even: bool = False) -> None:
    """Concat-demuxer list: each frame shown until the next entry's output time. `even`: round the frame size
    down to even pixels (surfaces have any size; yuv420p needs even ones)."""
    entries, end = frame_entries(frames, flags, timeline)
    lines = []
    for (name, t), nxt in zip(entries, [e[1] for e in entries[1:]] + [end]):
        if nxt - t <= 0:
            continue
        lines.append(f"file '{(frames_dir / name).as_posix()}'\nduration {nxt - t:.4f}")
    lines.append(f"file '{(frames_dir / entries[-1][0]).as_posix()}'")
    listing = out_path.with_suffix(".txt")
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
    size = "scale=trunc(iw/2)*2:trunc(ih/2)*2," if even else ""
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(listing), "-vf", f"{size}fps={FPS},format=yuv420p",
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
    if any(flags):
        print(f"[edit] {sum(flags)} cuadros en blanco (cargas, C4/N26)")
    mixed = mixed_flags(frames, flags, frames_dir)
    if any(mixed):
        print(f"[edit] {sum(mixed)} cuadros con dos vistas mezcladas (N26)")
    flags = [b or m for b, m in zip(flags, mixed)]
    blanks = blank_spans(frames, flags)
    if blanks:
        print(f"[edit] corto {len(blanks)} tramos ({sum(b - a for a, b in blanks):.1f} s, C4/N26)")
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
        for name, spec in (timeline.get("surfaces") or {}).items():
            sdir = pdir / "capture" / "surfaces" / name
            sframes = read_json(sdir / "frames.json")["frames"]
            if not sframes:
                raise PipelineError(f"La superficie '{name}' no tiene cuadros en la captura. Repite capture.py.")
            build_video(sframes, [False] * len(sframes), sdir / "frames", timeline, out_dir / spec["file"], even=True)
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
