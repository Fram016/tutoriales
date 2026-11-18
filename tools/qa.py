"""Stage: QA. Automatic checks of reglas/reglas-video.md on every video, plus stills for review.

Usage: python tools/qa.py <slug> [--video ID] [--pre]

--pre  check BEFORE rendering: only timeline.json + layout.json + snapshots, no MP4 (fast fix loop).
       Without --pre the MP4 checks run too (after the one final render).

For each video of tutorial.yaml (or only --video ID) it reads proyectos/<slug>/:
  edit/<video>/timeline.json  type duration (RED 15–35, PRO 20–60, NOV 15–30, TUT > 5 min needs
                           chapters), A2 voice gaps > 1.0 s, closing card ≤ 2.5 s, N8 RED/PRO
                           closing names a destination
  hf-<video>/layout.json   O1, O2, R1, R2, T1, T2, C1, C5, V1, V3, V4, L1–L4 on the captions and
                           C7 establishing shot per screen, C8 no framing frozen > 4 s (TUT) / 3 s,
                           C9 active control (and its frame_box with label) inside the viewport,
                           C10 clicks in frame and hard cut on screen change, N1 instruction before
                           the action, N2/N7 chip text and no repeated text, N3 captions in the band,
                           N5 brand palette, N6 result window, N9 stable 9:16 composition
  out/<slug>-<video>.mp4   (not with --pre) resolution by format, duration vs timeline total (±0.3 s),
                           audio track, A1 integrated loudness −14 ±1 LUFS and true peak < −1 dBTP,
                           A2 silences > 1.0 s, C4 near-empty frames every 0.25 s outside the
                           opening, closing and result windows (N6)
Then snapshots (every video in parallel) at the opening, each establishing shot, mid-typing,
0.2 s before each click, every result/highlight and the closing; their PNG paths are printed for
the mandatory visual review. Writes qa/<video>.json {mode: pre|full, checks: [{id, rule, status
PASS|FAIL|WARN, detail}]}, prints a table and exits 1 on any FAIL.
"""
from __future__ import annotations

import argparse
import colorsys
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import yaml

from common import PipelineError, main_guard, project_dir, read_json, run, which, write_json
from compose import R2_CLEAN
from edit import INSTRUCTION, instruction_share
from lint import DESTINATION, language_issues, norm, similarity, wrap

SIZES = {"16:9": (1920, 1080), "9:16": (1080, 1920)}
DURATION_TOLERANCE = 0.3
LOUDNESS_TARGET, LOUDNESS_TOLERANCE, TRUE_PEAK_MAX = -14.0, 1.0, -1.0
SILENCE_DB, MAX_GAP, CLOSING_MAX = -50, 1.0, 2.5
TYPE_RANGES = {"RED": (15, 35), "PRO": (20, 60), "NOV": (15, 30)}
TUT_CHAPTERS_AFTER = 300
# C4: frames sampled every 0.25 s at 1/4 scale; 8 px tiles = 32 output px.
SAMPLE_FPS, SAMPLE_DIV, TILE, TILE_STD, BG_DIST, EMPTY_LIMIT = 4, 4, 8, 3.0, 10.0, 0.70
# C1/R1: detail zoom threshold. 9:16 is a real crop whose base scale is ≈1.78× (L6).
DETAIL_SCALE = {"16:9": 1.8, "9:16": 1.75}
CONTEXT_MAX, MIN_RESULT, MIN_CAPTION = 1.0, R2_CLEAN, 1.2
LINE_CHARS, MAX_LINES, MIN_FONT, MIN_CONTRAST = 42, 2, 40, 4.5
TITLE_MAX, SAFE_TOP, SAFE_BOTTOM, VIEWPORT_MIN = 3.0, 0.15, 0.20, 0.70
EPS = 0.05
# T1: a caption line may not end in an article, preposition, conjunction or possessive.
WEAK_ENDINGS = set("""
el la los las lo un una unos unas al del a ante bajo con contra de desde durante en entre hacia hasta
mediante para por según sin sobre tras y e ni o u que pero mas sino porque pues si aunque como cuando
mientras tu tus su sus mi mis este esta estos estas ese esa nuestro nuestra
""".split())
TOUCHING = ("active", "result", "highlight")
# Round two (Parte 4).
ESTABLISH_WINDOW, ESTABLISH_MAX, ESTABLISH_SCALE = 1.5, 1.0, 1.05   # C7
STATIC_MAX, STATIC_DEFAULT, SAME_PX, SAME_SCALE = {"TUT": 4.0}, 3.0, 4.0, 0.01  # C8
FRAME_TOL, CUT_AFTER, SYNC_LATE, SIMILAR = 2.0, 0.3, 0.3, 0.60  # C9, C10, N1, N2
HUE_TOL, CHROMA_MIN, NEUTRAL_SAT, BLACK_L = 15.0, 0.08, 0.15, 0.10  # N5
CHIP_TEXT = re.compile(r"^(?:Parte \d+ · )?Paso \d+$")
TIME_RES = 1e-3   # timeline.json times are rounded to the millisecond
FILLER = {"haz", "clic", "click", "toca", "pulsa", "presiona", "boton"}
HEX = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
BRAND_KEYS = ("primary", "accent", "background", "surface", "on_surface", "text")


def check(check_id: str, rule: str, ok, detail: str) -> dict:
    status = ok if isinstance(ok, str) else ("PASS" if ok else "FAIL")
    return {"id": check_id, "rule": rule, "status": status, "detail": detail}


def problems(check_id: str, rule: str, found: list[str], ok_detail: str) -> dict:
    if not found:
        return check(check_id, rule, True, ok_detail)
    more = f" (+{len(found) - 5})" if len(found) > 5 else ""
    return check(check_id, rule, False, "; ".join(found[:5]) + more)


# ---------- geometry and time helpers ----------

def intersects(a, b) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return min(ax + aw, bx + bw) - max(ax, bx) > 0 and min(ay + ah, by + bh) - max(ay, by) > 0


def overlap(a0, a1, b0, b1) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def subtract(spans, cuts):
    """Parts of the (t0, t1) spans outside every cut interval."""
    out = list(spans)
    for c0, c1 in cuts:
        nxt = []
        for s0, s1 in out:
            if s1 <= c0 or s0 >= c1:
                nxt.append((s0, s1))
                continue
            if s0 < c0:
                nxt.append((s0, c0))
            if s1 > c1:
                nxt.append((c1, s1))
        out = nxt
    return [(a, b) for a, b in out if b - a > 1e-6]


def merge(spans, gap=0.01):
    merged = []
    for s0, s1 in sorted(spans):
        if merged and s0 - merged[-1][1] <= gap:
            merged[-1] = (merged[-1][0], max(merged[-1][1], s1))
        else:
            merged.append((s0, s1))
    return merged


def block_span(block) -> tuple[float, float] | None:
    if not block:
        return None
    start = float(block.get("start", 0))
    return start, start + float(block.get("duration", 0))


def cards(timeline: dict) -> list[tuple[float, float]]:
    """Opening, requirements and closing: the intro/outro of C1/C4."""
    return [s for s in (block_span(timeline.get(k)) for k in ("opening", "requirements", "closing")) if s]


def segments(timeline: dict) -> list[tuple[str, float, float]]:
    out = [(name, *span) for name in ("opening", "requirements", "closing")
           if (span := block_span(timeline.get(name)))]
    out += [(s["id"], float(s["start"]), float(s["start"]) + float(s["duration"])) for s in timeline.get("steps", [])]
    return sorted(out, key=lambda s: s[1])


def fmt_t(t: float) -> str:
    return f"{t:.2f}s"


# ---------- timeline ----------

def voice_spans(timeline: dict) -> list[tuple[float, float]]:
    blocks = [timeline.get(k) for k in ("opening", "requirements")] + list(timeline.get("steps", [])) + \
        [timeline.get("closing")]
    spans = []
    for block in blocks:
        if block and float(block.get("voice_duration") or 0) > 0:
            start = float(block.get("voice_start") or 0)
            spans.append((start, start + float(block["voice_duration"])))
    return sorted(spans)


def check_timeline(timeline: dict) -> list[dict]:
    rows = []
    vtype, total = timeline.get("type"), float(timeline.get("total") or 0)
    if vtype in TYPE_RANGES:
        low, high = TYPE_RANGES[vtype]
        rule = {"RED": "RED2/V5", "PRO": "PRO2", "NOV": "NOV2"}[vtype]
        rows.append(check("S3.duration", rule, low <= total <= high, f"{total:.1f} s ({vtype}: {low}–{high} s)"))
    else:
        rows.append(check("S3.duration", "TUT2", True, f"{total:.1f} s (TUT: libre)"))
    chapters = any(s.get("chapter") for s in timeline.get("steps", []))
    long = vtype == "TUT" and total > TUT_CHAPTERS_AFTER
    rows.append(check("E3.chapters", "E3/TUT3", chapters or not long,
                      f"{total / 60:.1f} min, {'con' if chapters else 'sin'} capítulos"))

    spans = voice_spans(timeline)
    gaps = []
    cursor = 0.0
    for start, end in spans + [(total, total)]:
        if start - cursor > MAX_GAP + EPS:
            gaps.append(f"{fmt_t(cursor)}–{fmt_t(start)} ({start - cursor:.1f} s)")
        cursor = max(cursor, end)
    if not spans:
        gaps.append("sin narración")
    rows.append(problems("A2.voice_gaps", "A2", [f"silencio de voz {g}" for g in gaps],
                         f"ninguna pausa de voz > {MAX_GAP:g} s"))
    closing = timeline.get("closing") or {}
    dur = float(closing.get("duration") or 0)
    rows.append(check("A2.closing_card", "A2", 0 < dur <= CLOSING_MAX + EPS,
                      f"tarjeta de cierre {dur:.1f} s (máximo {CLOSING_MAX:g} s)"))
    return rows + check_destination(timeline)


def check_destination(timeline: dict) -> list[dict]:
    """N8: RED/PRO closings say where to see or do it."""
    if timeline.get("type") not in ("RED", "PRO"):
        return []
    closing = timeline.get("closing") or {}
    text = f"{closing.get('text') or ''} {closing.get('narration') or ''}".strip()
    return [check("N8.destination", "N8", bool(DESTINATION.search(text)),
                  f"cierre «{text}»" + ("" if DESTINATION.search(text) else
                                         ": di dónde verlo («en el enlace del perfil», «en nuestro canal»)"))]


def snapshot_times(timeline: dict, layout: dict | None = None) -> list[float]:
    """Key frames: opening, establishing shots, mid-typing, 0.2 s before each click, results, closing."""
    times = []
    for name in ("opening", "requirements"):
        if span := block_span(timeline.get(name)):
            times.append((span[0] + span[1]) / 2)
    excluded = cards(timeline)
    base = base_scale(layout or {}, timeline.get("format", "16:9"))
    for seg in (layout or {}).get("camera") or []:
        if seg.get("kind") != "move" and establishing(seg, base):
            times += [(a + b) / 2 for a, b in subtract([(float(seg["t0"]), float(seg["t1"]))], excluded)]
    for step in timeline.get("steps", []):
        key = False
        for ev in step.get("events", []):
            kind, t = ev.get("type"), float(ev["t"])
            t_end = float(ev.get("t_end") or 0)
            if kind == "type":
                times.append((t + t_end) / 2 if t_end > t else t)
            elif kind in ("click", "select"):
                times.append(max(t - 0.2, float(step["start"])))
            elif kind in ("result", "highlight"):
                times.append((t + t_end) / 2 if t_end > t else t + 0.4)
            else:
                continue
            key = True
        if not key:
            times.append(float(step["start"]) + float(step["duration"]) / 2)
    if span := block_span(timeline.get("closing")):
        times.append((span[0] + span[1]) / 2)
    return sorted({round(t, 3) for t in times})


# ---------- layout ----------

def camera_scale_at(camera: list[dict], t: float) -> float | None:
    for seg in camera:
        if float(seg["t0"]) <= t < float(seg["t1"]):
            return float(seg["scale"])
    return None


def caption_lines(item: dict, product: str | None) -> list[str]:
    return list(item.get("lines") or wrap(item.get("text", ""), product, LINE_CHARS))


def last_word(line: str) -> str:
    words = re.findall(r"[^\W\d_]+", line.lower())
    return words[-1] if words else ""


def check_layout(layout: dict, timeline: dict, tutorial: dict) -> list[dict]:
    rows = []
    fmt = timeline.get("format", "16:9")
    out_w, out_h = layout.get("output") or SIZES.get(fmt, (1920, 1080))
    items = layout.get("items", [])
    by_kind = {}
    for it in items:
        by_kind.setdefault(it.get("kind"), []).append(it)
    chips, captions = by_kind.get("chip", []), by_kind.get("caption", [])
    cursors, titles = by_kind.get("cursor", []), by_kind.get("title", [])
    touching = [it for k in TOUCHING for it in by_kind.get(k, [])]
    camera = layout.get("camera") or []
    excluded = cards(timeline)
    product = timeline.get("product") or tutorial.get("product")

    def clashes(overlays, targets):
        found = []
        for ov in overlays:
            for tg in targets:
                if overlap(ov["t0"], ov["t1"], tg["t0"], tg["t1"]) > 0 and intersects(ov["rect"], tg["rect"]):
                    found.append(f"{ov['kind']} «{ov.get('text', '')}» tapa {tg['kind']} "
                                 f"{tg.get('step', '')} en {fmt_t(max(ov['t0'], tg['t0']))}")
        return found

    # O1: step chip.
    rows.append(problems("O1.chip_overlap", "O1", clashes(chips, touching),
                         f"{len(chips)} etiquetas sin tapar elementos activos"))
    style = []
    recorded = False
    for chip in chips:
        if "opacity" in chip:
            recorded = True
            if float(chip["opacity"]) < 1.0:
                style.append(f"«{chip.get('text', '')}» opacidad {float(chip['opacity']):.0%}")
        if "contrast" in chip:
            recorded = True
            if float(chip["contrast"]) < MIN_CONTRAST:
                style.append(f"«{chip.get('text', '')}» contraste {float(chip['contrast']):.1f}:1")
    if style:
        rows.append(problems("O1.chip_style", "O1", style, ""))
    elif chips and not recorded:
        rows.append(check("O1.chip_style", "O1", "WARN", "compose no registró opacidad/contraste: revisa las capturas"))
    else:
        rows.append(check("O1.chip_style", "O1", True, "opacidad 100 % y contraste ≥ 4,5:1" if chips else "sin etiquetas"))

    # O2: captions vs active element / toast / highlight.
    rows.append(problems("O2.caption_overlap", "O2", clashes(captions, touching),
                         f"{len(captions)} subtítulos sin tapar el elemento activo"))

    # R1 / R2: result in detail and clear for ≥ 0.8 s.
    detail = DETAIL_SCALE.get(fmt, 1.8)
    results = by_kind.get("result", [])
    r1, r2 = [], []
    for res in results:
        mid = (res["t0"] + res["t1"]) / 2
        scale = camera_scale_at(camera, mid)
        if scale is None or scale < detail - 1e-6:
            r1.append(f"resultado en {fmt_t(mid)} a {scale if scale is not None else '?'}× (detalle ≥ {detail:g}×)")
        blockers = [(ov["t0"], ov["t1"]) for ov in captions + cursors if intersects(ov["rect"], res["rect"])]
        clear = subtract([(res["t0"], res["t1"])], merge(blockers))
        best = max((b - a for a, b in clear), default=0.0)
        if best < MIN_RESULT - 1e-6:
            r2.append(f"resultado en {fmt_t(res['t0'])}: {best:.2f} s limpio (mínimo {MIN_RESULT:g} s sin subtítulo ni cursor)")
    rows.append(problems("R1.detail", "R1", r1, f"{len(results)} resultados en zoom de detalle"))
    rows.append(problems("R2.result_clear", "R2", r2, f"{len(results)} resultados visibles ≥ {MIN_RESULT:g} s y limpios"))

    # T1: caption segmentation.
    lengths, durations, endings, crossings = [], [], [], []
    segs = segments(timeline)
    for cap in captions:
        lines = caption_lines(cap, product)
        if len(lines) > MAX_LINES:
            lengths.append(f"{len(lines)} líneas: {' / '.join(lines)}")
        lengths += [f"{len(line)} caracteres: «{line}»" for line in lines if len(line) > LINE_CHARS]
        dur = cap["t1"] - cap["t0"]
        if dur < MIN_CAPTION - 1e-6:
            durations.append(f"«{cap.get('text', '')}» {dur:.2f} s")
        for line in lines:
            if last_word(line) in WEAK_ENDINGS:
                endings.append(f"«{' / '.join(lines)}» termina línea en «{last_word(line)}»")
        if len(lines) > 1 and any(len(line.split()) == 1 for line in lines):
            endings.append(f"«{' / '.join(lines)}» deja una palabra sola")
        touched = [name for name, s0, s1 in segs if overlap(cap["t0"], cap["t1"], s0, s1) > EPS]
        if len(touched) > 1:
            crossings.append(f"«{cap.get('text', '')}» cruza {' → '.join(touched)}")
    rows.append(problems("T1.lines", "T1", lengths, f"≤ {MAX_LINES} líneas de ≤ {LINE_CHARS} caracteres"))
    rows.append(problems("T1.duration", "T1", durations, f"subtítulos ≥ {MIN_CAPTION:g} s"))
    rows.append(problems("T1.last_word", "T1", endings, "ninguna línea termina en artículo, preposición o conjunción"))
    rows.append(problems("T1.step", "T1", crossings, "ningún subtítulo cruza un cambio de paso"))

    # T2: font size in output pixels.
    sizes = [("layout", layout.get("font_px"))] + [
        (f"{it['kind']} «{it.get('text', '')}»", it.get("font_px")) for it in captions + chips + titles if "font_px" in it]
    small = [f"{name}: {px}px" for name, px in sizes if px is None or float(px) < MIN_FONT]
    rows.append(problems("T2.font", "T2", small, f"letra ≥ {MIN_FONT} px ({layout.get('font_px')} px)"))

    # C1: wide shots ≤ 1.0 s outside the opening and closing.
    if not camera:
        rows.append(check("C1.context", "C1", False, "layout.json sin cámara"))
    else:
        wide = [(float(s["t0"]), float(s["t1"])) for s in camera if float(s["scale"]) < detail - 1e-6]
        runs = merge(subtract(merge(wide), excluded))
        long_runs = [f"{fmt_t(a)}–{fmt_t(b)} ({b - a:.1f} s) por debajo de {detail:g}×"
                     for a, b in runs if b - a > CONTEXT_MAX + EPS]
        rows.append(problems("C1.context", "C1", long_runs, f"planos generales ≤ {CONTEXT_MAX:g} s"))

    # C5: constant cursor size.
    cursor_px = layout.get("cursor_px")
    sizes_px = [max(c["rect"][2], c["rect"][3]) for c in cursors]
    if cursor_px is None:
        rows.append(check("C5.cursor", "C5", False, "layout.json sin cursor_px"))
    elif sizes_px and max(sizes_px) - min(sizes_px) > 2:
        rows.append(check("C5.cursor", "C5", False, f"el cursor cambia de {min(sizes_px):g} a {max(sizes_px):g} px"))
    else:
        rows.append(check("C5.cursor", "C5", "PASS" if 40 <= float(cursor_px) <= 60 else "WARN",
                          f"cursor fijo de {cursor_px} px"))

    # V: vertical only.
    if fmt == "9:16":
        vp = layout.get("viewport") or [0, 0, 0, 0]
        rows.append(check("V1.viewport", "V1", vp[3] >= VIEWPORT_MIN * out_h - 1,
                          f"interfaz {vp[3] / out_h:.0%} del alto (mínimo {VIEWPORT_MIN:.0%})"))
        late = [f"título hasta {fmt_t(t['t1'])}" for t in titles if t["t1"] > TITLE_MAX + EPS]
        rows.append(problems("V3.title", "V3", late, f"título solo en los primeros {TITLE_MAX:g} s"))
        top, bottom = SAFE_TOP * out_h, (1 - SAFE_BOTTOM) * out_h
        unsafe = [f"{it['kind']} «{it.get('text', '')}» en y={it['rect'][1]}–{it['rect'][1] + it['rect'][3]}"
                  for it in chips + captions if it["rect"][1] < top - 1 or it["rect"][1] + it["rect"][3] > bottom + 1]
        rows.append(problems("V4.safe_zones", "V4", unsafe,
                             f"etiquetas y subtítulos entre {top:.0f} y {bottom:.0f} px"))

    # L1–L4 on what is shown.
    device = tutorial.get("device") or "desktop"
    glossary = tutorial.get("glossary") or {}
    lang = []
    for cap in captions:
        text = cap.get("text") or " ".join(cap.get("lines") or [])
        lang += [f"{rule} {msg}" for rule, msg in language_issues(text, device, glossary)]
    rows.append(problems("L.captions", "L1-L4", lang, f"{len(captions)} subtítulos sin voseo, modismos ni sinónimos"))
    return rows + check_round_two(layout, timeline, tutorial)


# ---------- round two: C7-C10, N1-N9 ----------

def base_scale(layout: dict, fmt: str) -> float:
    return float(layout.get("base_scale") or (1920 / 1080 if fmt == "9:16" else 1.0))


def establishing(seg: dict, base: float) -> bool:
    return seg.get("reason") == "establishing" or seg.get("kind") == "context" or \
        float(seg["scale"]) <= base * ESTABLISH_SCALE + 1e-6


def has_offset(seg: dict) -> bool:
    return seg.get("x") is not None and seg.get("y") is not None


def ease(p: float) -> float:
    """GSAP power2.inOut, as compose animates the moves."""
    return 2 * p * p if p < 0.5 else 1 - (-2 * p + 2) ** 2 / 2


def frame_at(camera: list[dict], t: float) -> dict | None:
    """{x, y, s} of the camera at t (output = source * s + offset); None without offsets."""
    if not camera:
        return None
    seg = next((s for s in camera if float(s["t0"]) <= t < float(s["t1"])), None)
    if seg is None:
        seg = camera[-1] if t >= float(camera[-1]["t1"]) else camera[0]
    if not has_offset(seg):
        return None
    to = {"x": float(seg["x"]), "y": float(seg["y"]), "s": float(seg["scale"])}
    fr = seg.get("from")
    if seg.get("kind") != "move" or not fr:
        return to
    span = float(seg["t1"]) - float(seg["t0"])
    p = ease(min(max((t - float(seg["t0"])) / span, 0.0), 1.0)) if span > 0 else 1.0
    return {k: float(fr[k]) + (to[k] - float(fr[k])) * p for k in ("x", "y", "s")}


def map_box(box: dict, fr: dict) -> list[float]:
    return [box["x"] * fr["s"] + fr["x"], box["y"] * fr["s"] + fr["y"], box["w"] * fr["s"], box["h"] * fr["s"]]


def inside(rect, area, tol: float = FRAME_TOL) -> bool:
    x, y, w, h = rect
    ax, ay, aw, ah = area
    return x >= ax - tol and y >= ay - tol and x + w <= ax + aw + tol and y + h <= ay + ah + tol


def in_cards(t: float, excluded) -> bool:
    return any(a - 1e-6 <= t < b for a, b in excluded)


def fmt_rect(rect) -> str:
    return "[" + ", ".join(f"{v:.0f}" for v in rect) + "]"


def timeline_events(timeline: dict):
    for step in timeline.get("steps", []):
        for ev in sorted(step.get("events", []), key=lambda e: float(e["t"])):
            yield step, ev


def screen_changes(timeline: dict) -> list[float]:
    return sorted(float(ev["screen_at"]) for _, ev in timeline_events(timeline) if ev.get("screen_at") is not None)


def check_establishing(camera, timeline, base, fmt, excluded) -> dict:
    """C7: every screen (first step + each screen_at) opens with a ≤ 1.0 s establishing shot."""
    steps = timeline.get("steps", [])
    if not camera or not steps:
        return check("C7.establishing", "C7", "WARN", "sin cámara o sin pasos")
    end = float(timeline.get("screen_end") or 0) or max(float(s["t1"]) for s in camera)
    starts = [float(steps[0]["start"])] + [t for t in screen_changes(timeline) if t < end and not in_cards(t, excluded)]
    wide = merge([(float(s["t0"]), float(s["t1"])) for s in camera
                  if s.get("kind") != "move" and establishing(s, base)])
    found = []
    for ts in sorted(set(starts)):
        window = (ts, ts + ESTABLISH_WINDOW)
        span = next((w for w in wide if overlap(w[0], w[1], *window) > EPS), None)
        if span is None:
            found.append(f"pantalla en {fmt_t(ts)} sin plano de ubicación en sus primeros {ESTABLISH_WINDOW:g} s")
            continue
        shown = max((b - a for a, b in subtract([span], excluded)), default=0.0)
        if shown > ESTABLISH_MAX + EPS:
            found.append(f"plano de ubicación en {fmt_t(ts)} de {shown:.1f} s (máximo {ESTABLISH_MAX:g} s)")
    row = problems("C7.establishing", "C7", found, f"{len(set(starts))} pantallas con plano de ubicación ≤ {ESTABLISH_MAX:g} s")
    if found and fmt == "9:16":
        row["status"] = "WARN"  # the vertical crop has no full-screen view: review it in the snapshots
    return row


def check_static(camera, vtype, excluded) -> dict:
    """C8: no identical framing (same scale and center) longer than 4 s in TUT, 3 s otherwise."""
    limit = STATIC_MAX.get(vtype, STATIC_DEFAULT)

    def same(a, b) -> bool:
        if abs(float(a["scale"]) - float(b["scale"])) > SAME_SCALE or has_offset(a) != has_offset(b):
            return False
        return not has_offset(a) or (abs(float(a["x"]) - float(b["x"])) <= SAME_PX and
                                     abs(float(a["y"]) - float(b["y"])) <= SAME_PX)

    runs, cur = [], None
    for seg in sorted(camera, key=lambda s: float(s["t0"])):
        if seg.get("kind") == "move":
            cur = None
            continue
        if cur and same(cur["seg"], seg) and abs(float(seg["t0"]) - cur["t1"]) < 0.02:
            cur["t1"] = float(seg["t1"])
        else:
            cur = {"seg": seg, "t0": float(seg["t0"]), "t1": float(seg["t1"])}
            runs.append(cur)
    found = [f"{fmt_t(a)}–{fmt_t(b)} ({b - a:.1f} s) con el mismo encuadre"
             for run in runs for a, b in subtract([(run["t0"], run["t1"])], excluded) if b - a > limit + EPS]
    return problems("C8.static", "C8", found, f"ningún encuadre fijo > {limit:g} s")


def check_in_frame(actives, camera, timeline, vp, excluded) -> dict:
    """C9/V2: the active control (and its frame_box with the label) fully inside the viewport."""
    found = []
    for it in actives:
        t = float(it.get("t", it["t0"]))
        if not in_cards(t, excluded) and not inside(it["rect"], vp):
            found.append(f"{it.get('selector') or it.get('step', '')} en {fmt_t(t)}: {fmt_rect(it['rect'])} "
                         f"se sale del encuadre {fmt_rect(vp)}")
    for _, ev in timeline_events(timeline):
        box = ev.get("frame_box")
        if not box:
            continue
        moments = [float(ev["t"])] + ([float(ev["t_end"])] if ev.get("type") == "type" and ev.get("t_end") else [])
        for t in moments:
            fr = frame_at(camera, t)
            if fr is None or in_cards(t, excluded):
                continue
            rect = map_box(box, fr)
            if not inside(rect, vp):
                found.append(f"{ev.get('selector', '')} con su etiqueta en {fmt_t(t)}: {fmt_rect(rect)} "
                             f"se sale del encuadre {fmt_rect(vp)}")
                break
    return problems("C9.in_frame", "C9/V2", found, "controles activos completos dentro del encuadre")


def check_clicks(actives, camera, timeline, vp, excluded) -> list[dict]:
    """C10: no click on nothing; on a screen change the camera cuts (no pan right after it)."""
    off, clicks = [], 0
    for _, ev in timeline_events(timeline):
        t = float(ev["t"])
        if ev.get("type") != "click" or in_cards(t, excluded):
            continue
        fr = frame_at(camera, t)
        point = None
        if fr and ev.get("point"):
            point = (ev["point"]["x"] * fr["s"] + fr["x"], ev["point"]["y"] * fr["s"] + fr["y"])
        else:
            match = [it for it in actives if float(it["t0"]) - EPS <= t <= float(it["t1"]) + EPS and
                     it.get("selector", ev.get("selector")) == ev.get("selector")]
            if match:
                x, y, w, h = match[0]["rect"]
                point = (x + w / 2, y + h / 2)
        if point is None:
            continue
        clicks += 1
        if not inside([point[0], point[1], 0, 0], vp, 0):
            off.append(f"clic en {ev.get('selector', '')} en {fmt_t(t)} cae en ({point[0]:.0f}, {point[1]:.0f}), "
                       f"fuera del encuadre {fmt_rect(vp)}")
    pans = [f"paneo {fmt_t(float(m['t0']))}–{fmt_t(float(m['t1']))} justo después del cambio de pantalla "
            f"en {fmt_t(ts)} (tiene que ser un corte)"
            for ts in screen_changes(timeline) for m in camera
            if m.get("kind") == "move" and overlap(float(m["t0"]), float(m["t1"]), ts, ts + CUT_AFTER) > EPS / 5]
    return [problems("C10.click", "C10", off, f"{clicks} clics sobre el elemento, dentro del encuadre"),
            problems("C10.cut", "C10", pans, f"{len(screen_changes(timeline))} cambios de pantalla con corte")]


def instruction_end(step: dict) -> float:
    """End of the sentence that asks for the action: the `instruction_end` edit planned with, or (older
    timelines) the same estimate edit uses (edit.instruction_share of the step voice)."""
    if step.get("instruction_end") is not None:
        return float(step["instruction_end"])
    start, dur = float(step.get("voice_start") or 0), float(step.get("voice_duration") or 0)
    return start + dur * instruction_share(str(step.get("narration") or ""))


def check_sync(captions, timeline) -> dict:
    """N1: the instruction (voice and caption) comes before the action, ≤ 0.3 s after it at most."""
    found, checked = [], 0
    for step in timeline.get("steps", []):
        acts = [ev for ev in step.get("events", []) if ev.get("type") in ("click", "select")]
        if not acts or not float(step.get("voice_duration") or 0):
            continue
        checked += 1
        t_act = min(float(ev["t"]) for ev in acts)
        end = instruction_end(step)
        if end > t_act + SYNC_LATE + TIME_RES:
            found.append(f"{step['id']}: la instrucción termina en {fmt_t(end)}, {end - t_act:.1f} s después de la "
                         f"acción ({fmt_t(t_act)}; máximo {SYNC_LATE:g} s)")
        v0 = float(step.get("voice_start") or 0)
        v1 = v0 + float(step.get("voice_duration") or 0)
        caps = [c for c in captions if c.get("step") == step["id"]] or \
            [c for c in captions if "step" not in c and overlap(c["t0"], c["t1"], v0, v1) > EPS]
        caps.sort(key=lambda c: c["t0"])
        cap = next((c for c in caps if INSTRUCTION.search(c.get("text") or " ".join(c.get("lines") or []))),
                   caps[0] if caps else None)
        if cap and cap["t0"] >= t_act - 1e-6:
            found.append(f"{step['id']}: el subtítulo «{cap.get('text', '')}» aparece en {fmt_t(cap['t0'])}, "
                         f"después de la acción ({fmt_t(t_act)})")
    return problems("N1.sync", "N1", found, f"{checked} pasos con la instrucción antes de la acción")


def check_texts(chips, captions, items, timeline) -> list[dict]:
    """N2/N7: chip only «Paso N» (TUT) or none; no title repeated by the opening card or a caption."""
    rows = []
    if timeline.get("type", "TUT") == "TUT":
        bad = [f"«{c.get('text', '')}»" for c in chips if not CHIP_TEXT.match(str(c.get("text") or "").strip())]
        rows.append(problems("N2.chip", "N2", [f"etiqueta {b}: solo «Paso N» (o «Parte N · Paso M»)" for b in bad],
                             f"{len(chips)} etiquetas solo con el número de paso"))
    else:
        rows.append(problems("N7.no_chip", "N7", [f"etiqueta «{c.get('text', '')}» en {fmt_t(c['t0'])}" for c in chips],
                             f"{timeline.get('type')}: sin etiquetas de paso"))
    opening = block_span(timeline.get("opening"))
    repeated = []
    if opening:
        shown = [it for it in items if overlap(it["t0"], it["t1"], *opening) > EPS]
        for title in [it for it in shown if it.get("kind") == "title"]:
            for card in [it for it in shown if it.get("kind") == "card"]:
                share = similarity(title.get("text"), card.get("text"))
                if share >= SIMILAR:
                    repeated.append(f"título «{title.get('text', '')}» y tarjeta «{card.get('text', '')}» "
                                    f"comparten {share:.0%} de las palabras")
    rows.append(problems("N2.opening", "N2", repeated, "la apertura no repite el título"))
    visible = " ".join(norm(str(c.get("text") or "")) for c in chips)
    echoes = []
    for step in timeline.get("steps", []):
        title = str(step.get("title") or "")
        if not title or norm(title) not in visible:
            continue
        for cap in [c for c in captions if c.get("step") == step["id"]]:
            text = cap.get("text") or " ".join(cap.get("lines") or [])
            if similarity(text, title, FILLER) >= SIMILAR:
                echoes.append(f"{step['id']}: el subtítulo «{text}» repite el título «{title}»")
    rows.append(problems("N2.caption_title", "N2", echoes, "ningún subtítulo repite el título del paso"))
    return rows


def check_band(captions, bands, vp) -> dict:
    """N3: captions live in a fixed band outside the UI viewport."""
    found = [f"subtítulo «{c.get('text', '')}» {fmt_rect(c['rect'])} sobre la interfaz {fmt_rect(vp)}"
             for c in captions if intersects(c["rect"], vp)]
    if bands:
        found += [f"subtítulo «{c.get('text', '')}» {fmt_rect(c['rect'])} fuera de la banda"
                  for c in captions if not any(inside(c["rect"], b["rect"]) for b in bands)]
    if found:
        return problems("N3.band", "N3", found, "")
    if captions and not bands:
        return check("N3.band", "N3", "WARN", "layout.json sin banda (band): no puedo confirmar dónde van los subtítulos")
    return check("N3.band", "N3", True, f"{len(captions)} subtítulos en la banda, fuera de la interfaz")


def rgb(color: str) -> tuple[float, float, float] | None:
    m = HEX.fullmatch(str(color).strip())
    if not m:
        return None
    h = m.group(0)[1:]
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def neutral(c) -> bool:
    hue, light, sat = colorsys.rgb_to_hls(*c)
    return max(c) - min(c) < CHROMA_MIN / 2 or sat < NEUTRAL_SAT


def palette_issue(color: str, palette: list[tuple], surfaces: list[tuple] = ()) -> str | None:
    """N5: None when the color is a brand color, a shade of a brand hue or a neutral (not black).

    Near-black is only allowed when it is the brand background/surface (a dark app), never because
    the brand text happens to be dark."""
    c = rgb(color)
    if c is None:
        return None

    def same(p) -> bool:
        return max(abs(a - b) for a, b in zip(c, p)) <= 0.03

    if max(c) - min(c) < CHROMA_MIN and (max(c) + min(c)) / 2 < BLACK_L:
        return None if any(same(p) for p in surfaces) else "caja negra"
    if any(same(p) for p in palette):
        return None
    if neutral(c):
        return None
    hue = colorsys.rgb_to_hls(*c)[0] * 360
    for p in palette:
        if not neutral(p):
            diff = abs(hue - colorsys.rgb_to_hls(*p)[0] * 360) % 360
            if min(diff, 360 - diff) <= HUE_TOL:
                return None
    return "tono ajeno a la marca"


def item_colors(it: dict) -> list[str]:
    found = []
    for key, value in it.items():
        if not isinstance(value, str):
            continue
        if key == "style" or key in ("color", "background", "bg", "fill", "border", "stroke") or key.endswith("_color"):
            found += HEX.findall(value)
    return found


def check_palette(items, tutorial) -> dict:
    """N5: overlays use the brand palette (primary, its darker/lighter shades, neutrals; no black boxes)."""
    brand = tutorial.get("brand") or {}
    palette = [c for k in BRAND_KEYS if (c := rgb(brand.get(k) or ""))]
    surfaces = [c for k in ("background", "surface") if (c := rgb(brand.get(k) or ""))]
    if not palette:
        return check("N5.palette", "N5", "WARN", "tutorial.yaml sin brand: no puedo comparar los colores")
    found, seen = [], set()
    for it in items:
        for color in item_colors(it):
            issue = palette_issue(color, palette, surfaces)
            key = (it.get("kind"), color.lower())
            if issue and key not in seen:
                seen.add(key)
                found.append(f"{it.get('kind')} {it.get('text') and '«' + it['text'] + '» ' or ''}"
                             f"{color.lower()}: {issue}")
    return problems("N5.palette", "N5", found, "colores de la paleta de la marca")


def result_events(timeline: dict):
    return [(step, ev) for step, ev in timeline_events(timeline)
            if ev.get("type") == "result" or "toast" in str(ev.get("selector") or "").lower()]


def check_results(results, timeline) -> dict:
    """N6: every result/toast is framed ≥ 0.8 s (layout `result` t0–t1, the camera at rest on it) while
    edit keeps it on screen (event t–t_end); that window (and its zoom in/out, `exempt`) is exempt from C4."""
    found = []
    events = result_events(timeline)
    for step, ev in events:
        t = float(ev["t"])
        t_end = float(ev.get("t_end") or 0) if float(ev.get("t_end") or 0) > t else float("inf")
        best = max((overlap(float(r["t0"]), float(r["t1"]), t, t_end) for r in results
                    if r.get("step", step["id"]) == step["id"]), default=0.0)
        if best < MIN_RESULT - TIME_RES:
            found.append(f"{step['id']}: el aviso {ev.get('selector', '')} en {fmt_t(t)} no tiene ventana de "
                         f"≥ {MIN_RESULT:g} s en layout.json (encuadrado {best:.2f} s mientras se ve, "
                         f"{fmt_t(t)}–{fmt_t(t_end) if t_end < float('inf') else '…'})")
    return problems("N6.result", "N6", found, f"{len(events)} avisos visibles ≥ {MIN_RESULT:g} s (exentos de C4)")


def check_vertical(camera, timeline, layout, vp, excluded) -> dict:
    """N9: one 9:16 composition: the source always covers the whole viewport (no bands that come and go)."""
    src_w, src_h = timeline.get("source") or (1920, 1080)
    shots = [s for s in camera if s.get("kind") != "move" and
             subtract([(float(s["t0"]), float(s["t1"]))], excluded)]
    if any(not has_offset(s) for s in shots):
        return check("N9.vertical", "N9", "WARN", "cámara sin x/y: no puedo medir las franjas")
    vx, vy, vw, vh = vp
    found = []
    for s in shots:
        x, y, sc = float(s["x"]), float(s["y"]), float(s["scale"])
        if x > vx + FRAME_TOL or y > vy + FRAME_TOL or x + src_w * sc < vx + vw - FRAME_TOL or \
                y + src_h * sc < vy + vh - FRAME_TOL:
            found.append(f"{fmt_t(float(s['t0']))}–{fmt_t(float(s['t1']))}: franja sin interfaz dentro del "
                         f"encuadre {fmt_rect(vp)}")
        if s.get("viewport") and list(s["viewport"]) != list(vp):
            found.append(f"{fmt_t(float(s['t0']))}: el encuadre cambia a {fmt_rect(s['viewport'])}")
    return problems("N9.vertical", "N9", found, f"composición vertical única {fmt_rect(vp)}")


def check_round_two(layout: dict, timeline: dict, tutorial: dict) -> list[dict]:
    fmt = timeline.get("format", "16:9")
    out_w, out_h = layout.get("output") or SIZES.get(fmt, (1920, 1080))
    vp = list(layout.get("viewport") or [0, 0, out_w, out_h])
    items = layout.get("items", [])
    by_kind = {}
    for it in items:
        by_kind.setdefault(it.get("kind"), []).append(it)
    camera = sorted(layout.get("camera") or [], key=lambda s: float(s["t0"]))
    excluded = cards(timeline)
    actives, captions = by_kind.get("active", []), by_kind.get("caption", [])
    rows = [check_establishing(camera, timeline, base_scale(layout, fmt), fmt, excluded),
            check_static(camera, timeline.get("type", "TUT"), excluded),
            check_in_frame(actives, camera, timeline, vp, excluded)]
    rows += check_clicks(actives, camera, timeline, vp, excluded)
    rows.append(check_sync(captions, timeline))
    rows += check_texts(by_kind.get("chip", []), captions, items, timeline)
    rows.append(check_band(captions, by_kind.get("band", []), vp))
    rows.append(check_palette(items, tutorial))
    rows.append(check_results(by_kind.get("result", []), timeline))
    if fmt == "9:16":
        rows.append(check_vertical(camera, timeline, layout, vp, excluded))
    return rows


def c4_ranges(timeline: dict, layout: dict | None) -> list[tuple[float, float]]:
    """Where C4 applies: outside the cards and the result windows (N6: R2 wins over C4)."""
    total = float(timeline.get("total") or 0)
    if layout:
        windows = [tuple(map(float, r.get("exempt") or (r["t0"], r["t1"])))
                   for r in layout.get("items", []) if r.get("kind") == "result"]
    else:
        windows = [(float(ev["t"]), max(float(ev.get("t_end") or 0), float(ev["t"]) + MIN_RESULT))
                   for _, ev in result_events(timeline)]
    spans = subtract(subtract([(0.0, total)], cards(timeline)), merge(windows))
    return [(round(a, 3), round(b, 3)) for a, b in spans]


# ---------- media ----------

def probe(path: Path) -> dict:
    out = run([which("ffprobe"), "-v", "error", "-show_entries",
               "stream=codec_type,codec_name,width,height:format=duration", "-of", "json", str(path)],
              quiet=True).stdout
    return json.loads(out)


def loudness(path: Path) -> tuple[float, float]:
    """(integrated LUFS, true peak dBTP) with ffmpeg ebur128."""
    res = run([which("ffmpeg"), "-hide_banner", "-nostats", "-i", str(path), "-map", "0:a:0",
               "-af", "ebur128=peak=true:framelog=verbose", "-f", "null", "-"], quiet=True)
    summary = res.stderr[res.stderr.rfind("Summary:"):]
    lufs = re.search(r"I:\s+(-?(?:[\d.]+|inf)) LUFS", summary)
    peak = re.search(r"Peak:\s+(-?(?:[\d.]+|inf)) dBFS", summary)
    if not lufs or not peak:
        raise PipelineError(f"No pude medir la sonoridad de {Path(path).name} (ebur128)")
    return float(lufs.group(1)), float(peak.group(1))


def check_loudness(path: Path) -> list[dict]:
    lufs, peak = loudness(path)
    return [check("A1.loudness", "A1", abs(lufs - LOUDNESS_TARGET) <= LOUDNESS_TOLERANCE,
                  f"{lufs:.1f} LUFS (objetivo {LOUDNESS_TARGET:g} ±{LOUDNESS_TOLERANCE:g})"),
            check("A1.true_peak", "A1", peak < TRUE_PEAK_MAX, f"pico {peak:.1f} dBTP (< {TRUE_PEAK_MAX:g} dBTP)")]


def silences(path: Path) -> list[tuple[float, float]]:
    res = run([which("ffmpeg"), "-hide_banner", "-nostats", "-i", str(path), "-map", "0:a:0",
               "-af", f"silencedetect=noise={SILENCE_DB}dB:d={MAX_GAP}", "-f", "null", "-"], quiet=True)
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", res.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", res.stderr)]
    if len(ends) < len(starts):
        ends.append(float(probe(path)["format"]["duration"]))
    return list(zip(starts, ends))


def check_silence(path: Path) -> list[dict]:
    found = [f"{fmt_t(max(a, 0))}–{fmt_t(b)} ({b - max(a, 0):.1f} s)" for a, b in silences(path)
             if b - max(a, 0) > MAX_GAP + EPS]
    return [problems("A2.silence", "A2", [f"silencio {f}" for f in found], f"ningún silencio > {MAX_GAP:g} s")]


def empty_ratio(frame: np.ndarray) -> float:
    """Share of TILE×TILE tiles that are uniform AND the frame's background colour."""
    h, w = frame.shape[0] // TILE, frame.shape[1] // TILE
    tiles = frame[:h * TILE, :w * TILE].reshape(h, TILE, w, TILE, 3).transpose(0, 2, 1, 3, 4)
    tiles = tiles.reshape(h, w, TILE * TILE, 3)
    flat = tiles.std(axis=2).max(axis=-1) < TILE_STD
    if not flat.any():
        return 0.0
    mean = tiles.mean(axis=2)
    keys, counts = np.unique(np.round(mean[flat] / 8), axis=0, return_counts=True)
    background = keys[counts.argmax()] * 8
    return float((flat & (np.abs(mean - background).max(axis=-1) < BG_DIST)).mean())


def check_empty_frames(path: Path, ranges, size) -> list[dict]:
    w, h = (int(size[0]) // SAMPLE_DIV, int(size[1]) // SAMPLE_DIV)
    bad, sampled = [], 0
    for a, b in ranges:
        if b - a <= 0:
            continue
        res = subprocess.run([which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-ss", f"{a:.3f}",
                              "-t", f"{b - a:.3f}", "-i", str(path), "-vf", f"fps={SAMPLE_FPS},scale={w}:{h}",
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
        if res.returncode != 0:
            raise PipelineError(f"ffmpeg no pudo leer {Path(path).name}: {res.stderr.decode(errors='replace')[-300:]}")
        frames = np.frombuffer(res.stdout, np.uint8)[: (len(res.stdout) // (w * h * 3)) * w * h * 3]
        for i, frame in enumerate(frames.reshape(-1, h, w, 3).astype(np.float32)):
            sampled += 1
            ratio = empty_ratio(frame)
            if ratio > EMPTY_LIMIT:
                bad.append(f"{fmt_t(a + i / SAMPLE_FPS)} {ratio:.0%} vacío")
    return [problems("C4.empty_frames", "C4", bad,
                     f"{sampled} fotogramas con ≤ {EMPTY_LIMIT:.0%} vacío (fuera de apertura y cierre)")]


def check_media(path: Path, timeline: dict, layout: dict | None = None) -> list[dict]:
    fmt = timeline.get("format", "16:9")
    w, h = SIZES.get(fmt, tuple(timeline.get("output") or (1920, 1080)))
    info = probe(path)
    video = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    audio = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    got = f"{video['width']}x{video['height']}" if video else "sin video"
    total = float(timeline.get("total") or 0)
    duration = float(info["format"]["duration"])
    rows = [check("tech.resolution", "S3", got == f"{w}x{h}", f"{got} (esperado {w}x{h} para {fmt})"),
            check("tech.duration", "S3", abs(duration - total) <= DURATION_TOLERANCE,
                  f"{duration:.2f} s (timeline {total:.2f} ±{DURATION_TOLERANCE} s)"),
            check("tech.audio", "A1", audio is not None, audio["codec_name"] if audio else "sin pista de audio")]
    if audio:
        rows += check_loudness(path) + check_silence(path)
    if video:
        ranges = [(a, min(b, duration)) for a, b in c4_ranges(timeline, layout) if a < duration]
        rows += check_empty_frames(path, ranges, (video["width"], video["height"]))
    return rows


# ---------- driver ----------

def take_snapshots(slug: str, video: str, times: list[float]) -> list[Path]:
    from render import snapshots  # render/compose are only needed for this step
    return snapshots(slug, video, times)


def check_video(slug: str, pdir: Path, tutorial: dict, video: dict,
                pre: bool = False) -> tuple[list[dict], list[float] | None]:
    """(checks, snapshot times or None when there is nothing to snapshot)."""
    vid = video["id"]
    rows: list[dict] = []
    timeline_path = pdir / "edit" / vid / "timeline.json"
    if not timeline_path.exists():
        return [check("timeline", "S3", False, f"falta edit/{vid}/timeline.json: corre antes el pipeline")], None
    timeline = read_json(timeline_path)
    layout_path = pdir / f"hf-{vid}" / "layout.json"
    layout = read_json(layout_path) if layout_path.exists() else None
    out = pdir / "out" / f"{slug}-{vid}.mp4"
    if not pre:
        if out.exists():
            rows += check_media(out, timeline, layout)
        else:
            rows.append(check("tech.file", "S3", False, f"falta out/{out.name}: corre render.py"))
    rows += check_timeline(timeline)
    if layout is not None:
        rows.append(check("layout", "L5", True, f"hf-{vid}/layout.json"))
        rows += check_layout(layout, timeline, tutorial)
    else:
        rows.append(check("layout", "L5", False, f"falta hf-{vid}/layout.json: compose.py v2 lo escribe; sin él "
                                                 "no se pueden validar O1, O2, R2, T1, T2, C1, C5, C7-C10, N1-N9, V"))
    return rows, (snapshot_times(timeline, layout) if pre or out.exists() else None)


def snapshot_all(slug: str, jobs: dict[str, list[float]]) -> dict[str, list[Path] | Exception]:
    """Snapshots of every video at once (one HyperFrames process each); they dominate --pre."""
    if not jobs:
        return {}
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = {vid: pool.submit(take_snapshots, slug, vid, times) for vid, times in jobs.items()}
        done = {}
        for vid, fut in futures.items():
            try:
                done[vid] = fut.result()
            except (PipelineError, ImportError) as exc:
                done[vid] = exc
    return done


def qa(slug: str, video: str | None = None, pre: bool = False) -> bool:
    pdir = project_dir(slug)
    tutorial = yaml.safe_load((pdir / "tutorial.yaml").read_text(encoding="utf-8")) or {}
    videos = tutorial.get("videos") or []
    if video:
        videos = [v for v in videos if v.get("id") == video]
        if not videos:
            raise PipelineError(f"tutorial.yaml no tiene un video '{video}'")
    if not videos:
        raise PipelineError("tutorial.yaml no tiene videos (formato v2)")
    mode = "pre" if pre else "full"
    passed = True
    print(f"[qa] {slug} ({'pre: layout + timeline + capturas, sin MP4' if pre else 'full: con MP4'})")
    print(f"  {'video':<10} {'regla':<8} {'chequeo':<19} {'estado':<6} detalle")
    checked = {v["id"]: check_video(slug, pdir, tutorial, v, pre) for v in videos}
    taken = snapshot_all(slug, {vid: times for vid, (_, times) in checked.items() if times is not None})
    all_shots = {}
    for v in videos:
        vid = v["id"]
        rows, _ = checked[vid]
        shots: list[Path] = []
        if isinstance(taken.get(vid), Exception):
            rows.append(check("snapshots", "QA", False, str(taken[vid]).splitlines()[0]))
        elif vid in taken:
            shots = taken[vid]
            rows.append(check("snapshots", "QA", True, f"{len(shots)} PNG para revisión visual"))
        ok = not any(r["status"] == "FAIL" for r in rows)
        passed &= ok
        all_shots[vid] = shots
        write_json(pdir / "qa" / f"{vid}.json", {"video": vid, "type": v.get("type"), "format": v.get("format"),
                                                 "mode": mode, "status": "PASS" if ok else "FAIL", "checks": rows,
                                                 "snapshots": [str(p) for p in shots]})
        for r in rows:
            print(f"  {vid:<10} {r['rule']:<8} {r['id']:<19} {r['status']:<6} {r['detail']}")
    for vid, shots in all_shots.items():
        if shots:
            print(f"[qa] capturas {vid} (revisión visual obligatoria):")
            for path in shots:
                print(f"  {path}")
    print(f"[qa] {'PASS' if passed else 'FAIL'} (detalle en proyectos/{slug}/qa/)")
    return passed


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug")
    ap.add_argument("--video", help="id de videos[] en tutorial.yaml (por defecto, todos)")
    ap.add_argument("--pre", action="store_true",
                    help="antes de renderizar: solo timeline.json + layout.json + capturas (sin MP4)")
    a = ap.parse_args()
    if not qa(a.slug, a.video, a.pre):
        sys.exit(1)


if __name__ == "__main__":
    main_guard(main)
