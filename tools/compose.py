"""Stage: compose. Builds one HyperFrames project per video from the edit + mix artifacts.

Usage: python tools/compose.py <slug>
       python tools/compose.py --fixture tutorial|redes --out DIR   (templates/fixtures, for QA of compose)

For every video V of tutorial.yaml reads edit/V/timeline.json (v2), edit/V/screen.mp4 and
audio/V/mix.wav, and writes proyectos/<slug>/hf-V/ (index.html, assets/, meta.json,
hyperframes.json) plus hf-V/layout.json: every overlay, camera segment and mapped element rect in
output pixels, so qa.py checks the rules (reglas/reglas-video.md) without looking at pixels.

Rules applied here: C1 (detail 1.8-2.5x on every action, context <= 1.0 s), C2 (500 ms
ease-in-out pans, never fades), C3 (target framed >= 500 ms before the click), C5 (48 px cursor
whatever the zoom, halo on click), O1-O3 (chip glued to the caption block, one opaque style),
R1-R3 (result in detail and clean, accent outline on the new element), T1-T3 (caption
segmentation, size, unbreakable product), E1 (opening/closing cards), V1-V4 (real 9:16 crop,
safe zones, title only in the opening).
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from common import (ROOT, PipelineError, ffmpeg, load_tutorial, main_guard, project_dir, read_json, run,
                    which, write_json)

TEMPLATE = ROOT / "templates" / "composition.html"
FIXTURES = ROOT / "templates" / "fixtures"
GSAP = ROOT / "node_modules" / "gsap" / "dist" / "gsap.min.js"
HYPERFRAMES = ROOT / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs"

SRC_W, SRC_H = 1920, 1080
NBSP = "\u00a0"
BRAND_DEFAULTS = {"primary": "#2563eb", "accent": "#facc15", "background": "#0f172a",
                  "text": "#ffffff", "font": "Segoe UI"}

# Camera (C1-C3).
DETAIL_MIN, DETAIL_MAX, DETAIL_PREF = 1.8, 2.5, 2.2
CONTEXT_MAX = 1.0       # C1: a context (1.0x) framing lasts at most this long
MOVE, MOVE_MIN = 0.5, 0.4   # C2: pans/zooms of 400-600 ms
LEAD = 0.5              # C3: target framed this long before the event
# Typing in a row leaves little time between fields: the next field may be framed 0.3 s ahead and the
# camera may leave the previous one during its last 0.2 s of typing (the text is already there).
LEAD_BY_TYPE = {"type": 0.3}
TYPE_OVERLAP = 0.2
EARLY = 0.5             # extra margin when the camera may leave the previous shot freely
BOX_PAD = 16            # source px kept around a framed box
MERGE_GAP = 2.5         # consecutive actions closer than this may share one framing
BOXED = {"click", "hover", "type", "select", "focus", "result", "highlight"}
POINTER = {"click", "hover", "type", "select"}      # the cursor travels to these
SCREEN_CHANGE = {"click", "goto", "press"}          # after these the camera follows the next box at once
HOLD = {"click": 0.3, "hover": 0.5, "type": 0.35, "select": 0.4, "focus": 0.8, "result": 1.0,
        "highlight": 1.5}
R2_CLEAN = 0.8          # R2: result visible without caption or cursor over it

# Overlays (O1-O3, T1-T2, C5).
CURSOR_PX = 48
CURSOR_W = 36
CHAR_W = 0.58           # average advance of the bold sans, in em (conservative)
CAPTION_MIN = 1.2       # T1
CAPTION_BG, CAPTION_FG = "#0b0b12", "#ffffff"
RADIUS = 18
STYLE = f"bold|{CAPTION_BG}|{CAPTION_FG}|r{RADIUS}"   # O3: chip and captions share it everywhere
PAD_X, PAD_Y, CHIP_PAD_Y, BLOCK_GAP, MARGIN = 32, 14, 10, 10, 24

FORMATS = {
    "16:9": {"size": (1920, 1080), "base": 1.0, "floor": 1.0, "font": 44, "chars": 42, "cap_w": 1240,
             "cap_bottom": 1040, "safe_top": 0, "safe_bottom": 1080, "card_font": 80, "card_pad": 160},
    # V1: the 1920x1080 source covers the full height at 1.78x; never below 1.25x (UI >= 70 % high).
    # V4: overlays between the top 15 % (288 px) and the bottom 20 % (1536 px).
    "9:16": {"size": (1080, 1920), "base": 1920 / 1080, "floor": 1.25, "font": 48, "chars": 28,
             "cap_w": 1000, "cap_bottom": 1512, "safe_top": 288, "safe_bottom": 1536, "card_font": 76,
             "card_pad": 130},
}
# Back-compat for readers that only need the output size per format.
LAYOUTS = {k: {"size": v["size"]} for k, v in FORMATS.items()}

STOPWORDS = {"el", "la", "los", "las", "un", "una", "unos", "unas", "lo", "al", "del", "de", "a", "en", "con",
             "por", "para", "sin", "sobre", "entre", "hacia", "hasta", "desde", "y", "e", "o", "u", "ni",
             "que", "pero", "si", "como"}
INF = float("inf")


def hf_env() -> dict:
    return {**os.environ, "HYPERFRAMES_NO_TELEMETRY": "1", "HYPERFRAMES_SKIP_SKILLS": "1"}


def hyperframes(*args, quiet: bool = True, **kwargs):
    if not HYPERFRAMES.exists():
        raise PipelineError("Falta HyperFrames local. Corré: npm install (ver python tools/doctor.py)")
    return run([which("node"), HYPERFRAMES, *args], quiet=quiet, env=hf_env(), cwd=ROOT, **kwargs)


def brand_of(tut: dict, pdir) -> dict:
    brand = {**BRAND_DEFAULTS, **{k: v for k, v in (tut.get("brand") or {}).items() if v}}
    logo = None
    if brand.get("dir"):
        for name in ("logo.svg", "logo.png"):
            if (pdir / brand["dir"] / name).exists():
                logo = pdir / brand["dir"] / name
                break
    brand["logo"] = logo
    return brand


def num(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".") or "0"


def esc(text) -> str:
    return html.escape(str(text or ""), quote=True)


# --- color ------------------------------------------------------------------------------------

def _rgb(color: str) -> tuple[float, float, float]:
    c = color.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _hex(rgb) -> str:
    return "#" + "".join(f"{round(max(0, min(1, v)) * 255):02x}" for v in rgb)


def contrast(a: str, b: str) -> float:
    def lum(color):
        ch = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in _rgb(color)]
        return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def readable(color: str, ground: str, minimum: float) -> str:
    """`color` darkened (on light ground) or lightened (on dark ground) until it reaches `minimum`."""
    toward = (0, 0, 0) if contrast(ground, "#000000") > contrast(ground, "#ffffff") else (1, 1, 1)
    rgb = _rgb(color)
    for _ in range(20):
        if contrast(_hex(rgb), ground) >= minimum:
            break
        rgb = tuple(v + (t - v) * 0.12 for v, t in zip(rgb, toward))
    return _hex(rgb)


# --- text (T1, T3) ----------------------------------------------------------------------------

def protect_product(text: str, product: str | None) -> str:
    """T3: the product name is joined with non-breaking spaces so no line break can split it."""
    if not product or " " not in product:
        return text
    return re.sub(re.escape(product), product.replace(" ", NBSP), text)


def split_words(text: str) -> list[str]:
    """Words split on ordinary whitespace only: str.split() would also break at NBSP."""
    return [w for w in re.split(r"[ \t\r\n]+", text) if w]


def _bare(word: str) -> str:
    return word.strip(".,;:!?¿¡\"'()«»…").lower()


def _break_cost(words: list[str], k: int, caption: bool) -> float:
    """Cost of breaking after words[k] (a line break, or a caption break when `caption`)."""
    word = words[k]
    if k == len(words) - 1:
        return 0
    if re.search(r"[.!?…]$", word):
        return 0 if caption else 5       # a sentence end closes the caption when it can
    if re.search(r"[,;:]$", word):
        return 2 if caption else 1
    if _bare(word) in STOPWORDS:
        return INF                       # T1: never end a line in an article/preposition/conjunction
    if _bare(words[k + 1]) in STOPWORDS:
        return 6 if caption else 3       # phrase boundary: break before the function word
    return 16 if caption else 8          # between two content words ("aviso / verde")


def _width(words: list[str]) -> int:
    return sum(len(w) for w in words) + len(words) - 1


def _lines(words: list[str], max_chars: int, max_lines: int) -> tuple[float, list[str]]:
    """Best split of `words` into <= max_lines lines of <= max_chars characters."""
    n = len(words)
    best = [(INF, [])] * (n + 1)
    best[0] = (0, [])
    for j in range(1, n + 1):
        for i in range(j - 1, -1, -1):
            width = _width(words[i:j])
            if width > max_chars and j - i > 1:
                break
            prev_cost, prev = best[i]
            if prev_cost == INF or len(prev) >= max_lines:
                continue
            cost = prev_cost + (_break_cost(words, j - 1, False) if j < n else 0)
            if width > max_chars:
                cost += 50                   # one unbreakable token longer than the line
            if j - i == 1 and n > 1:
                cost += 4                    # orphan word on its own line
            if cost < best[j][0]:
                best[j] = (cost, prev + [" ".join(words[i:j])])
    cost, lines = best[n]
    if len(lines) == 2:
        cost += abs(len(lines[0]) - len(lines[1])) / max_chars * 4
    return cost, lines


def break_lines(text: str, product: str | None, max_chars: int) -> list[str]:
    """Card text: as many lines as needed, same break rules as captions."""
    words = split_words(protect_product(text, product))
    if not words:
        return []
    return _lines(words, max_chars, len(words))[1]


def segment_captions(text: str, product: str | None, max_chars: int = 42, max_lines: int = 2) -> list[list[str]]:
    """T1: captions of <= max_lines lines x max_chars, no line ending in a function word, product whole."""
    words = split_words(protect_product(text, product))
    n = len(words)
    best = [(INF, [])] * (n + 1)
    best[0] = (0, [])
    for j in range(1, n + 1):
        for i in range(j - 1, -1, -1):
            if _width(words[i:j]) > max_chars * max_lines + max_lines:
                break
            prev_cost, prev = best[i]
            if prev_cost == INF:
                continue
            cost, lines = _lines(words[i:j], max_chars, max_lines)
            if cost == INF or not lines:
                continue
            cost += prev_cost + 3 + (_break_cost(words, j - 1, True) if j < n else 0)
            if _width(words[i:j]) < 16 and n > 4:
                cost += 6                    # too short to read for 1.2 s
            if cost < best[j][0]:
                best[j] = (cost, prev + [lines])
    return best[n][1]


def text_width(text: str, font: float) -> float:
    return len(text) * CHAR_W * font


# --- geometry ---------------------------------------------------------------------------------

def overlaps(a, b, pad: float = 0) -> bool:
    return (a[0] - pad < b[0] + b[2] and b[0] - pad < a[0] + a[2]
            and a[1] - pad < b[1] + b[3] and b[1] - pad < a[1] + a[3])


def rnd(rect) -> list[float]:
    return [round(v, 1) for v in rect]


class Stage:
    """Output geometry of one format: overlay block, safe area for the action, camera framings."""

    def __init__(self, fmt: str, chip: bool):
        if fmt not in FORMATS:
            raise PipelineError(f"timeline.json: formato desconocido '{fmt}' (usa 16:9 o 9:16)")
        self.fmt = fmt
        spec = FORMATS[fmt]
        self.spec = spec
        self.W, self.H = spec["size"]
        self.font = spec["font"]
        self.line_h = round(self.font * 1.25)
        self.chars = spec["chars"]
        self.cap_w = spec["cap_w"]
        self.cap_x = (self.W - self.cap_w) / 2
        self.cap_bottom = spec["cap_bottom"]
        self.chip_h = self.line_h + 2 * CHIP_PAD_Y
        self.chip_y = self.cap_bottom - self.cap_h(2) - BLOCK_GAP - self.chip_h
        block_top = self.chip_y if chip else self.cap_bottom - self.cap_h(2)
        top = spec["safe_top"] + MARGIN
        # O2/V4: the action is framed inside this rect, above the caption block and the unsafe zones.
        self.safe = (MARGIN, top, self.W - 2 * MARGIN, block_top - MARGIN - top)
        self.base = spec["base"]
        self.detail_min = max(DETAIL_MIN, self.base)

    def cap_h(self, lines: int) -> float:
        return lines * self.line_h + 2 * PAD_Y

    def cap_rect(self, lines: int) -> list[float]:
        """Captions hang from a fixed top right under the chip, so the block never jumps (O3)."""
        return [self.cap_x, self.cap_bottom - self.cap_h(2), self.cap_w, self.cap_h(lines)]

    def chip_rect(self, text: str) -> list[float]:
        w = min(self.cap_w, text_width(text, self.font) + 2 * PAD_X)
        return [self.cap_x, self.chip_y, w, self.chip_h]

    def frame(self, cx: float, cy: float, s: float) -> dict:
        sx, sy, sw, sh = self.safe
        # 9:16 may push the source into the unsafe bands (top 15 %, bottom 20 %) so that an element at
        # the edge of the app still lands in the safe area (V4); 16:9 never shows past the source.
        over_top, over_bottom = self.spec["safe_top"], self.H - self.spec["safe_bottom"]
        out = {}
        for axis, c, size, src, lo_safe, len_safe, a, b in (
                ("x", cx, self.W, SRC_W, sx, sw, 0, 0), ("y", cy, self.H, SRC_H, sy, sh, over_top, over_bottom)):
            want = lo_safe + len_safe / 2 - c * s
            span = size - src * s
            out[axis] = round(min(max(want, min(0, span) - b), max(0, span) + a), 1)
        out["s"] = round(s, 4)
        return out

    def context(self, point=None) -> dict:
        cx, cy = (point["x"], point["y"]) if point else (SRC_W / 2, SRC_H / 2)
        return self.frame(cx, cy, self.base)

    def focus_box(self, ev: dict) -> dict:
        """The part of the event box the camera frames: all of it when it fits at detail scale."""
        box = ev["box"]
        sw, sh = self.safe[2], self.safe[3]
        max_w = sw / self.detail_min - 2 * BOX_PAD
        max_h = sh / self.detail_min - 2 * BOX_PAD
        if box["w"] <= max_w and box["h"] <= max_h:
            return box
        point = ev.get("point") or {"x": box["x"] + box["w"] / 2, "y": box["y"] + box["h"] / 2}
        w, h = min(box["w"], max_w), min(box["h"], max_h)
        # Text and rows are read from the left; a click target is framed around the pointer.
        x = box["x"] if ev["type"] in ("type", "highlight", "result", "focus") else point["x"] - w / 2
        y = box["y"] if box["h"] <= max_h else point["y"] - h / 2
        x = min(max(x, box["x"]), box["x"] + box["w"] - w)
        y = min(max(y, box["y"]), box["y"] + box["h"] - h)
        return {"x": x, "y": y, "w": w, "h": h}

    def fit(self, box: dict) -> float:
        return min(self.safe[2] / (box["w"] + 2 * BOX_PAD), self.safe[3] / (box["h"] + 2 * BOX_PAD))

    def detail(self, box: dict) -> dict:
        s = max(min(DETAIL_PREF, DETAIL_MAX, self.fit(box)), self.detail_min)
        return self.frame(box["x"] + box["w"] / 2, box["y"] + box["h"] / 2, s)

    @staticmethod
    def map(box: dict, fr: dict) -> list[float]:
        return [box["x"] * fr["s"] + fr["x"], box["y"] * fr["s"] + fr["y"], box["w"] * fr["s"], box["h"] * fr["s"]]


def union(a: dict, b: dict) -> dict:
    x, y = min(a["x"], b["x"]), min(a["y"], b["y"])
    return {"x": x, "y": y, "w": max(a["x"] + a["w"], b["x"] + b["w"]) - x,
            "h": max(a["y"] + a["h"], b["y"] + b["h"]) - y}


# --- camera (C1-C3, R1) -----------------------------------------------------------------------

def lead(ev: dict) -> float:
    return LEAD_BY_TYPE.get(ev["type"], LEAD)


def shots_of(timeline: dict, stage: Stage) -> list[dict]:
    """Groups the boxed events into framings: one per click/result/highlight, typing in a row shares one."""
    shots = []
    for step in timeline["steps"]:
        for ev in sorted((e for e in step["events"] if e["type"] in BOXED and e.get("box")), key=lambda e: e["t"]):
            fbox = stage.focus_box(ev)
            end = (ev.get("t_end") or ev["t"]) + HOLD[ev["type"]]
            last = shots[-1] if shots else None
            if (last and last["step"] == step["id"] and last["events"][-1]["type"] not in ("click", "result", "highlight")
                    and ev["type"] not in ("result", "highlight")
                    and ev["t"] - last["last"] <= MERGE_GAP
                    and stage.fit(union(last["box"], fbox)) >= stage.detail_min):
                last["box"] = union(last["box"], fbox)
                last["events"].append(ev)
                last["last"] = ev.get("t_end") or ev["t"]
                last["release"] = max(last["release"], end)
                continue
            shots.append({"step": step["id"], "events": [ev], "box": fbox, "need": ev["t"] - lead(ev),
                          "last": ev.get("t_end") or ev["t"], "release": end,
                          "point": ev.get("point") or {"x": fbox["x"] + fbox["w"] / 2, "y": fbox["y"] + fbox["h"] / 2}})
    for shot in shots:
        shot["frame"] = stage.detail(shot["box"])
    return shots


def camera_plan(timeline: dict, stage: Stage) -> list[dict]:
    """Contiguous camera segments over [screen_start, screen_end]: holds (context/detail) and moves."""
    ss, se = timeline["screen_start"], timeline["screen_end"]
    shots = shots_of(timeline, stage)
    changes = sorted(e["t"] for s in timeline["steps"] for e in s["events"] if e["type"] in SCREEN_CHANGE)
    segs: list[dict] = []

    def hold(frame, until, kind):
        t0 = segs[-1]["t1"] if segs else ss
        until = min(until, se)
        if until - t0 <= 1e-6:
            return
        if segs and segs[-1]["kind"] == kind and segs[-1]["to"] == frame:
            segs[-1]["t1"] = until
        else:
            segs.append({"t0": t0, "t1": until, "kind": kind, "to": frame, "from": frame})

    def move(frame, start, dur):
        prev = segs[-1]["to"] if segs else frame
        segs.append({"t0": start, "t1": min(start + dur, se), "kind": "move", "from": prev, "to": frame})

    def go(frame, kind_prev, earliest, need, hard=ss):
        """Hold the current framing, then pan/zoom so `frame` is reached by `need` (never before `hard`)."""
        cur = max(segs[-1]["t1"] if segs else ss, hard)
        if segs and segs[-1]["to"] == frame:
            return
        start = max(cur, earliest)
        if start + MOVE > need:
            start = max(cur, need - MOVE)
        dur = min(MOVE, max(MOVE_MIN, need - start))
        if start >= se:
            return
        hold(segs[-1]["to"], start, kind_prev)
        move(frame, start, dur)

    if not shots:
        hold(stage.context(), se, "context")
        return finish(segs, stage)

    first = shots[0]
    tut_wide = timeline.get("type", "TUT") == "TUT" and stage.fmt == "16:9"
    if tut_wide and first["need"] - ss >= CONTEXT_MAX + MOVE:
        # A short establishing shot (C1: context <= 1.0 s) before the first action of a tutorial.
        segs.append({"t0": ss, "t1": ss, "kind": "context", "to": stage.context(first["point"]),
                     "from": stage.context(first["point"])})
        go(first["frame"], "context", min(ss + CONTEXT_MAX, first["need"] - MOVE), first["need"])
    else:
        segs.append({"t0": ss, "t1": ss, "kind": "detail", "to": first["frame"], "from": first["frame"]})
    kind_prev = "detail"
    screens = sorted(e["screen_at"] for s in timeline["steps"] for e in s["events"] if e.get("screen_at") is not None)
    for prev, shot in zip(shots, shots[1:]):
        cut = next((t for t in screens if prev["events"][-1]["t"] - 1e-6 <= t <= shot["events"][0]["t"]), None)
        if cut is not None:
            # The screen changed (edit's screen_at): cut to the next target with the new screen, even if
            # that is later than its lead (it did not exist before). A pan would cross the empty parts of
            # the new screen (C4); a cut is not a cross-fade of the same screen (C2).
            cut = max(cut, segs[-1]["t1"])
            hold(segs[-1]["to"], cut, kind_prev)
            segs.append({"t0": cut, "t1": cut, "kind": "detail", "to": shot["frame"], "from": shot["frame"]})
            kind_prev = "detail"
            continue
        follow = prev["events"][-1]["type"] == "click" or any(prev["last"] < t <= shot["need"] for t in changes)
        if follow:
            # The screen changed: straight on to the next target in detail (C1). A 1.0x look at the new
            # screen ran past 1.0 s with its zoom-out and showed sparse or dimmed pages half empty (C4).
            earliest = max(prev["release"], prev["last"] + 0.1)
        else:
            earliest = max(prev["release"], shot["need"] - MOVE - EARLY)
        # Never leave before the previous action happened, even if the next target arrives late.
        typing = prev["events"][-1]["type"] == "type" and shot["events"][0]["type"] == "type"
        go(shot["frame"], kind_prev, earliest, shot["need"], prev["last"] + (-TYPE_OVERLAP if typing else 0.1))
    hold(segs[-1]["to"], se, "detail" if segs[-1]["kind"] != "context" else "context")
    return finish(segs, stage)


def finish(segs: list[dict], stage: Stage) -> list[dict]:
    out = []
    for seg in segs:
        if seg["t1"] - seg["t0"] <= 1e-6:
            continue
        to = seg["to"]
        item = {"t0": round(seg["t0"], 3), "t1": round(seg["t1"], 3), "scale": to["s"], "kind": seg["kind"],
                "x": to["x"], "y": to["y"]}
        if seg["kind"] == "move":
            item["from"] = seg["from"]
        if seg["kind"] == "context":
            item["scale"] = round(stage.base, 4)
        out.append(item)
    for a, b in zip(out, out[1:]):
        b["t0"] = a["t1"]
    return out


def ease(p: float) -> float:
    """GSAP power2.inOut."""
    return 2 * p * p if p < 0.5 else 1 - (-2 * p + 2) ** 2 / 2


def frame_at(camera: list[dict], t: float) -> dict:
    seg = next((s for s in camera if s["t0"] <= t < s["t1"]), camera[-1] if t >= camera[-1]["t1"] else camera[0])
    to = {"x": seg["x"], "y": seg["y"], "s": seg["scale"]}
    if seg["kind"] != "move":
        return to
    p = ease(min(max((t - seg["t0"]) / (seg["t1"] - seg["t0"]), 0), 1))
    fr = seg["from"]
    return {k: fr[k] + (to[k] - fr[k]) * p for k in ("x", "y", "s")}


# --- plan: layout.json ------------------------------------------------------------------------

def subtract(spans: list[tuple[float, float]], blocked: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out = spans
    for b0, b1 in sorted(blocked):
        nxt = []
        for a0, a1 in out:
            if b1 <= a0 or b0 >= a1:
                nxt.append((a0, a1))
                continue
            if b0 > a0:
                nxt.append((a0, b0))
            if b1 < a1:
                nxt.append((b1, a1))
        out = nxt
    return [(a, b) for a, b in out if b - a > 1e-6]


def schedule(caps: list[list[str]], v0: float, vdur: float, s0: float, s1: float,
             blocked: list[tuple[float, float]]) -> list[tuple[float, float, list[str]]]:
    """T1: captions in time order inside the step, >= 1.2 s each, outside the blocked windows."""
    if not caps:
        return []
    free = subtract([(max(v0, s0), s1)], blocked)
    total = sum(len(" ".join(c)) for c in caps)
    wants = [max(CAPTION_MIN, max(vdur, CAPTION_MIN) * len(" ".join(c)) / total) for c in caps]
    out, t, k = [], None, 0
    for lines, want in zip(caps, wants):
        while k < len(free):
            a, b = free[k]
            t = a if t is None or t < a else t
            if b - t >= CAPTION_MIN - 1e-9:
                break
            k += 1
            t = None
        if k >= len(free):
            # No room left: the rest joins the last caption if it still fits in two lines.
            if out and len(out[-1][2]) + len(lines) <= 2:
                out[-1] = (out[-1][0], out[-1][1], out[-1][2] + lines)
            continue
        end = min(t + want, free[k][1])
        out.append((t, end, lines))
        t = end
    # Stretch each caption up to the next one (or its interval end) so text never blinks out mid-step.
    final = []
    for i, (t0, t1, lines) in enumerate(out):
        limit = next((b for a, b in free if a - 1e-9 <= t0 < b), t1)
        nxt = out[i + 1][0] if i + 1 < len(out) else limit
        final.append((t0, min(max(t1, t0 + CAPTION_MIN), nxt, limit) if nxt > t0 else t1, lines))
    return final


def step_label(timeline: dict, step: dict) -> str | None:
    """O1/PRO4: no chip on PRO/NOV; 'Parte N · Paso M' when the tutorial has chapters (E3)."""
    kind = timeline.get("type", "TUT")
    if kind not in ("TUT", "RED"):
        return None
    number = step.get("number") or (timeline["steps"].index(step) + 1)
    if step.get("chapter"):
        same = [s for s in timeline["steps"] if s.get("chapter") == step["chapter"]]
        label = f"Parte {step['chapter']} · Paso {same.index(step) + 1}"
    else:
        label = f"Paso {number}"
    return f"{label} · {step['title']}" if step.get("title") else label


def card_lines(text: str, product: str | None, width: float, font: float, max_lines: int = 3):
    """Lines and font size for card text: shrink until it fits (T3: the product never splits)."""
    for _ in range(12):
        chars = max(8, int(width / (CHAR_W * font)))
        lines = break_lines(text, product, chars)
        if lines and len(lines) <= max_lines and max(len(line) for line in lines) <= chars:
            return lines, font
        font *= 0.9
    return lines, font


def plan(timeline: dict, brand: dict) -> dict:
    """Everything compose decides, in output pixels: the layout.json of the video (L5)."""
    kind = timeline.get("type", "TUT")
    fmt = timeline.get("format", "16:9")
    product = timeline.get("product")
    labels = {s["id"]: step_label(timeline, s) for s in timeline["steps"]}
    stage = Stage(fmt, chip=any(labels.values()))
    camera = camera_plan(timeline, stage)
    accent = brand.get("accent") or BRAND_DEFAULTS["accent"]
    items: list[dict] = []
    protected: list[tuple[float, float, list[float]]] = []
    ends = {s["id"]: s["start"] + s["duration"] for s in timeline["steps"]}

    # Elements of every event, mapped through the camera.
    pointer_events = []
    for step in timeline["steps"]:
        for ev in sorted(step["events"], key=lambda e: e["t"]):
            if ev["type"] in POINTER and ev.get("point"):
                pointer_events.append(ev)
            if ev["type"] not in BOXED or not ev.get("box"):
                continue
            fbox = stage.focus_box(ev)
            fr = frame_at(camera, ev["t"])
            rect = rnd(stage.map(fbox, fr))
            base = {"t": round(ev["t"], 3), "step": step["id"], "event": ev["type"],
                    "selector": ev.get("selector", ""), "rect": rect, "full_rect": rnd(stage.map(ev["box"], fr))}
            if ev["type"] == "result":
                t1 = min(max(ev["t"] + HOLD["result"], ev["t"] + R2_CLEAN), max(ends[step["id"]], ev["t"] + R2_CLEAN))
                items.append({"kind": "result", "t0": round(ev["t"], 3), "t1": round(t1, 3), **base})
                protected.append((ev["t"] - 0.1, t1, rect))
            elif ev["type"] == "highlight":
                color = readable(accent, "#ffffff", 3.0)
                t1 = max(ends[step["id"]], ev["t"] + HOLD["highlight"])
                items.append({"kind": "highlight", "t0": round(ev["t"], 3), "t1": round(min(t1, timeline["screen_end"]), 3),
                              **base, "color": color, "contrast": round(contrast(color, "#ffffff"), 2)})
                protected.append((ev["t"], t1, rect))
            else:
                t0 = max(ev["t"] - lead(ev), timeline["screen_start"])
                t1 = (ev.get("t_end") or ev["t"]) + HOLD[ev["type"]]
                start = rnd(stage.map(fbox, frame_at(camera, t0)))
                items.append({"kind": "active", "t0": round(t0, 3), "t1": round(t1, 3), **base, "rect_start": start})
                protected.append((t0, t1, rect))

    # Cursor (C5): samples at each pointer event and at each result; hidden when over a result (R2).
    hidden: list[tuple[float, float]] = []
    for item in [i for i in items if i["kind"] == "result"]:
        last = [e for e in pointer_events if e["t"] <= item["t0"]]
        if not last:
            continue
        p = last[-1]["point"]
        fr = frame_at(camera, item["t0"])
        crect = [p["x"] * fr["s"] + fr["x"], p["y"] * fr["s"] + fr["y"], CURSOR_W, CURSOR_PX]
        in_frame = crect[0] >= 0 and crect[1] >= 0 and crect[0] + CURSOR_W <= stage.W and crect[1] + CURSOR_PX <= stage.H
        if overlaps(crect, item["rect"], 16) or not in_frame:
            nxt = next((e["t"] for e in pointer_events if e["t"] > item["t0"]), timeline["screen_end"])
            hidden.append((item["t0"] - 0.1, max(item["t1"], min(nxt - 0.6, timeline["screen_end"]))))
        else:
            items.append({"kind": "cursor", "t0": item["t0"], "t1": item["t0"], "event": "result", "rect": rnd(crect)})
    for ev in pointer_events:
        if any(a <= ev["t"] < b for a, b in hidden):
            continue
        fr = frame_at(camera, ev["t"])
        p = ev["point"]
        items.append({"kind": "cursor", "t0": round(ev["t"], 3), "t1": round(ev["t"], 3), "event": ev["type"],
                      "rect": rnd([p["x"] * fr["s"] + fr["x"], p["y"] * fr["s"] + fr["y"], CURSOR_W, CURSOR_PX])})

    # Chip + captions: one block, one style (O1-O3); away from active/result/highlight (O2, R2).
    cap2 = stage.cap_rect(2)
    accent_ok = contrast(accent, CAPTION_BG) >= 4.5
    for step in timeline["steps"]:
        s0, s1 = step["start"], step["start"] + step["duration"]
        label = labels[step["id"]]
        if label:
            rect = stage.chip_rect(label)
            if rect[2] >= stage.cap_w:
                label = label.split(" · ")[0] if not step.get("chapter") else " · ".join(label.split(" · ")[:2])
                rect = stage.chip_rect(label)
            blocked = [(a, b) for a, b, r in protected if overlaps(r, rect, 8)]
            for a, b in subtract([(s0, s1)], blocked):
                items.append({"kind": "chip", "t0": round(a, 3), "t1": round(b, 3), "rect": rnd(rect), "text": label,
                              "step": step["id"], "style": STYLE, "opacity": 1,
                              "contrast": round(min(contrast(CAPTION_FG, CAPTION_BG),
                                                    contrast(accent, CAPTION_BG) if accent_ok else 99), 2),
                              "label_color": accent if accent_ok else CAPTION_FG})
        caps = segment_captions(step.get("narration") or "", product, stage.chars)
        blocked = [(a, b) for a, b, r in protected if overlaps(r, cap2, 8)]
        for t0, t1, lines in schedule(caps, step.get("voice_start", s0), step.get("voice_duration", 0), s0, s1, blocked):
            items.append({"kind": "caption", "t0": round(t0, 3), "t1": round(t1, 3), "rect": rnd(stage.cap_rect(len(lines))),
                          "text": " ".join(lines), "lines": lines, "step": step["id"], "style": STYLE})

    cards = plan_cards(timeline, stage, product, kind)
    items.extend(cards)
    items.sort(key=lambda i: (i["t0"], i["kind"]))
    return {"video": timeline.get("video"), "type": kind, "format": fmt, "total": timeline["total"],
            "output": [stage.W, stage.H], "viewport": [0, 0, stage.W, stage.H], "base_scale": round(stage.base, 4),
            "safe": {"top": stage.spec["safe_top"], "bottom": stage.spec["safe_bottom"], "action": rnd(stage.safe)},
            "cursor_px": CURSOR_PX, "font_px": stage.font, "screen": [timeline["screen_start"], timeline["screen_end"]],
            "camera": camera, "cursor_hidden": [[round(a, 3), round(b, 3)] for a, b in hidden], "items": items}


def plan_cards(timeline: dict, stage: Stage, product: str | None, kind: str) -> list[dict]:
    spec = stage.spec
    width = stage.W - 2 * spec["card_pad"]
    mid = (spec["safe_top"] + spec["safe_bottom"]) / 2
    out = []
    parts = [("opening", timeline.get("opening")), ("requirements", timeline.get("requirements")),
             ("closing", timeline.get("closing"))]
    for name, card in parts:
        if not card or not card.get("text"):
            continue
        lines, font = card_lines(card["text"], product, width, spec["card_font"])
        line_h = round(font * 1.15)
        blocks = [("card", lines, font, line_h)]
        if name == "opening" and kind == "TUT" and timeline.get("title"):
            tfont = round(font * 0.5)
            tlines, tfont = card_lines(timeline["title"], product, width, tfont, 2)
            blocks.insert(0, ("title", tlines, tfont, round(tfont * 1.25)))
        gap = 40
        height = sum(len(b[1]) * b[3] for b in blocks) + gap * (len(blocks) - 1)
        y = mid - height / 2
        t0 = card.get("start", 0)
        t1 = t0 + card["duration"]
        if name == "closing":
            t1 = timeline["total"]
        for kind_, blines, bfont, bline_h in blocks:
            w = min(width, max(text_width(line, bfont) for line in blines))
            h = len(blines) * bline_h
            item = {"kind": kind_, "t0": round(t0, 3), "t1": round(min(t1, t0 + 3.0) if kind_ == "title" else t1, 3),
                    "rect": rnd([(stage.W - w) / 2, y, w, h]), "text": " ".join(blines), "lines": blines,
                    "card": name, "font": round(bfont, 1), "line_h": bline_h}
            out.append(item)
            y += h + gap
    return out


# --- html -------------------------------------------------------------------------------------

def fill(template: str, values: dict) -> str:
    def sub(m):
        key = m.group(1)
        if key not in values:
            raise PipelineError(f"templates/composition.html: falta el valor '{key}'")
        return str(values[key])
    return re.sub(r"\{\{([A-Z_]+)\}\}", sub, template)


def lines_html(lines: list[str]) -> str:
    return "<br />".join(esc(line).replace(NBSP, "&nbsp;") for line in lines)


def box_style(rect) -> str:
    x, y, w, h = rect
    return f"left: {num(x)}px; top: {num(y)}px; width: {num(w)}px; height: {num(h)}px"


def build(timeline: dict, brand: dict, logo_src: str | None = None) -> tuple[str, dict]:
    """(index.html, layout) for one video."""
    brand = {**BRAND_DEFAULTS, **{k: v for k, v in brand.items() if v}}
    layout = plan(timeline, brand)
    W, H = layout["output"]
    ss, se, total = timeline["screen_start"], timeline["screen_end"], timeline["total"]
    items = layout["items"]
    script: list[str] = []

    # Camera: CSS variables so the cursor can divide by the same scale every frame (C5).
    cam = layout["camera"]
    c0 = cam[0].get("from") or cam[0]
    script.append(f'tl.set("#cam", {{"--cx": {num(c0["x"])}, "--cy": {num(c0["y"])}, '
                  f'"--s": {num(c0.get("s", c0.get("scale")))}}}, 0);')
    for before, seg in zip([None] + cam, cam):
        if seg["kind"] != "move" and before and (before["x"], before["y"], before["scale"]) != (seg["x"], seg["y"], seg["scale"]):
            # A cut on a screen change (camera_plan): the new framing starts with the new screen.
            script.append(f'tl.set("#cam", {{"--cx": {num(seg["x"])}, "--cy": {num(seg["y"])}, '
                          f'"--s": {num(seg["scale"])}}}, {num(seg["t0"])});')
        if seg["kind"] == "move":
            script.append(f'tl.to("#cam", {{"--cx": {num(seg["x"])}, "--cy": {num(seg["y"])}, "--s": {num(seg["scale"])}, '
                          f'duration: {num(seg["t1"] - seg["t0"])}, ease: "power2.inOut"}}, {num(seg["t0"])});')

    # Cursor: waypoints; halo on clicks; hidden over results (R2).
    pointer = [e for s in timeline["steps"] for e in sorted(s["events"], key=lambda e: e["t"])
               if e["type"] in POINTER and e.get("point")]
    if pointer:
        p0 = pointer[0]["point"]
        script.append(f'tl.set("#cursor", {{x: {num(min(p0["x"] + 200, SRC_W - 80))}, '
                      f'y: {num(min(p0["y"] + 140, SRC_H - 80))}, opacity: 1}}, 0);')
        last = ss
        for ev in pointer:
            t, p = ev["t"], ev["point"]
            # The cursor rests on the target before acting (recorded click times may trail the page change).
            start = max(last, t - 0.8)
            arrive = t - 0.25
            if arrive - start >= 0.1:
                script.append(f'tl.to("#cursor", {{x: {num(p["x"])}, y: {num(p["y"])}, duration: {num(arrive - start)}, '
                              f'ease: "power2.inOut"}}, {num(start)});')
            else:
                script.append(f'tl.set("#cursor", {{x: {num(p["x"])}, y: {num(p["y"])}}}, {num(max(start, last))});')
            last = max(t, last)
            if ev["type"] == "click":
                script.append(f'tl.set("#halo", {{scale: 0.3, opacity: 0.9}}, {num(t)});')
                script.append(f'tl.to("#halo", {{scale: 1.6, opacity: 0, duration: 0.5, ease: "power2.out"}}, {num(t)});')
                script.append(f'tl.to("#cursor-arrow", {{scale: 0.82, duration: 0.08, ease: "power1.out"}}, {num(t)});')
                script.append(f'tl.to("#cursor-arrow", {{scale: 1, duration: 0.14, ease: "power1.in"}}, {num(t + 0.08)});')
                last = max(last, t + 0.22)
        for a, b in layout["cursor_hidden"]:
            script.append(f'tl.set("#cursor", {{opacity: 0}}, {num(a)});')
            script.append(f'tl.set("#cursor", {{opacity: 1}}, {num(b)});')
    else:
        script.append('tl.set("#cursor", {opacity: 0}, 0);')

    # Highlights (R3): accent outline at 100 % plus a pulsing glow, inside the camera.
    hl_markup = []
    for i, item in enumerate(i for i in items if i["kind"] == "highlight"):
        ev = next(e for s in timeline["steps"] for e in s["events"]
                  if e["type"] == "highlight" and round(e["t"], 3) == item["t0"])
        b = ev["box"]
        hid = f"hl-{i}"
        hl_markup.append(f'          <div class="hl" id="{hid}" style="{box_style([b["x"] - 6, b["y"] - 4, b["w"] + 12, b["h"] + 8])}; '
                         f'--hl: {item["color"]}"><div class="hl-glow" id="{hid}-glow"></div></div>')
        script.append(f'tl.set("#{hid}", {{opacity: 1}}, {num(item["t0"])});')
        for k in range(2):
            t = item["t0"] + k * 0.7
            script.append(f'tl.to("#{hid}-glow", {{opacity: 0.85, duration: 0.3, ease: "sine.inOut"}}, {num(t)});')
            script.append(f'tl.to("#{hid}-glow", {{opacity: 0.25, duration: 0.4, ease: "sine.inOut"}}, {num(t + 0.3)});')
        script.append(f'tl.set("#{hid}", {{opacity: 0}}, {num(item["t1"])});')

    # Chip + captions: absolute rects from the plan; they appear at 100 % opacity at once (O1).
    overlays = []
    for i, item in enumerate(i for i in items if i["kind"] == "chip"):
        head, _, rest = item["text"].partition(" · ")
        if item["text"].startswith("Parte "):
            p1, _, rest2 = rest.partition(" · ")
            head, rest = f"{head} · {p1}", rest2
        tail = f' <span class="sep">·</span> {esc(rest)}' if rest else ""
        overlays.append(f'      <div id="chip-{i}" class="clip ov-layer" data-start="{num(item["t0"])}" '
                        f'data-duration="{num(item["t1"] - item["t0"])}"><div class="ov chip" '
                        f'style="{box_style(item["rect"])}"><b style="color: {item["label_color"]}">{esc(head)}</b>{tail}</div></div>')
    for i, item in enumerate(i for i in items if i["kind"] == "caption"):
        overlays.append(f'      <div id="cap-{i}" class="clip ov-layer" data-start="{num(item["t0"])}" '
                        f'data-duration="{num(item["t1"] - item["t0"])}"><div class="ov cap" '
                        f'style="{box_style(item["rect"])}">{lines_html(item["lines"])}</div></div>')

    # Cards (E1): opening/requirements/closing scenes; title only in the opening (V3).
    cards = []
    scenes = {}
    for item in items:
        if item["kind"] in ("card", "title"):
            scenes.setdefault(item["card"], []).append(item)
    for name, parts in scenes.items():
        t0 = min(p["t0"] for p in parts)
        t1 = max(p["t1"] for p in parts)
        inner = []
        if logo_src and name in ("opening", "closing"):
            top = min(p["rect"][1] for p in parts)
            inner.append(f'        <img class="logo" id="{name}-logo" src="{logo_src}" alt="" '
                         f'style="top: {num(max(stage_top(layout), top - 190))}px" />')
        for k, p in enumerate(parts):
            cls = "card-title" if p["kind"] == "title" else "card-text"
            pid = f"{name}-{p['kind']}"
            inner.append(f'        <div class="{cls}" id="{pid}" style="{box_style(p["rect"])}; '
                         f'font-size: {num(p["font"])}px; line-height: {p["line_h"]}px">{lines_html(p["lines"])}</div>')
            script.append(f'tl.from("#{pid}", {{y: 30, duration: 0.35, ease: "power3.out"}}, {num(t0 + 0.05 * k)});')
        bar_y = max(p["rect"][1] + p["rect"][3] for p in parts) + 28
        inner.append(f'        <div class="bar" id="{name}-bar" style="top: {num(bar_y)}px"></div>')
        script.append(f'tl.from("#{name}-bar", {{scaleX: 0, duration: 0.4, ease: "power3.out"}}, {num(t0 + 0.1)});')
        cards.append(f'      <div id="{name}" class="clip scene" data-start="{num(t0)}" data-duration="{num(t1 - t0)}">\n'
                     + "\n".join(inner) + "\n      </div>")

    values = {
        "WIDTH": W, "HEIGHT": H, "ORIENTATION": "portrait" if H > W else "landscape",
        "PRIMARY": brand["primary"], "ACCENT": brand["accent"], "BACKGROUND": brand["background"],
        "TEXT": readable(brand["text"], brand["background"], 4.5),
        "FONT": f'"{brand["font"]}", "Segoe UI", Arial, sans-serif',
        "FONT_PX": layout["font_px"], "LINE_H": round(layout["font_px"] * 1.25), "PAD_X": PAD_X, "PAD_Y": PAD_Y,
        "CHIP_PAD_Y": CHIP_PAD_Y, "RADIUS": RADIUS, "CAP_BG": CAPTION_BG, "CAP_FG": CAPTION_FG,
        "CURSOR_PX": CURSOR_PX, "CURSOR_W": CURSOR_W,
        "TOTAL": num(total), "SCREEN_START": num(ss), "SCREEN": num(se - ss),
        "HIGHLIGHTS": "\n".join(hl_markup), "OVERLAYS": "\n".join(overlays), "CARDS": "\n".join(cards),
        "TIMELINE": "\n".join("      " + line for line in script),
    }
    return fill(TEMPLATE.read_text(encoding="utf-8"), values), layout


def stage_top(layout: dict) -> float:
    return layout["safe"]["top"] + 20


# --- project ----------------------------------------------------------------------------------

def compose_video(timeline: dict, screen: Path, mix: Path, brand: dict, out: Path, logo: Path | None = None,
                  checked: bool = True) -> dict:
    """Writes the HyperFrames project of one video into `out` (index.html, assets/, layout.json)."""
    if not GSAP.exists():
        raise PipelineError("Falta node_modules/gsap. Corré: npm install")
    assets = out / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(screen, assets / "screen.mp4")
    shutil.copyfile(mix, assets / "mix.wav")
    shutil.copyfile(GSAP, assets / "gsap.min.js")
    logo_src = None
    if logo:
        logo_src = f"assets/{logo.name}"
        shutil.copyfile(logo, assets / logo.name)
    page, layout = build(timeline, brand, logo_src)
    (out / "index.html").write_text(page, encoding="utf-8")
    write_json(out / "layout.json", layout)
    video = timeline.get("video") or out.name
    write_json(out / "meta.json", {"id": video, "name": f"{timeline.get('title', video)} ({video})"})
    write_json(out / "hyperframes.json", {
        "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
        "paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"},
        "media": {"autoProxy": True},
    })
    warnings = check(out) if checked else 0
    w, h = layout["output"]
    print(f"[compose] {video}: {timeline.get('type', 'TUT')} {w}x{h}, {timeline['total']:.1f} s, "
          f"{len(timeline['steps'])} pasos{'' if logo_src else ', sin logo'}, check OK ({warnings} avisos) -> {out}")
    return {"dir": str(out), "total": timeline["total"], "size": [w, h], "warnings": warnings}


def check(out) -> int:
    """Run `hyperframes check`; any error fails the stage. Returns the warning count."""
    if not HYPERFRAMES.exists():
        raise PipelineError("Falta HyperFrames local. Corré: npm install (ver python tools/doctor.py)")
    # Not common.run: check exits non-zero on errors and we want its JSON report either way.
    proc = subprocess.run([which("node"), str(HYPERFRAMES), "check", str(out), "--json", "--no-cache"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=hf_env(), cwd=ROOT)
    try:
        report = json.loads(proc.stdout[proc.stdout.index("{"):])
    except ValueError:
        tail = "\n".join((proc.stderr or proc.stdout).strip().splitlines()[-15:])
        raise PipelineError(f"hyperframes check no devolvió un reporte (exit {proc.returncode}):\n{tail}")
    passes = [v for v in report.values() if isinstance(v, dict) and "findings" in v]
    errors = [f for p in passes for f in p["findings"] if f.get("severity") == "error"]
    if errors or not report.get("ok"):
        lines = "\n".join(f"  - {f.get('code')}: {f.get('message')} ({f.get('selector', '')})" for f in errors[:10])
        raise PipelineError(f"hyperframes check encontró errores en {Path(out).name}:\n{lines}")
    return sum(p.get("warningCount", 0) for p in passes)


def video_ids(tut: dict, pdir: Path) -> list[str]:
    ids = [v["id"] for v in tut.get("videos") or [] if v.get("id")]
    if not ids:
        ids = sorted(p.parent.name for p in (pdir / "edit").glob("*/timeline.json"))
    return ids


def compose(slug: str) -> dict:
    tut = load_tutorial(slug)
    pdir = project_dir(slug)
    brand = brand_of(tut, pdir)
    ids = video_ids(tut, pdir)
    if not ids:
        raise PipelineError("No hay videos en tutorial.yaml ni cortes en edit/. Corré antes edit.py.")
    results = {}
    for video in ids:
        timeline_path = pdir / "edit" / video / "timeline.json"
        screen, mix = pdir / "edit" / video / "screen.mp4", pdir / "audio" / video / "mix.wav"
        for path in (timeline_path, screen, mix):
            if not path.exists():
                raise PipelineError(f"Falta {path.relative_to(pdir)}. Corré antes edit.py y mix.py.")
        timeline = read_json(timeline_path)
        timeline.setdefault("product", tut.get("product"))
        timeline.setdefault("title", tut.get("title"))
        results[video] = compose_video(timeline, screen, mix, brand, pdir / f"hf-{video}", brand["logo"])
    return results


def compose_fixture(video: str, out_root: Path) -> dict:
    """templates/fixtures/<video>.timeline.json + screen.mp4 -> <out_root>/hf-<video> (mix: quiet sine)."""
    timeline = read_json(FIXTURES / f"{video}.timeline.json")
    brand = read_json(FIXTURES / "brand.json")
    out_root.mkdir(parents=True, exist_ok=True)
    mix = out_root / f"{video}-mix.wav"
    ffmpeg("-f", "lavfi", "-i", f"sine=frequency=220:sample_rate=48000:duration={timeline['total']}",
           "-af", "volume=-30dB", "-ac", "2", str(mix))
    return compose_video(timeline, FIXTURES / "screen.mp4", mix, brand, out_root / f"hf-{video}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--fixture", choices=["tutorial", "redes"], help="compose a fixture of templates/fixtures")
    ap.add_argument("--out", type=Path, help="output folder for --fixture (outside the repository)")
    args = ap.parse_args()
    if args.fixture:
        if not args.out:
            raise PipelineError("--fixture necesita --out <carpeta>")
        compose_fixture(args.fixture, args.out)
    elif args.slug:
        compose(args.slug)
    else:
        ap.error("falta el slug (o --fixture)")


if __name__ == "__main__":
    main_guard(main)
