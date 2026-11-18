"""Stage: compose. Builds one HyperFrames project per video from the edit + mix artifacts.

Usage: python tools/compose.py <slug> [--video ID]
       python tools/compose.py --fixture tutorial|redes --out DIR   (templates/fixtures, for QA of compose)

For every video V of tutorial.yaml reads edit/V/timeline.json (v2), edit/V/screen.mp4 and
audio/V/mix.wav, and writes proyectos/<slug>/hf-V/ (index.html, assets/, meta.json,
hyperframes.json) plus hf-V/layout.json: every overlay, camera segment and mapped element rect in
output pixels, so qa.py checks the rules (reglas/reglas-video.md) without looking at pixels.

Rules applied here: C1 (detail 1.8-2.5x on every action, context <= 1.0 s), C2 (400-600 ms
ease-in-out pans, never fades), C3 (target framed >= 500 ms before the click), C5 (48 px cursor
whatever the zoom, halo on click), C7 (establishing shot of every new screen), C8 (one framing per
field, slow push-in on long holds), C9 (the field and its label always whole), C10 (hard cut when the
screen changes), N2/N7 (chip "Paso N" only in TUT; no paraphrase in the opening), N3/N9 (captions in a
fixed band outside the UI, one stable layout), N5 (brand palette only), N6/R2 (toast framed and clean),
O1-O3, R1-R3, T1-T3, E1, V1-V4.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import os
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

from common import (ROOT, PipelineError, ffmpeg, load_tutorial, main_guard, project_dir, read_json, run,
                    which, write_json)

TEMPLATE = ROOT / "templates" / "composition.html"
FIXTURES = ROOT / "templates" / "fixtures"
GSAP = ROOT / "node_modules" / "gsap" / "dist" / "gsap.min.js"
HYPERFRAMES = ROOT / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs"

SRC_W, SRC_H = 1920, 1080
NBSP = "\u00a0"
# N5: accent defaults to the primary and the caption band (surface) to the dark background of the app.
BRAND_DEFAULTS = {"primary": "#2563eb", "background": "#0f172a", "text": "#ffffff", "on_surface": "#ffffff",
                  "font": "Segoe UI"}

# Camera (C1-C3, C7-C10).
DETAIL_MIN, DETAIL_MAX, DETAIL_PREF = 1.8, 2.5, 2.2
CONTEXT_MAX = 1.0       # C1/C7: the establishing shot (full screen) lasts at most this long
ESTABLISH_MIN = 0.3     # shorter establishing shots are skipped: cut straight to the first target
ESTABLISH_WANT = 0.6    # a first target without pointer (toast, row) waits this long on the full screen
MOVE, MOVE_MIN, MOVE_MAX = 0.5, 0.4, 0.6   # C2: pans/zooms of 400-600 ms
LEAD = 0.5              # C3: target framed this long before the event
LEAD_BY_TYPE = {"type": 0.3, "select": 0.3}
EARLY = 0.5             # a pan may arrive this much before the lead when there is time
SEARCH_TOL = -4         # tight pans keep both targets at least 4 px inside the viewport
BOX_PAD = 16            # source px kept around a framed box
LABEL_PX = 32           # C9: label height above a field when the capture has no frame_box
BOXED = {"click", "hover", "type", "select", "focus", "result", "highlight"}
FIELD = {"type", "select"}                          # C9: always framed whole, label included
POINTER = {"click", "hover", "type", "select"}      # the cursor travels to these
HOLD = {"click": 0.3, "hover": 0.5, "type": 0.35, "select": 0.4, "focus": 0.8, "result": 1.0,
        "highlight": 1.5}
KEEP = {"click": 0.15, "hover": 0.3, "type": 0.0, "select": 0.2, "focus": 0.8, "result": 0.8,
        "highlight": 1.5}  # the target must stay whole in frame this long after its action ends
R2_CLEAN = 0.8          # R2: result visible without caption or cursor over it
HOLD_LIMIT = {"RED": 3.0}  # C8: identical framing at most 3 s in RED, 4 s otherwise
HOLD_LIMIT_DEFAULT = 4.0
PUSH = 0.1              # C8: slow push-in (scale +0.1 over a long hold)

# Overlays (O1-O3, T1-T2, C5, N3).
CURSOR_PX = 48
CURSOR_W = 36
CHAR_W = 0.58           # average advance of the bold sans, in em (conservative)
CAPTION_MIN = 1.2       # T1
RADIUS = 18
PAD_X, PAD_Y, CHIP_PAD_Y, MARGIN, BAND_PAD = 32, 14, 10, 24, 40

FORMATS = {
    # N3: the screen is drawn in the upper 1920x900 and a 180 px caption band sits below it.
    # The establishing shot fits the whole 1920x1080 screen in the viewport (0.83x).
    "16:9": {"size": (1920, 1080), "view_h": 900, "band_bottom": 1080, "fit": "contain", "font": 44,
             "chars": 42, "safe_top": 0, "safe_bottom": 1080, "card_font": 80, "card_pad": 160},
    # N3/N9/V1/V4: UI from the top through 71 % of the height (the source always covers it, no bars),
    # caption band right below it ending at the bottom 20 % unsafe area, brand background under it.
    "9:16": {"size": (1080, 1920), "view_h": 1365, "band_bottom": 1536, "fit": "cover", "font": 48,
             "chars": 28, "safe_top": 288, "safe_bottom": 1536, "card_font": 76, "card_pad": 130},
}
# Back-compat for readers that only need the output size per format.
LAYOUTS = {k: {"size": v["size"]} for k, v in FORMATS.items()}

STOPWORDS = {"el", "la", "los", "las", "un", "una", "unos", "unas", "lo", "al", "del", "de", "a", "en", "con",
             "por", "para", "sin", "sobre", "entre", "hacia", "hasta", "desde", "y", "e", "o", "u", "ni",
             "que", "pero", "si", "como"}
PARAPHRASE = 0.6        # N2: word overlap from which opening.text repeats the title
INF = float("inf")


def hf_env(extra: dict | None = None) -> dict:
    return {**os.environ, "HYPERFRAMES_NO_TELEMETRY": "1", "HYPERFRAMES_SKIP_SKILLS": "1", **(extra or {})}


def hyperframes(*args, quiet: bool = True, extra_env: dict | None = None, **kwargs):
    if not HYPERFRAMES.exists():
        raise PipelineError("Falta HyperFrames local. Corré: npm install (ver python tools/doctor.py)")
    return run([which("node"), HYPERFRAMES, *args], quiet=quiet, env=hf_env(extra_env), cwd=ROOT, **kwargs)


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


# --- palette (N5) -----------------------------------------------------------------------------

def norm(color: str) -> str:
    return _hex(_rgb(color))


def resolve_brand(brand: dict | None) -> dict:
    """Brand colors with the N5 defaults: accent = primary, surface = background, on_surface = white."""
    b = {**BRAND_DEFAULTS, **{k: v for k, v in (brand or {}).items() if v}}
    for key in ("primary", "background", "text", "on_surface"):
        b[key] = norm(b[key])
    b["accent"] = norm(b.get("accent") or b["primary"])
    surface = norm(b.get("surface") or b["background"])
    if surface == "#000000":
        # N5: no pure black boxes; tint it with the primary (same hue as the brand).
        surface = _hex(tuple(v * 0.16 for v in _rgb(b["primary"])))
    b["surface"] = surface
    return b


def palette_of(brand: dict | None) -> dict:
    """Every color compose may draw (layout.json `palette`); all derived from the brand (N5)."""
    b = resolve_brand(brand)
    return {"primary": b["primary"], "accent": b["accent"], "background": b["background"], "surface": b["surface"],
            "on_surface": readable(b["on_surface"], b["surface"], 4.5),
            "text": readable(b["text"], b["background"], 4.5),
            # O1: chip = the primary (darkened within its hue if needed) with white text >= 4.5:1.
            "chip": readable(b["primary"], "#ffffff", 4.5), "chip_text": "#ffffff",
            # R3: outline in the accent (= primary) with >= 3:1 against the light rows around it.
            "highlight": readable(b["accent"], "#ffffff", 3.0), "cursor": "#ffffff"}


def _content_words(text: str) -> set[str]:
    plain = "".join(c for c in unicodedata.normalize("NFD", (text or "").lower()) if not unicodedata.combining(c))
    return {w for w in re.findall(r"[a-z0-9]+", plain) if w not in STOPWORDS}


def paraphrase(text: str, title: str) -> bool:
    """N2: `text` says the same as `title` (content-word overlap >= 60 % of the shorter one)."""
    a, b = _content_words(text), _content_words(title)
    if not a or not b:
        return False
    return len(a & b) / min(len(a), len(b)) >= PARAPHRASE


# --- geometry ---------------------------------------------------------------------------------

def overlaps(a, b, pad: float = 0) -> bool:
    return (a[0] - pad < b[0] + b[2] and b[0] - pad < a[0] + a[2]
            and a[1] - pad < b[1] + b[3] and b[1] - pad < a[1] + a[3])


def rnd(rect) -> list[float]:
    return [round(v, 1) for v in rect]


def center(box: dict) -> tuple[float, float]:
    return box["x"] + box["w"] / 2, box["y"] + box["h"] / 2


def union(a: dict, b: dict) -> dict:
    x, y = min(a["x"], b["x"]), min(a["y"], b["y"])
    return {"x": x, "y": y, "w": max(a["x"] + a["w"], b["x"] + b["w"]) - x,
            "h": max(a["y"] + a["h"], b["y"] + b["h"]) - y}


def label_box(ev: dict) -> dict:
    """C9: the control plus its visible label (frame_box), or the box grown upward for older captures."""
    box = ev["box"]
    if ev.get("frame_box"):
        return union(ev["frame_box"], box)
    if ev["type"] in FIELD:
        top = max(0.0, box["y"] - LABEL_PX)
        return {"x": box["x"], "y": top, "w": box["w"], "h": box["y"] + box["h"] - top}
    return box


class Stage:
    """Output geometry of one format: UI viewport, caption band, safe area for the action, framings."""

    def __init__(self, fmt: str, chip_w: float = 0):
        if fmt not in FORMATS:
            raise PipelineError(f"timeline.json: formato desconocido '{fmt}' (usa 16:9 o 9:16)")
        self.fmt = fmt
        spec = FORMATS[fmt]
        self.spec = spec
        self.W, self.H = spec["size"]
        self.VH = spec["view_h"]
        self.view = [0, 0, self.W, self.VH]
        self.band = [0, self.VH, self.W, spec["band_bottom"] - self.VH]
        self.font = spec["font"]
        self.line_h = round(self.font * 1.25)
        self.chip_h = self.line_h + 2 * CHIP_PAD_Y
        # N3: chip at the left of the band, captions in the rest of it (same place in every step).
        self.chip_x = BAND_PAD
        self.cap_x = BAND_PAD + (chip_w + BAND_PAD if chip_w else 0)
        self.cap_w = self.W - BAND_PAD - self.cap_x
        self.chars = min(spec["chars"], int(self.cap_w / (CHAR_W * self.font)))
        top = spec["safe_top"] + MARGIN
        # V4: the action is framed inside this rect of the viewport (below the top 15 % in 9:16).
        self.safe = (MARGIN, top, self.W - 2 * MARGIN, self.VH - MARGIN - top)
        fits = (self.W / SRC_W, self.VH / SRC_H)
        self.base = min(fits) if spec["fit"] == "contain" else max(fits)
        self.detail_min = max(DETAIL_MIN, self.base)

    def cap_rect(self, lines: int) -> list[float]:
        bx, by, bw, bh = self.band
        h = lines * self.line_h
        return [self.cap_x, by + (bh - h) / 2, self.cap_w, h]

    def chip_rect(self, text: str) -> list[float]:
        bx, by, bw, bh = self.band
        return [self.chip_x, by + (bh - self.chip_h) / 2, text_width(text, self.font) + 2 * PAD_X, self.chip_h]

    def frame(self, cx: float, cy: float, s: float) -> dict:
        """Framing that centers (cx, cy) in the safe area; the source always covers the viewport (N9)."""
        s = round(s, 4)
        out = {}
        for axis, c, view, src, lo, length in (("x", cx, self.W, SRC_W, self.safe[0], self.safe[2]),
                                               ("y", cy, self.VH, SRC_H, self.safe[1], self.safe[3])):
            span = view - src * s
            pos = span / 2 if span >= 0 else min(max(lo + length / 2 - c * s, span), 0)
            out[axis] = round(pos, 1)
        out["s"] = s
        return out

    def context(self, point=None) -> dict:
        cx, cy = (point["x"], point["y"]) if point else (SRC_W / 2, SRC_H / 2)
        return self.frame(cx, cy, self.base)

    def focus_box(self, ev: dict) -> dict:
        """The part of the event box the camera frames: fields whole (C9), big boxes cropped to detail."""
        box = label_box(ev)
        if ev["type"] in FIELD or ev.get("frame_box"):
            return box
        sw, sh = self.safe[2], self.safe[3]
        max_w = sw / self.detail_min - 2 * BOX_PAD
        max_h = sh / self.detail_min - 2 * BOX_PAD
        if box["w"] <= max_w and box["h"] <= max_h:
            return box
        point = ev.get("point") or {"x": box["x"] + box["w"] / 2, "y": box["y"] + box["h"] / 2}
        w, h = min(box["w"], max_w), min(box["h"], max_h)
        # Text and rows are read from the left; a click target is framed around the pointer.
        x = box["x"] if ev["type"] in ("highlight", "result", "focus") else point["x"] - w / 2
        y = box["y"] if box["h"] <= max_h else point["y"] - h / 2
        x = min(max(x, box["x"]), box["x"] + box["w"] - w)
        y = min(max(y, box["y"]), box["y"] + box["h"] - h)
        return {"x": x, "y": y, "w": w, "h": h}

    def fit(self, box: dict) -> float:
        return min(self.safe[2] / (box["w"] + 2 * BOX_PAD), self.safe[3] / (box["h"] + 2 * BOX_PAD))

    def shot_frame(self, shot: dict) -> dict:
        box = shot["frame_box"]
        fit = self.fit(box)
        if shot["events"][0]["type"] == "result":
            s = max(min(self.detail_min, fit), self.base)     # N6: the toast with the UI around it
        elif shot["field"]:
            s = max(min(DETAIL_PREF, fit), self.base)          # C9 wins over C1 for very wide fields
        else:
            s = max(min(DETAIL_PREF, fit), self.detail_min)
        return self.frame(*center(box), s)

    def contains(self, fr: dict, box: dict) -> bool:
        return p_range(fr, fr, box, self.view) is not None

    def push(self, fr: dict, box: dict) -> dict | None:
        """C8: the framing at the end of a slow push-in on `box` (scale +0.1), keeping it whole."""
        for d in (PUSH, PUSH / 2, -PUSH):
            s = fr["s"] + d
            if not self.base <= s <= DETAIL_MAX + 1e-9:
                continue
            to = self.frame(*center(box), s)
            if self.contains(to, box) and to != fr:
                return to
        return None

    @staticmethod
    def map(box: dict, fr: dict) -> list[float]:
        return [box["x"] * fr["s"] + fr["x"], box["y"] * fr["s"] + fr["y"], box["w"] * fr["s"], box["h"] * fr["s"]]


# --- camera (C1-C3, C7-C10, R1) ---------------------------------------------------------------

def lead(ev: dict) -> float:
    return LEAD_BY_TYPE.get(ev["type"], LEAD)


def establish_room(kind: str | None) -> float:
    """C7/N6 contract with edit: output seconds a new screen needs before its first target of type `kind`
    so the establishing shot (ESTABLISH_WANT) and the zoom (MOVE) fit, plus the C3 lead of a pointer target.
    For a toast/row (`kind` not a pointer action) it is when the camera lands on it at the latest."""
    return ESTABLISH_WANT + MOVE + (LEAD_BY_TYPE.get(kind, LEAD) if kind in POINTER else 0.0)


def ease(p: float) -> float:
    """GSAP power2.inOut."""
    return 2 * p * p if p < 0.5 else 1 - (-2 * p + 2) ** 2 / 2


def inv_ease(e: float) -> float:
    e = min(max(e, 0.0), 1.0)
    return math.sqrt(e / 2) if e < 0.5 else 1 - math.sqrt(2 * (1 - e)) / 2


def p_range(f0: dict, f1: dict, box: dict, rect, tol: float = 0.5):
    """Progress interval [lo, hi] of a pan f0 -> f1 during which `box` is whole inside `rect`, or None.

    The mapped edges are linear in the (eased) progress, so each edge gives one bound."""
    rx, ry, rw, rh = rect

    def margins(fr):
        x, y, w, h = Stage.map(box, fr)
        return (x - rx, rx + rw - x - w, y - ry, ry + rh - y - h)

    lo, hi = 0.0, 1.0
    for a, b in zip(margins(f0), margins(f1)):
        if a >= -tol and b >= -tol:
            continue
        if a < -tol and b < -tol:
            return None
        p = (a + tol) / (a - b)
        if a < -tol:
            lo = max(lo, p)
        else:
            hi = min(hi, p)
    return (lo, hi) if lo <= hi else None


def screen_bounds(timeline: dict) -> list[float]:
    """Times where the screen changes (edit's screen_at, gotos): each starts a new screen (C7, C10)."""
    ss, se = timeline["screen_start"], timeline["screen_end"]
    times = set()
    for step in timeline["steps"]:
        for ev in step["events"]:
            at = ev.get("screen_at")
            if at is None and ev["type"] == "goto":
                at = ev["t"]
            if at is not None and ss + 1e-6 < at < se - 1e-6:
                times.add(round(at, 3))
    return sorted(times)


def shots_of(timeline: dict, stage: Stage) -> list[dict]:
    """One framing per boxed event (C8: field by field); events on the same element share it."""
    bounds = screen_bounds(timeline)
    shots: list[dict] = []
    for step in timeline["steps"]:
        for ev in sorted((e for e in step["events"] if e["type"] in BOXED and e.get("box")), key=lambda e: e["t"]):
            period = sum(1 for b in bounds if b < ev["t"] - 1e-6)
            fbox = stage.focus_box(ev)
            end = ev.get("t_end") or ev["t"]
            last = shots[-1] if shots else None
            if (last and last["period"] == period and ev.get("selector") and ev["selector"] == last["selector"]
                    and same_box(ev["box"], last["events"][-1]["box"])
                    and ev["type"] not in ("result", "highlight")
                    and last["events"][-1]["type"] not in ("result", "highlight")):
                last["box"] = union(last["box"], fbox)
                last["events"].append(ev)
                last["field"] = last["field"] or ev["type"] in FIELD or bool(ev.get("frame_box"))
                last["end"] = max(last["end"], end)
                continue
            shots.append({"step": step["id"], "period": period, "events": [ev], "selector": ev.get("selector"),
                          "box": fbox, "field": ev["type"] in FIELD or bool(ev.get("frame_box")),
                          "t": ev["t"], "lead": lead(ev), "pointer": ev["type"] in POINTER, "end": end,
                          "point": ev.get("point") or dict(zip("xy", center(fbox)))})
    prev = None
    for shot in shots:
        shot["frame_box"] = shot["box"]
        # Two fields typed back to back with no time for a 400 ms pan: the next framing also keeps the
        # previous field whole when both fit at detail scale, so neither is cut while typing (C9).
        if (prev and prev["period"] == shot["period"] and prev["field"] and shot["field"] and shot["pointer"]
                and shot["t"] - prev["end"] < MOVE + shot["lead"]):
            both = union(prev["box"], shot["box"])
            if stage.fit(both) >= stage.detail_min:
                shot["frame_box"] = both
        shot["frame"] = stage.shot_frame(shot)
        prev = shot
    return shots


def same_box(a: dict, b: dict, tol: float = 6) -> bool:
    return all(abs(a[k] - b[k]) <= tol for k in ("x", "y", "w", "h"))


def _keep(shot: dict, table: dict) -> float:
    """Until when the shot's target must stay framed (pointer actions: after the action ends; toasts,
    rows and texts: after the camera reached them, R2)."""
    last = shot["events"][-1]
    if last["type"] in POINTER:
        return shot["end"] + table[last["type"]]
    return max(shot["arrive"], last["t"]) + table[last["type"]]


def transition(a: dict, b: dict, free: float, stage: Stage, origin: dict | None = None) -> tuple[float, float]:
    """(start, duration) of the pan from shot a (framed as `origin`) to shot b on one screen (C2, C3, C9)."""
    origin = origin or a["frame"]
    soft = max(free, _keep(a, HOLD))
    target = b["t"] - b["lead"]
    if not b["pointer"]:
        return max(soft, target - MOVE), MOVE          # a toast/row/text: it may be framed a bit late
    if target - soft >= MOVE:
        return max(soft, target - MOVE - EARLY), MOVE
    if target - soft >= MOVE_MIN:
        return soft, target - soft
    # No room: the pan that keeps a whole until its action ends and b whole when its action starts.
    hard = _keep(a, KEEP)
    best = None
    t = free
    while t <= b["t"] + 1e-9:
        for d in (MOVE_MIN, MOVE, MOVE_MAX):
            ra = p_range(origin, b["frame"], a["box"], stage.view, SEARCH_TOL)
            rb = p_range(origin, b["frame"], b["box"], stage.view, SEARCH_TOL)
            leave = t if not ra or ra[0] > 0 else (INF if ra[1] >= 1 else t + d * inv_ease(ra[1]))
            enter = t + d if not rb or rb[1] < 1 else t + d * inv_ease(rb[0])
            key = (round(max(0, hard - leave) + max(0, enter - b["t"]), 3), round(max(0, enter - target), 3), -t)
            if best is None or key < best[0]:
                best = (key, t, d)
        t += 0.01
    return best[1], best[2]


def camera_shots(timeline: dict, stage: Stage) -> tuple[list[dict], list[dict]]:
    """Contiguous camera segments over [screen_start, screen_end] and the shots with their arrival time."""
    ss, se = timeline["screen_start"], timeline["screen_end"]
    shots = shots_of(timeline, stage)
    starts = [ss] + screen_bounds(timeline)
    limit = HOLD_LIMIT.get(timeline.get("type", "TUT"), HOLD_LIMIT_DEFAULT)
    segs: list[dict] = []

    def add(kind, t0, t1, frm, to, **extra):
        t1 = min(t1, se)
        if t1 - t0 <= 1e-6:
            return
        last = segs[-1] if segs else None
        if (kind != "move" and last and last["kind"] == kind and last["to"] == to and last["from"] == to
                and abs(last["t1"] - t0) < 1e-6):
            last["t1"] = t1
            return
        segs.append({"t0": t0, "t1": t1, "kind": kind, "from": frm, "to": to, **extra})

    for k, a in enumerate(starts):
        b = starts[k + 1] if k + 1 < len(starts) else se
        group = [s for s in shots if s["period"] == k]
        if not group:
            ctx = stage.context()
            add("context", a, b, ctx, ctx, reason="establishing")
            continue
        first = group[0]
        need = first["t"] - first["lead"]
        if not first["pointer"]:
            need = max(need, a + ESTABLISH_WANT + MOVE)
        est = min(a + CONTEXT_MAX, need - MOVE)
        if est - a >= ESTABLISH_MIN - 1e-9:
            # C7: the whole new screen first, then an ease-in-out zoom to the first target.
            ctx = stage.context(first["point"])
            add("context", a, est, ctx, ctx, reason="establishing")
            add("move", est, min(est + MOVE, b), ctx, first["frame"])
            first["arrive"] = est + MOVE
        else:
            first["arrive"] = a       # C10: hard cut straight to the first target of the new screen
        free = first["arrive"]
        for prev, shot in zip(group, group[1:]):
            if shot["frame"] == prev["frame"]:
                shot["arrive"] = free        # already framed (e.g. 9:16 fields of one row): no pan
                continue
            start, dur = transition(prev, shot, free, stage)
            end = prev["frame"]
            if start - free > limit + 1e-6:
                # C8: a long hold becomes a slow push-in; the pan then leaves from the pushed framing.
                end = stage.push(prev["frame"], prev["frame_box"]) or end
                start, dur = transition(prev, shot, free, stage, end)
            start = min(start, b)
            add("detail", free, start, prev["frame"], end, box=prev["frame_box"])
            add("move", start, min(start + dur, b), end, shot["frame"])
            shot["arrive"] = start + dur
            free = max(free, min(start + dur, b))
        last = group[-1]
        end = (stage.push(last["frame"], last["frame_box"]) or last["frame"]) if b - free > limit + 1e-6 else last["frame"]
        add("detail", free, b, last["frame"], end, box=last["frame_box"])
    return finish(segs), shots


def camera_plan(timeline: dict, stage: Stage) -> list[dict]:
    return camera_shots(timeline, stage)[0]


def finish(segs: list[dict]) -> list[dict]:
    out = []
    for seg in segs:
        if seg["t1"] - seg["t0"] <= 1e-6:
            continue
        to = seg["to"]
        item = {"t0": round(seg["t0"], 3), "t1": round(seg["t1"], 3), "scale": to["s"], "kind": seg["kind"],
                "x": to["x"], "y": to["y"]}
        if seg.get("reason"):
            item["reason"] = seg["reason"]
        if seg["kind"] == "move":
            item["from"] = dict(seg["from"])
        elif seg["from"] != to:
            item.update({"from": dict(seg["from"]), "push": True})   # C8: slow push-in, linear
        out.append(item)
    for a, b in zip(out, out[1:]):
        b["t0"] = a["t1"]
        if b["kind"] == "move":
            b["from"] = {"x": a["x"], "y": a["y"], "s": a["scale"]}
    return out


def framed_span(camera: list[dict], arrive: float) -> tuple[float, float, float]:
    """(move-in start, rest end, move-out end) of the framing the camera reaches at `arrive`: the rest ends
    where the next move (or another framing, a cut) starts."""
    k = next((i for i, s in enumerate(camera) if s["t0"] - 1e-6 <= arrive < s["t1"] - 1e-6), len(camera) - 1)
    move_in = arrive
    if k > 0 and camera[k - 1]["kind"] == "move" and abs(camera[k - 1]["t1"] - arrive) < 1e-3:
        move_in = camera[k - 1]["t0"]
    rest = camera[k]
    for seg in camera[k + 1:]:
        if seg["kind"] == "move":
            return move_in, seg["t0"], seg["t1"]
        if (seg["x"], seg["y"], seg["scale"]) != (rest["x"], rest["y"], rest["scale"]):
            return move_in, seg["t0"], seg["t0"]
    return move_in, camera[-1]["t1"], camera[-1]["t1"]


def frame_at(camera: list[dict], t: float) -> dict:
    seg = next((s for s in camera if s["t0"] <= t < s["t1"]), camera[-1] if t >= camera[-1]["t1"] else camera[0])
    to = {"x": seg["x"], "y": seg["y"], "s": seg["scale"]}
    if not seg.get("from"):
        return to
    p = min(max((t - seg["t0"]) / (seg["t1"] - seg["t0"]), 0), 1)
    p = ease(p) if seg["kind"] == "move" else p
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
             blocked: list[tuple[float, float]] = ()) -> list[tuple[float, float, list[str]]]:
    """T1/N1: captions follow the voice in time order inside the step, >= 1.2 s each."""
    if not caps:
        return []
    free = subtract([(max(v0, s0), s1)], list(blocked))
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
    """N2/N7/PRO4: only TUT shows a chip, "Paso N" ("Parte N · Paso M" with chapters, E3)."""
    if timeline.get("type", "TUT") != "TUT":
        return None
    number = step.get("number") or (timeline["steps"].index(step) + 1)
    if step.get("chapter"):
        same = [s for s in timeline["steps"] if s.get("chapter") == step["chapter"]]
        return f"Parte {step['chapter']} · Paso {same.index(step) + 1}"
    return f"Paso {number}"


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
    pal = palette_of(brand)
    style = f"bold|{pal['surface']}|{pal['on_surface']}|r{RADIUS}"   # O3: chip and captions share it
    labels = {s["id"]: step_label(timeline, s) for s in timeline["steps"]}
    font = FORMATS.get(fmt, FORMATS["16:9"])["font"]
    chip_w = max((text_width(label, font) + 2 * PAD_X for label in labels.values() if label), default=0)
    stage = Stage(fmt, chip_w)
    camera, shots = camera_shots(timeline, stage)
    arrival = {id(ev): shot["arrive"] for shot in shots for ev in shot["events"]}
    ss, se = timeline["screen_start"], timeline["screen_end"]
    items: list[dict] = [{"kind": "band", "t0": round(ss, 3), "t1": round(se, 3), "rect": rnd(stage.band),
                          "color": pal["surface"]}]
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
            at = max(ev["t"], arrival.get(id(ev), ev["t"])) if ev["type"] == "result" else ev["t"]
            fr = frame_at(camera, at)
            rect = rnd(stage.map(fbox, fr))
            base = {"t": round(ev["t"], 3), "step": step["id"], "event": ev["type"],
                    "selector": ev.get("selector", ""), "rect": rect, "full_rect": rnd(stage.map(ev["box"], fr)),
                    "frame_rect": rnd(stage.map(label_box(ev), fr))}
            if ev["type"] == "result":
                # N6/R2: framed from the moment the camera rests on the toast until it leaves, and never past
                # edit's hold (t_end: the toast is surely on screen); C4 exempts the zoom in and out too.
                move_in, rest_end, move_out = framed_span(camera, arrival.get(id(ev), ev["t"]))
                t1 = max(at, min(rest_end, ev.get("t_end") or rest_end))
                items.append({"kind": "result", "t0": round(at, 3), "t1": round(t1, 3), **base,
                              "exempt": [round(min(move_in, at), 3), round(max(move_out, t1), 3)]})
            elif ev["type"] == "highlight":
                t1 = min(max(ends[step["id"]], ev["t"] + HOLD["highlight"]), se)
                items.append({"kind": "highlight", "t0": round(ev["t"], 3), "t1": round(t1, 3), **base,
                              "color": pal["highlight"], "contrast": round(contrast(pal["highlight"], "#ffffff"), 2)})
            else:
                t0 = max(ev["t"] - lead(ev), ss)
                t1 = (ev.get("t_end") or ev["t"]) + HOLD[ev["type"]]
                start = rnd(stage.map(fbox, frame_at(camera, t0)))
                items.append({"kind": "active", "t0": round(t0, 3), "t1": round(t1, 3), **base, "rect_start": start})

    # Cursor (C5): samples at each pointer event; hidden while a toast is on screen (R2, N6).
    hidden: list[tuple[float, float]] = []
    for item in [i for i in items if i["kind"] == "result"]:
        nxt = next((e["t"] for e in pointer_events if e["t"] > item["t0"]), se)
        hidden.append((item["t0"] - 0.1, max(item["t1"], min(nxt - 0.6, se))))
    for ev in pointer_events:
        if any(a <= ev["t"] < b for a, b in hidden):
            continue
        fr = frame_at(camera, ev["t"])
        p = ev["point"]
        items.append({"kind": "cursor", "t0": round(ev["t"], 3), "t1": round(ev["t"], 3), "event": ev["type"],
                      "rect": rnd([p["x"] * fr["s"] + fr["x"], p["y"] * fr["s"] + fr["y"], CURSOR_W, CURSOR_PX]),
                      "color": pal["cursor"]})

    # Chip + captions in the band outside the UI (N3): nothing to dodge, one style (O1-O3).
    for step in timeline["steps"]:
        s0, s1 = step["start"], step["start"] + step["duration"]
        label = labels[step["id"]]
        if label:
            items.append({"kind": "chip", "t0": round(s0, 3), "t1": round(s1, 3), "rect": rnd(stage.chip_rect(label)),
                          "text": label, "step": step["id"], "style": style, "opacity": 1,
                          "color": pal["chip"], "text_color": pal["chip_text"],
                          "contrast": round(contrast(pal["chip_text"], pal["chip"]), 2), "font_px": stage.font})
        caps = segment_captions(step.get("narration") or "", product, stage.chars)
        for t0, t1, lines in schedule(caps, step.get("voice_start", s0), step.get("voice_duration", 0), s0, s1):
            items.append({"kind": "caption", "t0": round(t0, 3), "t1": round(t1, 3), "rect": rnd(stage.cap_rect(len(lines))),
                          "text": " ".join(lines), "lines": lines, "step": step["id"], "style": style,
                          "color": pal["on_surface"], "background": pal["surface"], "font_px": stage.font})

    items.extend(plan_cards(timeline, stage, product, kind, pal))
    items.sort(key=lambda i: (i["t0"], i["kind"]))
    return {"video": timeline.get("video"), "type": kind, "format": fmt, "total": timeline["total"],
            "output": [stage.W, stage.H], "viewport": stage.view, "band": rnd(stage.band),
            "base_scale": round(stage.base, 4),
            "safe": {"top": stage.spec["safe_top"], "bottom": stage.spec["safe_bottom"], "action": rnd(stage.safe)},
            "cursor_px": CURSOR_PX, "font_px": stage.font, "screen": [ss, se], "palette": pal,
            "camera": camera, "cursor_hidden": [[round(a, 3), round(b, 3)] for a, b in hidden], "items": items}


def plan_cards(timeline: dict, stage: Stage, product: str | None, kind: str, pal: dict) -> list[dict]:
    """E1 cards. N2: the TUT opening shows the title, plus opening.text only when it adds something."""
    spec = stage.spec
    width = stage.W - 2 * spec["card_pad"]
    mid = (spec["safe_top"] + spec["safe_bottom"]) / 2
    out = []
    parts = [("opening", timeline.get("opening")), ("requirements", timeline.get("requirements")),
             ("closing", timeline.get("closing"))]
    for name, card in parts:
        if not card:
            continue
        text, title = card.get("text"), timeline.get("title")
        blocks = []
        if name == "opening" and (kind == "TUT" or not text) and title:
            tlines, tfont = card_lines(title, product, width, spec["card_font"])
            blocks.append(("title", tlines, tfont, round(tfont * 1.15)))
            if text and kind == "TUT" and not paraphrase(text, title):
                lines, font = card_lines(text, product, width, round(spec["card_font"] * 0.55), 2)
                blocks.append(("card", lines, font, round(font * 1.25)))
        elif text:
            lines, font = card_lines(text, product, width, spec["card_font"])
            blocks.append(("card", lines, font, round(font * 1.15)))
        if not blocks:
            continue
        gap = 40
        height = sum(len(b[1]) * b[3] for b in blocks) + gap * (len(blocks) - 1)
        y = mid - height / 2
        t0 = card.get("start", 0)
        t1 = timeline["total"] if name == "closing" else t0 + card["duration"]
        for kind_, blines, bfont, bline_h in blocks:
            w = min(width, max(text_width(line, bfont) for line in blines))
            h = len(blines) * bline_h
            out.append({"kind": kind_, "t0": round(t0, 3),
                        "t1": round(min(t1, t0 + 3.0) if kind_ == "title" else t1, 3),
                        "rect": rnd([(stage.W - w) / 2, y, w, h]), "text": " ".join(blines), "lines": blines,
                        "card": name, "font": round(bfont, 1), "line_h": bline_h, "color": pal["text"]})
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


def cam_vars(fr: dict) -> str:
    return f'"--cx": {num(fr["x"])}, "--cy": {num(fr["y"])}, "--s": {num(fr["s"])}'


def build(timeline: dict, brand: dict, logo_src: str | None = None) -> tuple[str, dict]:
    """(index.html, layout) for one video."""
    layout = plan(timeline, brand)
    pal = layout["palette"]
    b = resolve_brand(brand)
    W, H = layout["output"]
    ss, se, total = timeline["screen_start"], timeline["screen_end"], timeline["total"]
    items = layout["items"]
    script: list[str] = []

    # Camera: CSS variables so the cursor can divide by the same scale every frame (C5). A framing that
    # does not continue the previous one is a cut (C10); moves ease in-out (C2), push-ins are linear (C8).
    prev = None
    for seg in layout["camera"]:
        end = {"x": seg["x"], "y": seg["y"], "s": seg["scale"]}
        start = seg.get("from") or end
        if prev is None or prev != start:
            script.append(f'tl.set("#cam", {{{cam_vars(start)}}}, {num(seg["t0"] if prev else 0)});')
        if seg.get("from"):
            curve = "power2.inOut" if seg["kind"] == "move" else "none"
            script.append(f'tl.to("#cam", {{{cam_vars(end)}, duration: {num(seg["t1"] - seg["t0"])}, '
                          f'ease: "{curve}"}}, {num(seg["t0"])});')
        prev = end

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
        for a, b_ in layout["cursor_hidden"]:
            script.append(f'tl.set("#cursor", {{opacity: 0}}, {num(a)});')
            script.append(f'tl.set("#cursor", {{opacity: 1}}, {num(b_)});')
    else:
        script.append('tl.set("#cursor", {opacity: 0}, 0);')

    # Highlights (R3): brand outline at 100 % plus a pulsing glow, inside the camera (N5).
    hl_markup = []
    for i, item in enumerate(i for i in items if i["kind"] == "highlight"):
        ev = next(e for s in timeline["steps"] for e in s["events"]
                  if e["type"] == "highlight" and round(e["t"], 3) == item["t0"])
        bx = ev["box"]
        hid = f"hl-{i}"
        hl_markup.append(f'          <div class="hl" id="{hid}" style="{box_style([bx["x"] - 6, bx["y"] - 4, bx["w"] + 12, bx["h"] + 8])}; '
                         f'--hl: {item["color"]}"><div class="hl-glow" id="{hid}-glow"></div></div>')
        script.append(f'tl.set("#{hid}", {{opacity: 1}}, {num(item["t0"])});')
        for k in range(2):
            t = item["t0"] + k * 0.7
            script.append(f'tl.to("#{hid}-glow", {{opacity: 0.85, duration: 0.3, ease: "sine.inOut"}}, {num(t)});')
            script.append(f'tl.to("#{hid}-glow", {{opacity: 0.25, duration: 0.4, ease: "sine.inOut"}}, {num(t + 0.3)});')
        script.append(f'tl.set("#{hid}", {{opacity: 0}}, {num(item["t1"])});')

    # Chip + captions: absolute rects in the band; they appear at 100 % opacity at once (O1).
    overlays = []
    for i, item in enumerate(i for i in items if i["kind"] == "chip"):
        overlays.append(f'      <div id="chip-{i}" class="clip ov-layer" data-start="{num(item["t0"])}" '
                        f'data-duration="{num(item["t1"] - item["t0"])}"><div class="ov chip" '
                        f'style="{box_style(item["rect"])}">{esc(item["text"])}</div></div>')
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
        "WIDTH": W, "HEIGHT": H, "VIEW_H": layout["viewport"][3], "ORIENTATION": "portrait" if H > W else "landscape",
        "PRIMARY": pal["primary"], "ACCENT": pal["accent"], "BACKGROUND": pal["background"], "TEXT": pal["text"],
        "SURFACE": pal["surface"], "ON_SURFACE": pal["on_surface"], "CHIP_BG": pal["chip"],
        "CHIP_FG": pal["chip_text"], "BAND": box_style(layout["band"]),
        "FONT": f'"{b["font"]}", "Segoe UI", Arial, sans-serif',
        "FONT_PX": layout["font_px"], "LINE_H": round(layout["font_px"] * 1.25), "PAD_X": PAD_X,
        "CHIP_PAD_Y": CHIP_PAD_Y, "RADIUS": RADIUS, "CURSOR_PX": CURSOR_PX, "CURSOR_W": CURSOR_W,
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


def compose(slug: str, video: str | None = None) -> dict:
    tut = load_tutorial(slug)
    pdir = project_dir(slug)
    brand = brand_of(tut, pdir)
    ids = video_ids(tut, pdir)
    if not ids:
        raise PipelineError("No hay videos en tutorial.yaml ni cortes en edit/. Corré antes edit.py.")
    if video:
        if video not in ids:
            raise PipelineError(f"No existe el video '{video}' (videos: {', '.join(ids)})")
        ids = [video]
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
    ap.add_argument("--video", help="id del video (por defecto: todos)")
    args = ap.parse_args()
    if args.fixture:
        if not args.out:
            raise PipelineError("--fixture necesita --out <carpeta>")
        compose_fixture(args.fixture, args.out)
    elif args.slug:
        compose(args.slug, args.video)
    else:
        ap.error("falta el slug (o --fixture)")


if __name__ == "__main__":
    main_guard(main)
