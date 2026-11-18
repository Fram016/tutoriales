"""Stage: compose. Builds one HyperFrames project per video from the edit + mix artifacts.

Usage: python tools/compose.py <slug> [--video ID]
       python tools/compose.py --fixture tutorial|redes --out DIR   (templates/fixtures, for QA of compose)

For every video V of tutorial.yaml reads edit/V/timeline.json (v2), edit/V/screen.mp4 and
audio/V/mix.wav, and writes proyectos/<slug>/hf-V/ (index.html, assets/, meta.json,
hyperframes.json) plus hf-V/layout.json: every overlay, camera segment and mapped element rect in
output pixels, so qa.py checks the rules (reglas/reglas-video.md) without looking at pixels.

Rules applied here: C1 (detail 1.4-1.8x on buttons, toasts and rows, context <= 1.0 s), C2 (400-600 ms
ease-in-out pans, never fades), C3 (target framed >= 500 ms before the click), C5 (48 px cursor
whatever the zoom, halo on click), C7 (establishing shot of every new screen), C8 (no framing frozen
longer than the limit: spotlight moves or a slow push-in), C9 (the field and its label always whole),
C10 (hard cut when the screen changes; straight to the toast when the new screen opens on one, S1a),
N10 (one framing for the whole form, 1.0 (base in 9:16) to 1.5x, split top to bottom when it does not
fit), N11 (brand outline + soft dim on the active field, 250-400 ms moves), N12 (9:16: the form across
the whole width), N2/N7 (chip "Paso N" only in TUT; no paraphrase in the opening), N3/N9 (captions in a
fixed band outside the UI, one stable layout), N5 (brand palette only), N6/R2 (toast framed and clean),
O1-O3, R1-R3, T1-T3, E1, V1-V4.

Surfaces (perseo-xml S5, timeline `surfaces`): an extension popup is drawn as the browser shows it, a white
card under a toolbar strip with the extension icon, anchored top-right of the screen and only while open.
Its events are moved into source px first (with_surfaces): `open` becomes a click on the icon, and the
panel plus the strip is the form box of its actions, so camera (N10), cursor and spotlight (N11) follow.
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
DETAIL_MIN, DETAIL_MAX, DETAIL_PREF = 1.4, 1.8, 1.6     # C1 revised (§Parte 5)
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
DRIFT = 8               # C8: output px of slow drift when no push-in keeps the target whole

# Form shot (N10-N12).
FORM_MIN, FORM_PREF = 1.0, 1.5   # N10: never below 1.0x (base in 9:16), at most 1.5x (C1 max 1.8x)
FORM_PAD = 24           # source px around the fields when the capture has no form_box
FORM_EDGE = 16          # N12: output px between the form and the viewport edges in width-fit
FIELD_EDGE = 8          # V2: every field of a form framing stays this far inside the viewport
FORM_EVENTS = {"click", "hover", "type", "select", "focus"}
SPOT_MOVE, SPOT_MIN, SPOT_MAX = 0.3, 0.25, 0.4   # N11: spotlight moves of 250-400 ms
SPOT_LEAD = 0.3         # the spotlight reaches the next field this long before the action
SPOT_DIM = 0.22         # N11: dim of the rest of the frame (<= 25 %)
SPOT_FADE = 0.3

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

# Surfaces (S5), in source px (common.SURFACE_EDGE/SURFACE_TOP leave room for them).
SURFACE_EDGE = 16       # from the side of the screen
TOOLBAR_Y, TOOLBAR_W, TOOLBAR_H = 8, 56, 40
ICON_PX = 28
PANEL_GAP = 6           # between the strip and the panel
TOOLBAR_LEAD = 1.2      # the strip is there before the cursor travels to the icon (it leaves 0.8 s before)
TOOLBAR_TAIL = 0.3


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


def union_all(boxes: list[dict]) -> dict:
    out = boxes[0]
    for box in boxes[1:]:
        out = union(out, box)
    return out


def pad_box(box: dict, pad: float) -> dict:
    """`box` grown by `pad` source px on every side, clamped to the source."""
    x, y = max(0.0, box["x"] - pad), max(0.0, box["y"] - pad)
    return {k: round(v, 1) for k, v in {"x": x, "y": y, "w": min(SRC_W, box["x"] + box["w"] + pad) - x,
                                        "h": min(SRC_H, box["y"] + box["h"] + pad) - y}.items()}


def label_box(ev: dict) -> dict:
    """C9: the control plus its visible label (frame_box), or the box grown upward for older captures."""
    box = ev["box"]
    if ev.get("frame_box"):
        return union(ev["frame_box"], box)
    if ev["type"] in FIELD:
        top = max(0.0, box["y"] - LABEL_PX)
        return {"x": box["x"], "y": top, "w": box["w"], "h": box["y"] + box["h"] - top}
    return box


# --- surfaces (perseo-xml S5) ------------------------------------------------------------------

def surface_geometry(spec: dict) -> dict:
    """Source boxes of a surface: toolbar strip, extension icon, panel (1 surface CSS px = 1 source px, like
    the real popup) and `area` = strip + panel (the form box of its actions)."""
    w, h = spec["size"]
    right = spec.get("anchor", "top-right") == "top-right"
    tx = SRC_W - SURFACE_EDGE - TOOLBAR_W if right else SURFACE_EDGE
    toolbar = {"x": tx, "y": TOOLBAR_Y, "w": TOOLBAR_W, "h": TOOLBAR_H}
    icon = {"x": tx + (TOOLBAR_W - ICON_PX) // 2, "y": TOOLBAR_Y + (TOOLBAR_H - ICON_PX) // 2, "w": ICON_PX, "h": ICON_PX}
    panel = {"x": SRC_W - SURFACE_EDGE - w if right else SURFACE_EDGE, "y": TOOLBAR_Y + TOOLBAR_H + PANEL_GAP,
             "w": w, "h": h}
    return {"toolbar": toolbar, "icon": icon, "panel": panel, "area": union(toolbar, panel)}


def _clip(box: dict, to: dict) -> dict:
    x0, y0 = max(box["x"], to["x"]), max(box["y"], to["y"])
    x1 = min(box["x"] + box["w"], to["x"] + to["w"])
    y1 = min(box["y"] + box["h"], to["y"] + to["h"])
    return {"x": x0, "y": y0, "w": max(0, x1 - x0), "h": max(0, y1 - y0)}


def with_surfaces(timeline: dict) -> dict:
    """The timeline with surface events in source px: boxes and points moved onto the panel (clipped to it),
    `open` as a click on the toolbar icon, and the strip + panel as the form box of every action there."""
    specs = timeline.get("surfaces") or {}
    if not specs or timeline.get("surfaces_placed"):
        return timeline
    geo = {name: surface_geometry(spec) for name, spec in specs.items()}
    steps = []
    for step in timeline["steps"]:
        events = []
        for ev in step["events"]:
            g = geo.get(ev.get("surface"))
            if g is None or ev["type"] == "close":
                events.append(ev)
                continue
            if ev["type"] == "open":
                icon = g["icon"]
                events.append({**ev, "type": "click", "opens": True, "selector": f"{ev['surface']}:icon",
                               "box": dict(icon), "point": dict(zip("xy", center(icon))), "frame_box": dict(icon),
                               "form_box": dict(g["area"])})
                continue
            panel = g["panel"]
            moved = dict(ev)
            for key in ("box", "frame_box"):
                if ev.get(key):
                    moved[key] = _clip({**ev[key], "x": ev[key]["x"] + panel["x"], "y": ev[key]["y"] + panel["y"]}, panel)
            if ev.get("point"):
                moved["point"] = {"x": ev["point"]["x"] + panel["x"], "y": ev["point"]["y"] + panel["y"]}
            moved.pop("form_box", None)
            if ev["type"] in FORM_EVENTS:
                moved["form_box"] = dict(g["area"])
            events.append(moved)
        steps.append({**step, "events": events})
    return {**timeline, "steps": steps, "surfaces_placed": True}


def plan_surfaces(timeline: dict, camera: list[dict], stage: "Stage") -> list[dict]:
    """`surface` items (the panel, only while open) and `toolbar` items (the strip, from before the icon click
    until just after closing), with their source box and output rect when they appear."""
    ss, se = timeline["screen_start"], timeline["screen_end"]
    out = []
    for name, spec in (timeline.get("surfaces") or {}).items():
        g = surface_geometry(spec)
        bars: list[list[float]] = []
        for t0, t1 in spec.get("windows") or []:
            out.append({"kind": "surface", "name": name, "t0": round(t0, 3), "t1": round(t1, 3), "box": dict(g["panel"]),
                        "rect": rnd(stage.map(g["panel"], frame_at(camera, t0)))})
            a, b = max(ss, t0 - TOOLBAR_LEAD), min(se, t1 + TOOLBAR_TAIL)
            if bars and a <= bars[-1][1]:
                bars[-1][1] = max(bars[-1][1], b)
            else:
                bars.append([a, b])
        for a, b in bars:
            out.append({"kind": "toolbar", "name": name, "t0": round(a, 3), "t1": round(b, 3), "box": dict(g["toolbar"]),
                        "rect": rnd(stage.map(g["toolbar"], frame_at(camera, a)))})
    return out


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
        self.form_min = max(FORM_MIN, self.base)

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

    def form_scale(self, box: dict) -> float:
        """N10/N12: the form fitted to the viewport, between form_min and FORM_PREF. In 9:16 the width is
        fitted edge to edge (N12: whole form across the width rather than detail)."""
        if self.fmt == "9:16":
            fit_w = (self.W - 2 * FORM_EDGE) / box["w"]
        else:
            fit_w = self.safe[2] / (box["w"] + 2 * BOX_PAD)
        fit = min(fit_w, self.safe[3] / (box["h"] + 2 * BOX_PAD))
        return max(min(fit, FORM_PREF), self.form_min)

    def holds(self, fr: dict, boxes: list[dict]) -> bool:
        """V2/C9: every box whole and FIELD_EDGE px inside the viewport."""
        vx, vy, vw, vh = self.view
        for box in boxes:
            x, y, w, h = self.map(box, fr)
            if x < vx + FIELD_EDGE - 0.5 or x + w > vx + vw - FIELD_EDGE + 0.5 or y < vy - 0.5 or y + h > vy + vh + 0.5:
                return False
        return True

    def form_frame(self, form: dict, boxes: list[dict]) -> dict | None:
        """N10: framing of the whole form that keeps every field in `boxes` whole, or None when it does not
        fit at the minimum legible scale (then the form is split)."""
        fr = self.frame(*center(form), self.form_scale(form))
        if self.holds(fr, boxes):
            return fr
        fields = pad_box(union_all(boxes), FORM_PAD)
        fr = self.frame(*center(fields), self.form_scale(fields))
        return fr if self.holds(fr, boxes) else None

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

    def push(self, fr: dict, box: dict, boxes: list[dict] | None = None) -> dict | None:
        """C8: the framing at the end of a slow push-in on `box` (scale +0.1), keeping it (and `boxes`)
        whole; when no scale does, a slow drift of DRIFT px at the same scale (source still covering)."""
        whole = (lambda to: self.holds(to, boxes)) if boxes else (lambda to: self.contains(to, box))
        boxes = boxes or [box]
        for d in (PUSH, PUSH / 2, -PUSH):
            s = fr["s"] + d
            if not self.base <= s <= DETAIL_MAX + 1e-9:
                continue
            to = self.frame(*center(box), s)
            if to != fr and whole(to):
                return to
        for axis, d in (("x", DRIFT), ("x", -DRIFT), ("y", DRIFT), ("y", -DRIFT)):
            to = {**fr, axis: round(fr[axis] + d, 1)}
            view, src = (self.W, SRC_W) if axis == "x" else (self.VH, SRC_H)
            if view - src * fr["s"] >= 0 or not view - src * fr["s"] <= to[axis] <= 0:
                continue
            if whole(to):
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


def form_boxes(timeline: dict) -> dict[int, dict]:
    """N10: id(event) -> box of the form the action happens in: the captured form_box, or (older captures)
    the union of a step's consecutive type/select frame boxes padded by FORM_PAD when there are >= 2."""
    out: dict[int, dict] = {}
    for step in timeline["steps"]:
        run: list[dict] = []

        def close():
            if len(run) >= 2:
                box = pad_box(union_all([label_box(e) for e in run]), FORM_PAD)
                out.update({id(e): box for e in run})
            run.clear()

        for ev in sorted((e for e in step["events"] if e["type"] in BOXED and e.get("box")), key=lambda e: e["t"]):
            if ev["type"] in FORM_EVENTS and ev.get("form_box"):
                close()
                out[id(ev)] = ev["form_box"]
            elif ev["type"] in FIELD:
                run.append(ev)
            else:
                close()
        close()
    return out


def spot_box(ev: dict) -> dict:
    """N11: what the spotlight outlines: the field with its label (C9), or the button."""
    return label_box(ev)


def spot_targets(events: list[dict]) -> list[dict]:
    """Consecutive actions on the same element share one spotlight position."""
    targets: list[dict] = []
    for ev in events:
        box = spot_box(ev)
        if targets and same_box(targets[-1]["box"], box):
            targets[-1]["events"].append(ev)
            continue
        targets.append({"box": box, "events": [ev]})
    return targets


def spot_moves(targets: list[dict]) -> list[tuple[float, float]]:
    """N11: (start, end) of the 250-400 ms move into every target after the first: it leaves when the
    previous action ends and lands SPOT_LEAD before the next one when there is time."""
    moves = []
    last_end = -INF
    for prev, cur in zip(targets, targets[1:]):
        done = prev["events"][-1]
        prev_end = (done.get("t_end") or done["t"]) + (KEEP[done["type"]] if done["type"] == "click" else 0)
        t = cur["events"][0]["t"]
        start = max(prev_end, t - SPOT_LEAD - SPOT_MOVE, last_end)
        if start + SPOT_MOVE <= t - SPOT_LEAD + 1e-9:
            dur = SPOT_MOVE
        else:
            dur = max(SPOT_MIN, min(SPOT_MAX, t - start))
            start = max(min(start, t - dur), last_end)
        moves.append((round(start, 3), round(start + dur, 3)))
        last_end = start + dur
    return moves


def static_runs(t0: float, t1: float, changes: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """C8: the spans of [t0, t1] without a visual change (`changes`: spotlight moves)."""
    return [(round(a, 3), round(b, 3)) for a, b in subtract([(t0, t1)], changes)]


def form_shot(shot: dict, events: list[dict], stage: Stage, frame: dict | None) -> dict:
    """N10: one shot for consecutive actions in one form (or one top-to-bottom part of it)."""
    boxes = [spot_box(e) for e in events]
    targets = spot_targets(events)
    first = events[0]
    out = {**shot, "events": events, "box": union_all(boxes), "boxes": boxes, "field": True,
           "t": first["t"], "lead": lead(first), "pointer": first["type"] in POINTER,
           "end": max(e.get("t_end") or e["t"] for e in events), "selector": first.get("selector"),
           "point": first.get("point") or dict(zip("xy", center(boxes[0]))),
           "targets": targets, "moves": spot_moves(targets)}
    if frame is None:
        part = pad_box(union_all(boxes), FORM_PAD)
        frame = stage.form_frame(part, boxes) or stage.frame(*center(part), stage.form_scale(part))
        out["frame_box"] = part
    out["frame"] = frame
    return out


def split_form(shot: dict, stage: Stage) -> list[dict]:
    """N10: the whole form in one framing, or the fewest top-to-bottom framings (in action order) that keep
    every field whole at a legible scale."""
    events = shot["events"]
    frame = stage.form_frame(shot["form"], [spot_box(e) for e in events])
    if frame:
        return [form_shot({**shot, "frame_box": shot["form"]}, events, stage, frame)]
    groups: list[list[dict]] = []
    for ev in events:
        if groups:
            boxes = [spot_box(e) for e in groups[-1] + [ev]]
            if stage.form_frame(pad_box(union_all(boxes), FORM_PAD), boxes):
                groups[-1].append(ev)
                continue
        groups.append([ev])
    return [form_shot(shot, group, stage, None) for group in groups]


def shots_of(timeline: dict, stage: Stage) -> list[dict]:
    """One framing per boxed event, but one per form (N10); events on the same element share it."""
    bounds = screen_bounds(timeline)
    forms = form_boxes(timeline)
    shots: list[dict] = []
    for step in timeline["steps"]:
        for ev in sorted((e for e in step["events"] if e["type"] in BOXED and e.get("box")), key=lambda e: e["t"]):
            # A toast/row at the very screen change (edit cuts the wait for it) belongs to the new screen.
            edge = 1e-6 if ev["type"] in POINTER else -1e-6
            period = sum(1 for b in bounds if b < ev["t"] - edge)
            fbox = stage.focus_box(ev)
            end = ev.get("t_end") or ev["t"]
            last = shots[-1] if shots else None
            form = forms.get(id(ev))
            if form:
                if last and last.get("form") and last["period"] == period and same_box(last["form"], form):
                    last["events"].append(ev)
                else:
                    shots.append({"step": step["id"], "period": period, "events": [ev], "form": form})
                continue
            if (last and not last.get("form") and last["period"] == period and ev.get("selector")
                    and ev["selector"] == last["selector"]
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
    shots = [part for shot in shots for part in (split_form(shot, stage) if shot.get("form") else [shot])]
    prev = None
    for shot in shots:
        if shot.get("form"):
            shot["keep"] = shot["box"]
            prev = shot
            continue
        shot["frame_box"] = shot["box"]
        # Two fields typed back to back with no time for a 400 ms pan: the next framing also keeps the
        # previous field whole when both fit at detail scale, so neither is cut while typing (C9).
        if (prev and prev["period"] == shot["period"] and prev["field"] and shot["field"] and shot["pointer"]
                and shot["t"] - prev["end"] < MOVE + shot["lead"]):
            both = union(prev["box"], shot["box"])
            if stage.fit(both) >= stage.detail_min:
                shot["frame_box"] = both
        shot["frame"] = stage.shot_frame(shot)
        shot["keep"] = shot["frame_box"]
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


def leaves_toast(a: dict, b: dict, origin: dict, stage: Stage) -> bool:
    """C10/C4: from a toast framing to a target not even partly in it, the camera cuts: the pan would cross
    the empty part of the screen. A target next to the toast keeps its pan (same populated area)."""
    return a["events"][-1]["type"] == "result" and not overlaps(Stage.map(b["box"], origin), stage.view)


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

    def frozen(shot, t0, t1) -> bool:
        """C8: the shot held over [t0, t1] stays identical longer than the limit (spotlight moves count)."""
        return any(b - a > limit + 1e-6 for a, b in static_runs(t0, t1, shot.get("moves", [])))

    def pushed(shot) -> dict | None:
        return stage.push(shot["frame"], shot["keep"], shot.get("boxes"))

    def hold(shot, t0, t1, end):
        if shot.get("form"):
            add("form", t0, t1, shot["frame"], end, box=shot["keep"], form_box=shot["frame_box"])
        else:
            add("detail", t0, t1, shot["frame"], end, box=shot["keep"])

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
        if k > 0 and first["events"][0]["type"] == "result":
            first["arrive"] = a       # S1(a)/C4: the click's new screen opens on the toast: cut straight to it
        elif est - a >= ESTABLISH_MIN - 1e-9:
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
            if frozen(prev, free, start):
                # C8: a long hold becomes a slow push-in; the pan then leaves from the pushed framing.
                end = pushed(prev) or end
                start, dur = transition(prev, shot, free, stage, end)
            start = min(start, b)
            if leaves_toast(prev, shot, end, stage):
                # A hard cut once the toast had its R2 time, when the next target is due (it needs no travel).
                start, dur = min(max(free, _keep(prev, HOLD), shot["t"] - shot["lead"]), b), 0.0
            hold(prev, free, start, end)
            if dur:
                add("move", start, min(start + dur, b), end, shot["frame"])
            shot["arrive"] = start + dur
            free = max(free, min(start + dur, b))
        last = group[-1]
        end = (pushed(last) or last["frame"]) if frozen(last, free, b) else last["frame"]
        hold(last, free, b, end)
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
        if seg.get("form_box"):
            item["form_box"] = dict(seg["form_box"])
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
    timeline = with_surfaces(timeline)
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

    items.extend(plan_spotlights(shots, camera, stage, pal, timeline))
    items.extend(plan_surfaces(timeline, camera, stage))

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


def plan_spotlights(shots: list[dict], camera: list[dict], stage: Stage, pal: dict, timeline: dict) -> list[dict]:
    """N11: one `spotlight` item per field of every form shot, from when it lands on the field until it
    leaves it (`move`: the 250-400 ms move into it). `group` is the form shot, `box` the field in source px."""
    step_of = {id(e): s["id"] for s in timeline["steps"] for e in s["events"]}
    out = []
    for group, shot in enumerate(s for s in shots if s.get("form")):
        arrive = shot["arrive"]
        _, leave, move_out = framed_span(camera, arrive)
        starts = [arrive] + [m[1] for m in shot["moves"]]
        ends = [m[0] for m in shot["moves"]] + [leave]
        kept = []
        for k, target in enumerate(shot["targets"]):
            t0, t1 = max(starts[k], arrive), min(ends[k], leave)
            if t1 - t0 <= 1e-6:
                continue
            ev = target["events"][0]
            item = {"kind": "spotlight", "t0": round(t0, 3), "t1": round(t1, 3), "group": group,
                    "rect": rnd(stage.map(target["box"], frame_at(camera, t0))), "box": dict(target["box"]),
                    "selector": ev.get("selector", ""), "event": ev["type"], "step": step_of.get(id(ev)),
                    "color": pal["highlight"], "dim": SPOT_DIM, "dim_color": pal["background"]}
            if kept and k > 0 and shot["moves"][k - 1][0] >= arrive - 1e-6:
                item["move"] = list(shot["moves"][k - 1])
            kept.append(item)
        if kept:
            kept[-1]["exit"] = "cut" if move_out - leave <= 1e-6 else "fade"
        out.extend(kept)
    return out


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


def build(timeline: dict, brand: dict, logo_src: str | None = None,
          icon_srcs: dict[str, str] | None = None) -> tuple[str, dict]:
    """(index.html, layout) for one video. `icon_srcs`: surface name -> src of its toolbar icon."""
    timeline = with_surfaces(timeline)
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

    # Spotlight (N11): one SVG per form shot inside the camera (source px): a dim rect masked by the hole of
    # the active field (luminance mask: white keeps, black cuts; not drawn colors) plus its outline. GSAP
    # tweens the rect attributes field to field (250-400 ms ease-in-out; SVG geometry is sub-pixel, no
    # layout snapping), so any seek renders the same frame.
    spot_markup = []
    groups: dict[int, list[dict]] = {}
    for item in items:
        if item["kind"] == "spotlight":
            groups.setdefault(item["group"], []).append(item)
    for group, spots in groups.items():
        sid = f"spot-{group}"

        def attrs(box):
            return f'x: {num(box["x"] - 6)}, y: {num(box["y"] - 4)}, width: {num(box["w"] + 12)}, height: {num(box["h"] + 8)}'

        x, y, w, h = (num(v) for v in (spots[0]["box"]["x"] - 6, spots[0]["box"]["y"] - 4,
                                         spots[0]["box"]["w"] + 12, spots[0]["box"]["h"] + 8))
        hole = f'x="{x}" y="{y}" width="{w}" height="{h}" rx="8"'
        spot_markup.append(
            f'          <svg class="spot" id="{sid}" viewBox="-1920 -1080 5760 3240" xmlns="http://www.w3.org/2000/svg">\n'
            f'            <mask id="{sid}-mask"><rect x="-1920" y="-1080" width="5760" height="3240" fill="white" />'
            f'<rect class="{sid}-box" {hole} fill="black" /></mask>\n'
            f'            <rect x="-1920" y="-1080" width="5760" height="3240" fill="{spots[0]["dim_color"]}" '
            f'fill-opacity="{spots[0]["dim"]}" mask="url(#{sid}-mask)" />\n'
            f'            <rect class="{sid}-box spot-ring" {hole} fill="none" stroke="{spots[0]["color"]}" />\n'
            f'          </svg>')
        script.append(f'tl.to("#{sid}", {{opacity: 1, duration: {num(SPOT_FADE)}, ease: "power1.out"}}, '
                      f'{num(spots[0]["t0"])});')
        for spot in spots[1:]:
            a, b_ = spot.get("move") or (spot["t0"], spot["t0"])
            if b_ - a < 1e-6:
                script.append(f'tl.set(".{sid}-box", {{attr: {{{attrs(spot["box"])}}}}}, {num(spot["t0"])});')
                continue
            script.append(f'tl.to(".{sid}-box", {{attr: {{{attrs(spot["box"])}}}, duration: {num(b_ - a)}, '
                          f'ease: "power2.inOut"}}, {num(a)});')
        last = spots[-1]
        if last.get("exit") == "cut":
            script.append(f'tl.set("#{sid}", {{opacity: 0}}, {num(last["t1"])});')
        else:
            script.append(f'tl.to("#{sid}", {{opacity: 0, duration: 0.2, ease: "power1.in"}}, {num(last["t1"])});')

    # Surfaces (S5): the panel plays the surface track (same clock as the screen) and shows only while open;
    # the strip holds the extension icon, pressed while its panel is open.
    surface_markup = []
    for name, spec in (timeline.get("surfaces") or {}).items():
        g = surface_geometry(spec)
        sid = f"surface-{name}"
        ic, bar = g["icon"], g["toolbar"]
        src = (icon_srcs or {}).get(name)
        icon = (f'<img class="toolbar-icon" src="{esc(src)}" alt="" ' if src else '<div class="toolbar-icon toolbar-glyph" ') + \
            f'style="{box_style([ic["x"] - bar["x"], ic["y"] - bar["y"], ic["w"], ic["h"]])}"' + (" />" if src else "></div>")
        surface_markup.append(
            f'          <div class="toolbar" id="{sid}-bar" style="{box_style([bar["x"], bar["y"], bar["w"], bar["h"]])}">'
            f'<div class="toolbar-press" id="{sid}-press"></div>{icon}</div>\n'
            f'          <div class="surface" id="{sid}" style="{box_style([g["panel"][k] for k in "xywh"])}">'
            f'<video id="{sid}-video" class="clip" src="assets/{esc(spec["file"])}" muted playsinline '
            f'data-start="{num(ss)}" data-duration="{num(se - ss)}"></video></div>')
        for item in (i for i in items if i["kind"] == "surface" and i["name"] == name):
            for target in (f"#{sid}", f"#{sid}-press"):
                script.append(f'tl.set("{target}", {{opacity: 1}}, {num(item["t0"])});')
                script.append(f'tl.set("{target}", {{opacity: 0}}, {num(item["t1"])});')
        for item in (i for i in items if i["kind"] == "toolbar" and i["name"] == name):
            script.append(f'tl.to("#{sid}-bar", {{opacity: 1, duration: 0.2, ease: "power1.out"}}, {num(item["t0"])});')
            script.append(f'tl.to("#{sid}-bar", {{opacity: 0, duration: 0.2, ease: "power1.in"}}, {num(item["t1"])});')

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
        "HIGHLIGHTS": "\n".join(hl_markup), "SPOTLIGHTS": "\n".join(spot_markup), "OVERLAYS": "\n".join(overlays), "CARDS": "\n".join(cards),
        "SURFACES": "\n".join(surface_markup),
        "TIMELINE": "\n".join("      " + line for line in script),
    }
    return fill(TEMPLATE.read_text(encoding="utf-8"), values), layout


def stage_top(layout: dict) -> float:
    return layout["safe"]["top"] + 20


# --- project ----------------------------------------------------------------------------------

def compose_video(timeline: dict, screen: Path, mix: Path, brand: dict, out: Path, logo: Path | None = None,
                  checked: bool = True, icons: dict[str, Path] | None = None) -> dict:
    """Writes the HyperFrames project of one video into `out` (index.html, assets/, layout.json). Surface tracks
    (timeline `surfaces`) are read next to `screen`; `icons`: surface name -> its toolbar icon file."""
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
    icon_srcs = {}
    for name, spec in (timeline.get("surfaces") or {}).items():
        track = screen.parent / spec["file"]
        if not track.exists():
            raise PipelineError(f"Falta {track.name} junto a {screen.name}. Corré antes edit.py.")
        shutil.copyfile(track, assets / spec["file"])
        icon = (icons or {}).get(name)
        if icon:
            icon_srcs[name] = f"assets/surface-{name}-icon{icon.suffix}"
            shutil.copyfile(icon, out / icon_srcs[name])
    page, layout = build(timeline, brand, logo_src, icon_srcs)
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
        icons = {}
        for name, spec in (timeline.get("surfaces") or {}).items():
            if spec.get("icon"):
                path = pdir / spec["icon"]
                if not path.exists():
                    raise PipelineError(f"surfaces.{name}.icon: no existe {path}")
                icons[name] = path
        results[video] = compose_video(timeline, screen, mix, brand, pdir / f"hf-{video}", brand["logo"],
                                       icons=icons)
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
