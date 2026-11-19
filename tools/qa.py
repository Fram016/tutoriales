"""Stage: QA. Automatic checks of reglas/reglas-video.md on every video, plus stills for review.

Usage: python tools/qa.py <slug> [--video ID] [--pre]

--pre  check BEFORE rendering: only timeline.json + layout.json + snapshots, no MP4 (fast fix loop).
       Without --pre the MP4 checks run too (after the one final render).

For each video of tutorial.yaml (or only --video ID) it reads proyectos/<slug>/:
  edit/<video>/timeline.json  type duration (RED 15–35, PRO 20–60, NOV 15–30, TUT > 5 min needs
                           chapters), A2 voice gaps > 1.0 s, closing card ≤ 2.5 s, N8 RED/PRO
                           closing names a destination
  hf-<video>/layout.json   O1, O2, R1, R2, T1, T2, C1, C5, V1, V3, V4, L1–L4 on the captions and
                           C1 detail 1.4–1.8× (form shots ≤ 1.8×), C7 establishing shot per screen,
                           C8 no framing frozen > 4 s (TUT) / 3 s (a spotlight move breaks it),
                           C9 active control (and its frame_box with label) inside the viewport,
                           C10 clicks in frame and hard cut on screen change, N1 instruction before
                           the action, N2/N7 chip text and no repeated text, N3 captions in the band,
                           N5 brand palette, N6 result window, N9 stable 9:16 composition,
                           N10 one form shot per form (no reframing field by field), N11 spotlight on
                           the active field, N12/V2 every field of the form inside the frame;
                           round four (Parte 6): N13 verified targets (target_ok), N14 what a caption
                           names is on screen, N16 part separators and «Parte N · Paso M», N17 context
                           badge per step, N18 summary after each download, N19 one sentence per
                           caption, N20 no pillarbox / legible scale / no zoom jumps, N21 band ≤ 1/8,
                           N22 surfaces inside the frame, N24 logo contrast, N27 closing optional (TUT);
                           round five (Parte 7, timeline `pace: fast`): P3 detail 1.15–1.4× (C1/R1),
                           form shots usually 1.0–1.2×, a whole-form shot opens its screen (C7), C8
                           at 2.5 s, a form wider than the viewport may be cropped beyond the used
                           fields (N12); P1 timeline total ≤ videos[].max_seconds; P4 (every pace) each
                           caption visible (outside the cards) ≥ max(1.5, caracteres/15 + 0.4) s, part
                           separators ≥ 1.5 s, each step chip visible ≥ 1.5 s before it changes; a part
                           separator is no A2 voice gap.
                           Surface events (`surface`) are moved onto their panel (layout `surface` box)
                           before C9/C10 and the other geometric checks
  out/<slug>-<video>.mp4   (not with --pre) resolution by format, duration vs timeline total (±0.3 s),
                           audio track, A1 integrated loudness −14 ±1 LUFS and true peak < −1 dBTP,
                           A2 silences > 1.0 s, C4 near-empty frames every 0.25 s outside the
                           opening, closing and result (R2) windows (N6), and N26 frames blank below
                           the header (C4) or with an abrupt change in only one half (WARN, review)
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

from common import (CHIP_MIN, PART_SECONDS, PipelineError, main_guard, measure_loudness, project_dir, read_json,
                    reading_seconds, run, which, write_json)
from compose import FORMATS as FRAMES, R2_CLEAN
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
# C1/R1: detail zoom 1.4–1.8× (Parte 5); when the format's base scale (the 9:16 crop) is above it, the
# base is the floor/ceiling, as compose's Stage.detail_min.
DETAIL_MIN, DETAIL_MAX = 1.4, 1.8
FAST_DETAIL, FAST_FORM_USUAL, FAST_STATIC = (1.15, 1.4), (1.0, 1.2), 2.5   # P3/P2 (timeline pace: fast)
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
# Round three (Parte 5).
FORM_USUAL, SPOT_DIM_MAX, SPOT_MOVE = (1.1, 1.5), 0.25, (0.25, 0.4)  # N10, N11
FIELDS = ("type", "select")
CHIP_TEXT = re.compile(r"^(?:Parte \d+ · )?Paso \d+$")
TIME_RES = 1e-3   # timeline.json times are rounded to the millisecond
FILLER = {"haz", "clic", "click", "toca", "pulsa", "presiona", "boton"}
HEX = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
BRAND_KEYS = ("primary", "accent", "background", "surface", "on_surface", "text")
# Round four (Parte 6).
TARGETED = ("click", "highlight")   # N13
# N14: what a caption names (heuristic) and the evidence that shows it; an instruction may name it just
# before it appears (N1: the instruction ends before its effect).
MENTIONS = (("Perseo", re.compile(r"\bPerseo\b"), "surface"),
            ("configuración", re.compile(r"\bconfiguraci[oó]n\b", re.I), "tab"),
            ("Cambiar", re.compile(r"\bCambiar\b"), "tab"),
            ("resumen", re.compile(r"\bresumen\b", re.I), "summary"),
            ("lista", re.compile(r"\blista\b", re.I), "list"))
NAMED_LEAD = 1.0
PART_CHIP = re.compile(r"^Parte (\d+) · Paso (\d+)$")   # N16
BADGES = ("context", "badge")                            # N17
DOWNLOAD = re.compile(r"\bxml\b|descarg|download", re.I)  # N18
NOT_DOWNLOAD = re.compile(r"carpeta|folder|configur", re.I)
SENTENCE_END = re.compile(r"[.!?…][”»\"')]*$")           # N19
INNER_SENTENCE = re.compile(r"[.!?…][”»\"')]*\s+\S")
SCALE_JUMP, LEGIBLE_KEYS = 0.35, ("legible_scale", "min_scale", "scale_floor")   # N20
BAND_SHARE = 1 / 8                                       # N21
LOGO_CONTRAST = 3.0                                      # N24
# N26: blank below the header (share of the viewport top skipped), and one half changing alone.
HEADER_SHARE, BLANK_LIMIT, MIX_CHANGE, MIX_STILL = 0.15, 0.90, 20.0, 8.0
# N26: a page that has not loaded has no content below its header: no tile row past HEADER_MAX of the viewport
# holds ROW_INK content tiles or more (the cursor is ~2). The _demo "Clientes" list (round 4) is 92 % empty
# below its header but its table reaches 36 % of the viewport; the SRI shell is a header and nothing else.
HEADER_MAX, ROW_INK = 0.25, 5


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
    """Opening, requirements, part separators (N16, when edit timed them) and closing: the cards of C1/C4."""
    parts = [p for p in timeline.get("parts") or [] if p.get("start") is not None and p.get("duration")]
    return [s for s in (block_span(b) for b in [timeline.get(k) for k in ("opening", "requirements", "closing")]
                        + parts) if s]


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
    cap = timeline.get("max_seconds")
    if cap is not None:
        rows.append(check("P1.max_seconds", "P1", total <= float(cap) + EPS,
                          f"{total:.1f} s (máximo {float(cap):g} s, max_seconds)"))

    spans = voice_spans(timeline)
    seps = [(float(p["start"]), float(p["start"]) + float(p["duration"])) for p in timeline.get("parts") or []
            if p.get("start") is not None and p.get("duration")]
    gaps = []
    cursor = 0.0
    for start, end in spans + [(total, total)]:
        # P4: a part separator card is shown, not a silence of the voice.
        card = sum(overlap(cursor, start, a, b) for a, b in seps)
        if start - cursor - card > MAX_GAP + EPS:
            gaps.append(f"{fmt_t(cursor)}–{fmt_t(start)} ({start - cursor - card:.1f} s"
                        + (f" sin los {card:.1f} s del separador)" if card > 0 else ")"))
        cursor = max(cursor, end)
    if not spans:
        gaps.append("sin narración")
    rows.append(problems("A2.voice_gaps", "A2", [f"silencio de voz {g}" for g in gaps],
                         f"ninguna pausa de voz > {MAX_GAP:g} s"))
    closing = timeline.get("closing") or {}
    dur = float(closing.get("duration") or 0)
    if not closing and vtype == "TUT":
        rows.append(check("A2.closing_card", "A2/N27", True, "sin tarjeta de cierre: termina en el resultado (N27)"))
    else:
        rows.append(check("A2.closing_card", "A2", 0 < dur <= CLOSING_MAX + EPS,
                          f"tarjeta de cierre {dur:.1f} s (máximo {CLOSING_MAX:g} s)"))
    return rows + check_destination(timeline) + [check_targets(timeline)]


def check_targets(timeline: dict) -> dict:
    """N13: every clicked or highlighted element was visible in its box when recorded (target_ok)."""
    bad, unknown, count = [], [], 0
    for step, ev in timeline_events(timeline):
        if ev.get("type") not in TARGETED:
            continue
        count += 1
        name = f"{step['id']}: {ev.get('type')} en {ev.get('selector') or '?'} ({fmt_t(float(ev['t']))})"
        if ev.get("target_ok") is False:
            bad.append(f"{name} sin elemento visible en su caja (target_ok false)")
        elif ev.get("target_ok") is None:
            unknown.append(name)
    if bad:
        return problems("N13.target", "N13", bad, "")
    if unknown:
        return check("N13.target", "N13", "WARN", f"{len(unknown)} sin target_ok (graba de nuevo): "
                     + "; ".join(unknown[:5]))
    return check("N13.target", "N13", True, f"{count} clics y resaltados sobre elementos visibles")


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


def panel_at(layout: dict, timeline: dict, name: str, t: float) -> dict | None:
    """Source box of surface `name` at t: the layout `surface` item shown then (compose's geometry), else the
    nearest window of it, else compose.surface_geometry from the timeline spec."""
    shown = [it for it in layout.get("items", []) if it.get("kind") == "surface" and it.get("name") == name
             and it.get("box")]
    if shown:
        best = min(shown, key=lambda it: 0.0 if float(it["t0"]) - EPS <= t <= float(it["t1"]) + EPS else
                   min(abs(t - float(it["t0"])), abs(t - float(it["t1"]))))
        return best["box"]
    spec = (timeline.get("surfaces") or {}).get(name)
    if spec and spec.get("size"):
        from compose import surface_geometry
        return surface_geometry(spec)["panel"]
    return None


def place_surfaces(timeline: dict, layout: dict) -> dict:
    """The timeline with surface events (popup px, `surface` key) moved onto their panel in source px, as
    compose draws them; C9/C10 and the other geometric checks then read them as page events."""
    if timeline.get("surfaces_placed") or not any(ev.get("surface") for _, ev in timeline_events(timeline)):
        return timeline
    steps = []
    for step in timeline.get("steps", []):
        events = []
        for ev in step.get("events", []):
            panel = panel_at(layout, timeline, ev["surface"], float(ev["t"])) if ev.get("surface") else None
            if panel is None:
                events.append(ev)
                continue
            moved = dict(ev)
            for key in ("box", "frame_box"):
                if ev.get(key):
                    moved[key] = {**ev[key], "x": ev[key]["x"] + panel["x"], "y": ev[key]["y"] + panel["y"]}
            if ev.get("point"):
                moved["point"] = {"x": ev["point"]["x"] + panel["x"], "y": ev["point"]["y"] + panel["y"]}
            events.append(moved)
        steps.append({**step, "events": events})
    return {**timeline, "steps": steps, "surfaces_placed": True}


def check_layout(layout: dict, timeline: dict, tutorial: dict) -> list[dict]:
    rows = []
    timeline = place_surfaces(timeline, layout)
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

    # R1 / R2: result in detail and clear for ≥ 0.8 s. Only what is drawn over the UI viewport covers it:
    # a caption in the band never does (S1 b).
    base = base_scale(layout, fmt)
    fast = is_fast(timeline)
    detail, detail_max = detail_range(base, fast)
    vp = list(layout.get("viewport") or [0, 0, out_w, out_h])
    results = by_kind.get("result", [])
    r1, r2 = [], []
    for res in results:
        mid = (res["t0"] + res["t1"]) / 2
        scale = camera_scale_at(camera, mid)
        if scale is None or scale < detail - 1e-6:
            r1.append(f"resultado en {fmt_t(mid)} a {scale if scale is not None else '?'}× (detalle ≥ {detail:g}×)")
        shown = clip(res["rect"], vp)
        if shown is None:
            r2.append(f"resultado en {fmt_t(res['t0'])}: {fmt_rect(res['rect'])} fuera de la interfaz {fmt_rect(vp)}")
            continue
        blockers = [(ov["t0"], ov["t1"]) for ov in captions + cursors + chips
                    if (part := clip(ov["rect"], vp)) and intersects(part, shown)]
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

    # C1: wide shots ≤ 1.0 s outside the opening and closing (a form shot is not a wide shot, N10);
    # nothing above the 1.8× ceiling and no form shot below the base scale.
    if not camera:
        rows.append(check("C1.context", "C1", False, "layout.json sin cámara"))
        rows.append(check("C1.zoom", "C1", False, "layout.json sin cámara"))
    else:
        wide = [(float(s["t0"]), float(s["t1"])) for s in camera
                if s.get("kind") != "form" and float(s["scale"]) < detail - 1e-6]
        runs = merge(subtract(merge(wide), excluded))
        long_runs = [f"{fmt_t(a)}–{fmt_t(b)} ({b - a:.1f} s) por debajo de {detail:g}×"
                     for a, b in runs if b - a > CONTEXT_MAX + EPS]
        rows.append(problems("C1.context", "C1", long_runs, f"planos generales ≤ {CONTEXT_MAX:g} s"))
        zoom, usual = [], []
        lo, hi = (max(v, base) for v in (FAST_FORM_USUAL if fast else FORM_USUAL))
        for s in camera:
            sc, t0, t1 = float(s["scale"]), float(s["t0"]), float(s["t1"])
            if not subtract([(t0, t1)], excluded):
                continue
            name = "plano de formulario" if s.get("kind") == "form" else "encuadre"
            if sc > detail_max + 1e-6:
                zoom.append(f"{name} {fmt_t(t0)}–{fmt_t(t1)} a {sc:g}× (máximo {detail_max:g}×)")
            elif s.get("kind") == "form" and sc < base - 1e-6:
                zoom.append(f"{name} {fmt_t(t0)}–{fmt_t(t1)} a {sc:g}×, por debajo de la escala base {base:g}×")
            elif s.get("kind") == "form" and not lo - 1e-6 <= sc <= hi + 1e-6:
                usual.append(f"{name} {fmt_t(t0)}–{fmt_t(t1)} a {sc:g}× (en general {lo:g}–{hi:g}×)")
        if zoom:
            rows.append(problems("C1.zoom", "C1", zoom, ""))
        elif usual:
            rows.append(check("C1.zoom", "C1", "WARN", "; ".join(usual[:5]) + ": revisa que se lea"))
        else:
            rows.append(check("C1.zoom", "C1", True, f"detalle {detail:g}–{detail_max:g}×, formularios ≤ {detail_max:g}×"))

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
    return (rows + check_round_two(layout, timeline, tutorial) + check_round_four(layout, timeline, tutorial)
            + check_reading(layout, timeline))


# ---------- round two: C7-C10, N1-N9 ----------

def base_scale(layout: dict, fmt: str) -> float:
    return float(layout.get("base_scale") or (1920 / 1080 if fmt == "9:16" else 1.0))


def is_fast(timeline: dict) -> bool:
    return timeline.get("pace") == "fast"


def detail_range(base: float, fast: bool = False) -> tuple[float, float]:
    """C1 revised: (floor, ceiling) of the detail zoom for a format whose base scale is `base` (P3: 1.15–1.4×)."""
    low, high = FAST_DETAIL if fast else (DETAIL_MIN, DETAIL_MAX)
    return max(low, base), max(high, base)


def establishing(seg: dict, base: float) -> bool:
    if seg.get("kind") == "form":
        return seg.get("reason") == "establishing"
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
    to = seg_frame(seg)
    fr = seg.get("from")
    if not fr:
        return to
    span = float(seg["t1"]) - float(seg["t0"])
    p = min(max((t - float(seg["t0"])) / span, 0.0), 1.0) if span > 0 else 1.0
    p = ease(p) if seg.get("kind") == "move" else p   # a slow push-in (C8) is linear
    return {k: float(fr[k]) + (to[k] - float(fr[k])) * p for k in ("x", "y", "s")}


def seg_frame(seg: dict) -> dict:
    return {"x": float(seg["x"]), "y": float(seg["y"]), "s": float(seg["scale"])}


def map_box(box: dict, fr: dict) -> list[float]:
    return [box["x"] * fr["s"] + fr["x"], box["y"] * fr["s"] + fr["y"], box["w"] * fr["s"], box["h"] * fr["s"]]


def inside(rect, area, tol: float = FRAME_TOL) -> bool:
    x, y, w, h = rect
    ax, ay, aw, ah = area
    return x >= ax - tol and y >= ay - tol and x + w <= ax + aw + tol and y + h <= ay + ah + tol


def clip(rect, area) -> list[float] | None:
    """The part of rect inside area, or None when they do not intersect."""
    x0, y0 = max(rect[0], area[0]), max(rect[1], area[1])
    x1, y1 = min(rect[0] + rect[2], area[0] + area[2]), min(rect[1] + rect[3], area[1] + area[3])
    return [x0, y0, x1 - x0, y1 - y0] if x1 > x0 and y1 > y0 else None


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


def check_establishing(camera, timeline, base, fmt, excluded, results=()) -> dict:
    """C7: every screen (first step + each screen_at) opens with a ≤ 1.0 s establishing shot. A screen whose
    toast (`result` item) starts within ESTABLISH_WINDOW opens on the toast shot instead (S1 a, N6 > C7); under
    pace fast a whole-form shot within that window is the establishing shot (P3), however long."""
    steps = timeline.get("steps", [])
    if not camera or not steps:
        return check("C7.establishing", "C7", "WARN", "sin cámara o sin pasos")
    end = float(timeline.get("screen_end") or 0) or max(float(s["t1"]) for s in camera)
    starts = [float(steps[0]["start"])] + [t for t in screen_changes(timeline) if t < end and not in_cards(t, excluded)]
    wide = merge([(float(s["t0"]), float(s["t1"])) for s in camera
                  if s.get("kind") != "move" and establishing(s, base)])
    forms = [float(s["t0"]) for s in camera if s.get("kind") == "form"] if is_fast(timeline) else []
    found = []
    for ts in sorted(set(starts)):
        if any(ts - TIME_RES <= float(r["t0"]) <= ts + ESTABLISH_WINDOW + TIME_RES for r in results):
            continue
        if any(ts - TIME_RES <= t <= ts + ESTABLISH_WINDOW + TIME_RES for t in forms):
            continue
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


def same_framing(a: dict, b: dict) -> bool:
    """Same scale and center (C8/N10)."""
    if abs(float(a["scale"]) - float(b["scale"])) > SAME_SCALE or has_offset(a) != has_offset(b):
        return False
    return not has_offset(a) or (abs(float(a["x"]) - float(b["x"])) <= SAME_PX and
                                 abs(float(a["y"]) - float(b["y"])) <= SAME_PX)


def pushes_from(seg: dict, last: dict) -> bool:
    """A slow push-in (C8) that starts where the `last` still segment ends: the same shot."""
    fr = seg.get("from")
    return bool(seg.get("push") and fr) and same_framing({"scale": fr["s"], "x": fr["x"], "y": fr["y"]}, last)


def framings(camera: list[dict], t0: float = float("-inf"), t1: float = float("inf"),
             shots: bool = False) -> list[dict]:
    """Runs {seg, segs, t0, t1} of one still framing (moves split them), optionally only those touching
    t0–t1. A push-in is a visual change (C8) unless `shots`: then it continues the shot it starts from."""
    runs, cur = [], None
    for seg in sorted(camera, key=lambda s: float(s["t0"])):
        joined = cur and abs(float(seg["t0"]) - cur["t1"]) < 0.02
        if seg.get("kind") == "move" or (seg.get("push") and not shots):
            cur = None
            continue
        if joined and (pushes_from(seg, cur["segs"][-1]) if seg.get("push") else
                       same_framing(cur["segs"][-1], seg)):
            cur["t1"] = float(seg["t1"])
            cur["segs"].append(seg)
        else:
            cur = {"seg": seg, "segs": [seg], "t0": float(seg["t0"]), "t1": float(seg["t1"])}
            runs.append(cur)
    return [r for r in runs if r["t1"] > t0 + TIME_RES and r["t0"] < t1 - TIME_RES]


def spot_moves(spots) -> list[tuple[float, float]]:
    """N11 moves of the spotlight: `move` is [start, end] (compose) or its duration ending at t0."""
    out = []
    for s in spots:
        m = s.get("move")
        if isinstance(m, (list, tuple)) and len(m) == 2:
            out.append((float(m[0]), float(m[1])))
        elif isinstance(m, (int, float)) and m > 0:
            out.append((float(s["t0"]) - float(m), float(s["t0"])))
    return out


def spot_jumps(spots) -> list[tuple[float, float]]:
    """Instants where the spotlight appears on another target without a move (N13 waits for the click that
    reveals it): zero-length changes."""
    ordered = sorted(spots, key=lambda s: float(s["t0"]))
    return [(float(b["t0"]), float(b["t0"])) for a, b in zip(ordered, ordered[1:])
            if not b.get("move") and [round(v) for v in a["rect"]] != [round(v) for v in b["rect"]]]


def check_static(camera, vtype, excluded, spots=(), fast: bool = False) -> dict:
    """C8: no identical framing (same scale and center) longer than 4 s in TUT, 3 s otherwise (2.5 s under pace
    fast, P2); a spotlight moving to the next field inside it (N11) is a visual change, and under fast also one
    jumping to another target."""
    limit = FAST_STATIC if fast else STATIC_MAX.get(vtype, STATIC_DEFAULT)
    changes = merge(excluded + spot_moves(spots) + (spot_jumps(spots) if fast else []), gap=0)
    found = [f"{fmt_t(a)}–{fmt_t(b)} ({b - a:.1f} s) con el mismo encuadre"
             for run in framings(camera) for a, b in subtract([(run["t0"], run["t1"])], changes)
             if b - a > limit + EPS]
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
    """N1: the instruction (voice and caption) comes before the action, ≤ 0.3 s after it at most. Under pace fast
    the action is edit's planned one (`action_t`: a one-sentence chain ends with its last action)."""
    found, checked = [], 0
    for step in timeline.get("steps", []):
        acts = [ev for ev in step.get("events", []) if ev.get("type") in ("click", "select")]
        if not acts or not float(step.get("voice_duration") or 0):
            continue
        checked += 1
        t_act = min(float(ev["t"]) for ev in acts)
        if is_fast(timeline) and step.get("action_t") is not None:
            t_act = float(step["action_t"])
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
    edit keeps it on screen (event t–t_end); that window (not its zoom in/out) is exempt from C4."""
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


def same_box(a, b) -> bool:
    return bool(a) and bool(b) and all(abs(float(a[k]) - float(b[k])) <= FRAME_TOL for k in ("x", "y", "w", "h"))


def event_end(ev: dict) -> float:
    t = float(ev["t"])
    return max(t, float(ev.get("t_end") or 0)) if ev.get("type") == "type" else t


def form_runs(timeline: dict, excluded) -> list[dict]:
    """Consecutive events that share a form_box: {form_box, events, fields (type/select), t0, t1}."""
    runs, cur = [], None
    for _, ev in timeline_events(timeline):
        box = ev.get("form_box")
        if not box or in_cards(float(ev["t"]), excluded):
            cur = None
            continue
        if cur is None or not same_box(cur["form_box"], box):
            cur = {"form_box": box, "events": [], "fields": []}
            runs.append(cur)
        cur["events"].append(ev)
        if ev.get("type") in FIELDS:
            cur["fields"].append(ev)
    for run in runs:
        if run["fields"]:
            run["t0"] = float(run["fields"][0]["t"])
            run["t1"] = max(event_end(ev) for ev in run["fields"])
    return [r for r in runs if r["fields"]]


def bare_fields(timeline: dict, excluded) -> int:
    return sum(1 for _, ev in timeline_events(timeline) if ev.get("type") in FIELDS and not ev.get("form_box")
               and not in_cards(float(ev["t"]), excluded))


def check_form_shot(camera, timeline, vp, excluded) -> dict:
    """N10: consecutive fields of one form share one framing (the whole form), or the fewest form shots
    from top to bottom when it does not fit legible."""
    runs = form_runs(timeline, excluded)
    if not runs:
        if bare_fields(timeline, excluded):
            return check("N10.form", "N10", "WARN", "los campos no traen form_box: no puedo comprobar el plano de formulario")
        return check("N10.form", "N10", True, "sin formularios")
    found = []
    for run in [r for r in runs if len(r["fields"]) > 1]:
        shots = framings(camera, run["t0"], run["t1"], shots=True)
        where = f"formulario {fmt_t(run['t0'])}–{fmt_t(run['t1'])} ({len(run['fields'])} campos)"
        if len(shots) <= 1:
            continue
        if any(s["seg"].get("kind") != "form" for s in shots):
            found.append(f"{where}: {len(shots)} encuadres, la cámara se mueve campo por campo "
                         "(usa un plano del formulario completo)")
            continue
        ys = [float(s["seg"]["y"]) for s in shots if has_offset(s["seg"])]
        if len(ys) == len(shots) and any(b >= a - SAME_PX for a, b in zip(ys, ys[1:])):
            found.append(f"{where}: {len(shots)} planos de formulario que no van de arriba hacia abajo")
            continue
        scale = max(float(seg["scale"]) for s in shots for seg in s["segs"])
        need = max(1, -(-(float(run["form_box"]["h"]) * scale - FRAME_TOL) // vp[3]))
        if len(shots) > need:
            found.append(f"{where}: {len(shots)} planos de formulario, alcanzan {need:.0f} a {scale:g}×")
    return problems("N10.form", "N10", found, f"{len(runs)} formularios con un plano estable")


def check_spotlight(spots, camera, timeline, tutorial, excluded) -> dict:
    """N11: a brand-colored spotlight (dim ≤ 25 %) on every field of a form while it is used, moving
    250–400 ms from field to field."""
    fields = [ev for run in form_runs(timeline, excluded) for ev in run["fields"]]
    if not fields:
        return check("N11.spotlight", "N11", True, "sin formularios")
    brand = tutorial.get("brand") or {}
    palette = [c for k in BRAND_KEYS if (c := rgb(brand.get(k) or ""))]
    found, unknown = [], []
    for ev in fields:
        t, end = float(ev["t"]), event_end(ev)
        cover = [s for s in spots if float(s["t0"]) <= t + TIME_RES and float(s["t1"]) >= end - TIME_RES]
        if not cover:
            found.append(f"{ev.get('selector', '')} en {fmt_t(t)} sin recuadro (spotlight)")
            continue
        box = ev.get("box") or ev.get("frame_box")
        if box and not any(outlines(s, box, camera) for s in cover):
            found.append(f"{ev.get('selector', '')} en {fmt_t(t)}: el recuadro no rodea el campo")
    ordered = sorted(spots, key=lambda s: float(s["t0"]))
    for i, spot in enumerate(ordered):
        name = f"recuadro {fmt_t(float(spot['t0']))}"
        if "dim" not in spot:
            unknown.append(f"{name} sin dim")
        elif float(spot["dim"]) > SPOT_DIM_MAX + 1e-6:
            found.append(f"{name} oscurece {float(spot['dim']):.0%} (máximo {SPOT_DIM_MAX:.0%})")
        color = spot.get("color")
        if not color or rgb(color) is None:
            unknown.append(f"{name} sin color")
        elif palette and (palette_issue(color, palette) or neutral(rgb(color))):
            found.append(f"{name} {color.lower()}: no es un color de la marca")
        own = spot_moves([spot])
        if own:
            dur = own[0][1] - own[0][0]
            if not SPOT_MOVE[0] - 1e-6 <= dur <= SPOT_MOVE[1] + 1e-6:
                found.append(f"{name} se desplaza en {dur:.2f} s ({SPOT_MOVE[0]:g}–{SPOT_MOVE[1]:g} s)")
        elif i and float(ordered[i - 1]["t1"]) >= float(spot["t0"]) - SPOT_MOVE[1] - EPS and \
                ordered[i - 1].get("group") == spot.get("group"):
            unknown.append(f"{name} sin duración del desplazamiento (move)")
    if found:
        return problems("N11.spotlight", "N11", found, "")
    if unknown:
        return check("N11.spotlight", "N11", "WARN", "; ".join(unknown[:5]) + ": compose no lo registró")
    return check("N11.spotlight", "N11", True, f"{len(fields)} campos con recuadro de la marca")


def outlines(spot: dict, box: dict, camera) -> bool:
    """The spotlight surrounds the field: its source `box` (compose) or its rect at t0 in output px."""
    if spot.get("box"):
        b = spot["box"]
        return inside([box["x"], box["y"], box["w"], box["h"]], [b["x"], b["y"], b["w"], b["h"]])
    fr = frame_at(camera, float(spot["t0"]))
    return fr is None or inside(map_box(box, fr), spot["rect"])


def check_form_fields(camera, timeline, vp, excluded, base: float = 1.0) -> dict:
    """N12/V2: while a form is framed, every field of it (neighbors too, not only the active one) and the
    form's width are inside the viewport; a field may only be left out above/below in a split form. Under pace
    fast a form wider than the viewport at the base scale is cropped beyond its used fields (P3)."""
    runs = form_runs(timeline, excluded)
    if not runs:
        return check("N12.form_fields", "N12/V2", True, "sin formularios")
    found, blind = [], False
    for run in runs:
        shots = framings(camera, run["t0"], run["t1"], shots=True)
        split = len(shots) > 1 and all(s["seg"].get("kind") == "form" for s in shots)
        boxes = [(ev.get("selector", ""), ev.get("frame_box") or ev.get("box")) for ev in run["events"]]
        for shot in shots:
            if not all(has_offset(seg) for seg in shot["segs"]):
                blind = True
                continue
            # Frames are linear between a push-in's ends: checking both ends covers the whole shot.
            ends = [seg_frame(seg) for seg in shot["segs"]] + [
                {k: float(seg["from"][k]) for k in ("x", "y", "s")} for seg in shot["segs"] if seg.get("push")]
            when = f"{fmt_t(shot['t0'])}–{fmt_t(shot['t1'])}"
            wide = is_fast(timeline) and float(run["form_box"]["w"]) * base > vp[2] + FRAME_TOL
            for fr in ends:
                found += fields_cut(run, boxes, fr, vp, split, when, wide)
    if found:
        return problems("N12.form_fields", "N12/V2", list(dict.fromkeys(found)), "")
    if blind:
        return check("N12.form_fields", "N12/V2", "WARN", "cámara sin x/y: no puedo medir los campos del formulario")
    return check("N12.form_fields", "N12/V2", True, f"{len(runs)} formularios con todos sus campos dentro")


def fields_cut(run, boxes, fr, vp, split, when, wide: bool = False) -> list[str]:
    """N12/V2 at one framing: the form fits across the width (unless it is `wide`: wider than the viewport, P3)
    and no field of it is cut."""
    found = []
    vx, vy, vw, vh = vp
    form = map_box(run["form_box"], fr)
    if not wide and (form[0] < vx - FRAME_TOL or form[0] + form[2] > vx + vw + FRAME_TOL):
        found.append(f"{when}: el formulario {fmt_rect(form)} no entra a lo ancho en {fmt_rect(vp)}")
    for selector, box in boxes:
        if not box:
            continue
        rect = map_box(box, fr)
        if inside(rect, vp):
            continue
        side = rect[0] + rect[2] <= vx or rect[0] >= vx + vw
        if not side and not intersects(rect, vp) and split:
            continue  # shown in the other shot of the split form
        found.append(f"{selector} {when}: {fmt_rect(rect)} cortado fuera del encuadre {fmt_rect(vp)}")
    return found


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
    spots = by_kind.get("spotlight", [])
    rows = [check_establishing(camera, timeline, base_scale(layout, fmt), fmt, excluded, by_kind.get("result", [])),
            check_static(camera, timeline.get("type", "TUT"), excluded, spots, is_fast(timeline)),
            check_in_frame(actives, camera, timeline, vp, excluded)]
    rows += check_clicks(actives, camera, timeline, vp, excluded)
    rows.append(check_sync(captions, timeline))
    rows += check_texts(by_kind.get("chip", []), captions, items, timeline)
    rows.append(check_band(captions, by_kind.get("band", []), vp))
    rows.append(check_palette(items, tutorial))
    rows.append(check_results(by_kind.get("result", []), timeline))
    if fmt == "9:16":
        rows.append(check_vertical(camera, timeline, layout, vp, excluded))
    rows += [check_form_shot(camera, timeline, vp, excluded),
             check_spotlight(spots, camera, timeline, tutorial, excluded),
             check_form_fields(camera, timeline, vp, excluded, base_scale(layout, fmt))]
    return rows


# ---------- round four: N14-N24 (Parte 6) ----------

def caption_text(cap: dict) -> str:
    return str(cap.get("text") or " ".join(cap.get("lines") or [])).strip()


def follow_spans(timeline: dict) -> list[tuple[float, float]]:
    """Times on a tab adopted with `follow: tab` (recorder goto events tab follow → main)."""
    spans, start = [], None
    for _, ev in timeline_events(timeline):
        if ev.get("tab") == "follow" and start is None:
            start = float(ev["t"])
        elif ev.get("tab") == "main" and start is not None:
            spans.append((start, float(ev["t"])))
            start = None
    if start is not None:
        spans.append((start, float(timeline.get("screen_end") or timeline.get("total") or start)))
    return spans


def windows(items) -> list[tuple[float, float]]:
    return [(float(it["t0"]), float(it["t1"])) for it in items]


def evidence(by_kind: dict, timeline: dict) -> dict[str, list[tuple[float, float]] | None]:
    """N14: when each kind of named thing is on screen; None when the video gives no way to know."""
    surfaces = by_kind.get("surface", [])
    tabs = follow_spans(timeline)
    marked = [(float(ev["t"]), max(float(ev.get("t_end") or 0), float(ev["t"]) + MIN_RESULT))
              for _, ev in timeline_events(timeline) if ev.get("type") in ("highlight", "result")
              and re.search(r"\bcambiar\b", str(ev.get("target_text") or ""), re.I)]
    results = by_kind.get("result", [])
    # The summary of an extension is its result inside the surface, not a result of the page (the table).
    in_surface = {(step["id"], ev.get("selector")) for step, ev in timeline_events(timeline)
                  if ev.get("type") == "result" and ev.get("surface")}
    summaries = [r for r in results if (r.get("step"), r.get("selector")) in in_surface] if in_surface else results
    shown = results + by_kind.get("highlight", [])
    return {"surface": windows(surfaces) if surfaces or timeline.get("surfaces") else None,
            "tab": tabs + marked if tabs or marked else None,
            "summary": windows(summaries) if results else None,
            "list": windows(shown) if shown else None}


def check_named(captions, by_kind, timeline) -> dict:
    """N14: while a caption names Perseo, the settings, Cambiar, the summary or the list, it is on screen (an
    instruction may name it up to NAMED_LEAD s before it appears). I1: in a `chrome` step (Google, the store)
    "Perseo" is the typed query or the listing, not the popup: the timeline cannot prove it, the snapshots must."""
    proof = evidence(by_kind, timeline)
    browser = {s["id"] for s in timeline.get("steps", []) if s.get("context") == "chrome"}
    found, unknown, named = [], [], 0
    for cap in captions:
        text = caption_text(cap)
        t0, t1 = float(cap["t0"]), float(cap["t1"])
        lead = NAMED_LEAD if INSTRUCTION.search(text) else 0.0
        for word, pattern, kind in MENTIONS:
            if not pattern.search(text):
                continue
            named += 1
            spans = proof[kind]
            if kind == "surface" and cap.get("step") in browser:
                unknown.append(f"«{text}» nombra {word} en Chrome")
            elif spans is None:
                unknown.append(f"«{text}» nombra {word}")
            elif not any(overlap(t0, t1 + lead, a, b) > EPS for a, b in spans):
                found.append(f"«{text}» ({fmt_t(t0)}–{fmt_t(t1)}) nombra {word}, que no está en pantalla")
    if found:
        return problems("N14.named", "N14", found, "")
    if unknown:
        return check("N14.named", "N14", "WARN", "; ".join(unknown[:5]) + ": no puedo saber si se ve, revisa las capturas")
    return check("N14.named", "N14", True, f"{named} menciones con lo nombrado en pantalla")


def check_parts(chips, by_kind, timeline) -> dict:
    """N16: with parts, a separator «Parte N» before each part and chips «Parte N · Paso M»."""
    parts = timeline.get("parts") or []
    if not parts:
        return check("N16.parts", "N16", True, "sin partes")
    steps = timeline.get("steps", [])
    separators = separator_items(by_kind)
    found = []
    for part in parts:
        n = part.get("n")
        own = [s for s in steps if s.get("part") == n]
        start = float(own[0]["start"]) if own else float(part.get("start") or 0)
        sep = [it for it in separators if re.search(rf"\bParte {n}\b", str(it.get("text") or ""))]
        if not sep:
            found.append(f"parte {n} sin separador «Parte {n}: {part.get('title', '')}»")
        elif min(float(it["t0"]) for it in sep) > start + EPS:
            found.append(f"el separador de la parte {n} llega después de su primer paso ({fmt_t(start)})")
        for m, step in enumerate(own, 1):
            chip = next((c for c in chips if c.get("step") == step["id"]), None)
            got = PART_CHIP.match(str(chip.get("text") or "").strip()) if chip else None
            if chip and not (got and int(got.group(1)) == n and int(got.group(2)) in (m, step.get("number"))):
                found.append(f"{step['id']}: etiqueta «{chip.get('text', '')}» (tiene que ser «Parte {n} · Paso {m}»)")
    return problems("N16.parts", "N16", found, f"{len(parts)} partes con separador y etiqueta «Parte N · Paso M»")


def separator_items(by_kind: dict) -> list[dict]:
    """N16 separator cards: `separator` items or compose's `card` items of a part (card "part-N")."""
    return by_kind.get("separator", []) + [it for it in by_kind.get("card", [])
                                           if str(it.get("card") or "").startswith("part-")]


def expected_contexts(timeline: dict, step: dict) -> list[tuple[float, float, str]]:
    """N17: (t0, t1, context) of a step: its declared context, else extension while a surface is open and the
    page the rest of the time."""
    s0, s1 = float(step["start"]), float(step["start"]) + float(step["duration"])
    if step.get("context"):
        return [(s0, s1, str(step["context"]))]
    opened = [(max(float(a), s0), min(float(b), s1)) for spec in (timeline.get("surfaces") or {}).values()
              for a, b in spec.get("windows") or [] if float(a) < s1 and float(b) > s0]
    return sorted([(a, b, "page") for a, b in subtract([(s0, s1)], opened)] +
                  [(a, b, "extension") for a, b in opened if b > a])


def same_hue(a, b) -> bool:
    if neutral(a) or neutral(b):
        return False
    diff = abs(colorsys.rgb_to_hls(*a)[0] - colorsys.rgb_to_hls(*b)[0]) * 360 % 360
    return min(diff, 360 - diff) <= HUE_TOL


def check_context(by_kind, timeline, tutorial) -> dict:
    """N17: when the video has contexts (surfaces or declared ones), a badge says where the user works over
    every step; the brand color only for the extension, a neutral one for the page (SRI)."""
    badges = [it for k in BADGES for it in by_kind.get(k, [])]
    steps = timeline.get("steps", [])
    if not badges:
        if timeline.get("surfaces") or any(s.get("context") for s in steps):
            return check("N17.context", "N17", "WARN", "layout.json sin indicador de contexto: revisa las capturas")
        return check("N17.context", "N17", True, "sin contextos (ni superficies ni context en los pasos)")
    primary = rgb((tutorial.get("brand") or {}).get("primary") or "")
    found, unknown = [], []
    same = lambda want, got: got == want or (want in ("page", "sri") and got in ("page", "sri"))  # noqa: E731
    for step in steps:
        own = [b for b in badges if b.get("step") == step["id"]]
        if not own:
            found.append(f"{step['id']}: sin indicador de contexto")
            continue
        for a, b, want in expected_contexts(timeline, step):
            if b - a < MIN_CAPTION / 4:
                continue
            mid = (a + b) / 2
            if not any(same(want, str(x.get("context") or "")) and float(x["t0"]) - EPS <= mid <= float(x["t1"]) + EPS
                       for x in own):
                found.append(f"{step['id']}: en {fmt_t(mid)} se trabaja en «{want}» y el indicador no lo dice")
        for badge in own:
            got = str(badge.get("context") or "")
            color = rgb(str(badge.get("color") or badge.get("background") or ""))
            if color is None or primary is None:
                unknown.append(f"{step['id']}: sin color" if color is None else "tutorial.yaml sin brand.primary")
            elif got == "extension" and not same_hue(color, primary):
                found.append(f"{step['id']}: el indicador de la extensión no usa el color de la marca")
            elif got != "extension" and same_hue(color, primary):
                found.append(f"{step['id']}: el indicador «{got}» usa el color de la marca (solo para la extensión)")
    if found:
        return problems("N17.context", "N17", found, "")
    if unknown:
        return check("N17.context", "N17", "WARN", "; ".join(list(dict.fromkeys(unknown))[:5]))
    return check("N17.context", "N17", True, f"{len(steps)} pasos con su indicador de contexto")


def check_downloads(by_kind, timeline) -> dict:
    """N18: after each download (a click on a download button of a surface) its summary is shown."""
    found, unknown, count = [], [], 0
    for step in timeline.get("steps", []):
        events = sorted(step.get("events", []), key=lambda e: float(e["t"]))
        for ev in events:
            if ev.get("type") != "click" or not ev.get("surface"):
                continue
            label = str(ev.get("target_text") or "")
            if not label:
                unknown.append(f"{step['id']}: {ev.get('selector', '')} sin target_text")
                continue
            if not DOWNLOAD.search(label) or NOT_DOWNLOAD.search(label):
                continue
            count += 1
            t = float(ev["t"])
            shown = [r for r in by_kind.get("result", []) if r.get("step", step["id"]) == step["id"]
                     and float(r["t0"]) >= t - EPS]
            summary = [e for e in events if e.get("type") == "result" and e.get("surface") == ev["surface"]
                       and float(e["t"]) > t]
            if not summary or not shown:
                found.append(f"{step['id']}: la descarga «{label}» ({fmt_t(t)}) no muestra el resumen de la extensión")
    if found:
        return problems("N18.download", "N18", found, "")
    if unknown:
        return check("N18.download", "N18", "WARN", "; ".join(unknown[:5]) + ": no puedo saber si descarga")
    return check("N18.download", "N18", True, f"{count} descargas con su resumen" if count else "sin descargas")


def check_sentences(captions) -> dict:
    """N19: a caption block = one sentence; a long one may be split by clauses only when the blocks share its
    `sentence` index, and never across steps."""
    found, unknown = [], []
    ordered = sorted(captions, key=lambda c: float(c["t0"]))
    for i, cap in enumerate(ordered):
        text = caption_text(cap)
        if INNER_SENTENCE.search(text):
            found.append(f"«{text}» tiene más de una oración")
            continue
        if SENTENCE_END.search(text):
            continue
        nxt = ordered[i + 1] if i + 1 < len(ordered) else None
        if cap.get("sentence") is None:
            unknown.append(f"«{text}»")
        elif not (nxt and nxt.get("step") == cap.get("step") and nxt.get("sentence") == cap["sentence"]):
            found.append(f"«{text}» corta la oración")
    if found:
        return problems("N19.sentence", "N19", found, "")
    if unknown:
        return check("N19.sentence", "N19", "WARN", "sin punto final ni índice de oración (sentence): "
                     + "; ".join(unknown[:5]))
    return check("N19.sentence", "N19", True, f"{len(captions)} subtítulos de una oración")


def check_scale(camera, layout, timeline, vp, excluded) -> dict:
    """N20: no pillarbox (the source always covers the viewport width), legible scale (the establishing shot
    may go below it ≤ 1.0 s) and no zoom jump > 0.35 inside a step without a cut."""
    src_w = float((timeline.get("source") or [1920, 1080])[0])
    cover = vp[2] / src_w
    floor = legible_floor(layout, timeline.get("format", "16:9"))
    found = []
    for seg in camera:
        t0, t1 = float(seg["t0"]), float(seg["t1"])
        shown = subtract([(t0, t1)], excluded)
        if not shown:
            continue
        scales = [float(seg["scale"])] + ([float(seg["from"]["s"])] if seg.get("from") else [])
        when = f"{fmt_t(t0)}–{fmt_t(t1)}"
        if min(scales) < cover - 1e-6:
            found.append(f"{when} a {min(scales):g}× deja franjas negras (mínimo {cover:g}×)")
            continue
        if floor is None or seg.get("kind") == "move" or min(scales) >= floor - 1e-6:
            continue
        span = sum(b - a for a, b in shown)
        if not establishing(seg, base_scale(layout, timeline.get("format", "16:9"))) or span > ESTABLISH_MAX + EPS:
            found.append(f"{when} a {min(scales):g}×, por debajo de la escala legible {floor:g}×")
    for step in timeline.get("steps", []):
        s0, s1 = float(step["start"]), float(step["start"]) + float(step["duration"])
        for k, seg in enumerate(camera):
            if not (seg.get("kind") == "move" or seg.get("push")) or float(seg["t0"]) < s0 - EPS or \
                    float(seg["t1"]) > s1 + EPS or in_cards(float(seg["t0"]), excluded):
                continue
            prev = camera[k - 1] if k else None
            if seg.get("kind") == "move" and prev and establishing(prev, base_scale(layout, timeline.get("format", "16:9"))):
                continue   # leaving the establishing shot (C7)
            start = float(seg["from"]["s"]) if seg.get("from") else float(prev["scale"]) if prev else None
            if start is not None and abs(float(seg["scale"]) - start) > SCALE_JUMP + 1e-6:
                found.append(f"{step['id']}: salto de zoom {start:g}× → {float(seg['scale']):g}× en "
                             f"{fmt_t(float(seg['t0']))} (máximo {SCALE_JUMP:g} sin corte)")
    if found:
        return problems("N20.scale", "N20", found, "")
    if floor is None:
        return check("N20.scale", "N20", "WARN", f"sin franjas (≥ {cover:g}×) y sin saltos; layout.json sin "
                     "legible_scale: revisa que la letra de la interfaz se lea")
    return check("N20.scale", "N20", True, f"sin franjas (≥ {cover:g}×), legible (≥ {floor:g}×), sin saltos de zoom")


def legible_floor(layout: dict, fmt: str) -> float | None:
    """N20: the legible scale layout.json records, else compose's floor for the format (never below its base
    scale); None when neither says it."""
    floor = next((float(layout[k]) for k in LEGIBLE_KEYS if layout.get(k) is not None), None)
    spec = FRAMES.get(fmt) or {}
    if floor is None and "legible" in spec:
        floor = max(float(spec["legible"] or 0), base_scale(layout, fmt))
    return floor


def check_band_height(layout, by_kind, out_h) -> dict:
    """N21: the caption band takes at most 1/8 of the height (135 px at 1080)."""
    rect = layout.get("band") or next((b["rect"] for b in by_kind.get("band", [])), None)
    limit = out_h * BAND_SHARE
    if not rect:
        return check("N21.band", "N21", "WARN", "layout.json sin banda: no puedo medirla")
    return check("N21.band", "N21", float(rect[3]) <= limit + 0.5,
                 f"banda de {float(rect[3]):g} px (máximo {limit:g} px, 1/8 del alto)")


def check_surfaces_inside(by_kind, camera, vp, excluded) -> dict:
    """N22: an open surface panel is whole inside the viewport the whole time it is shown."""
    surfaces = by_kind.get("surface", [])
    found = []
    for it in surfaces:
        t0, t1 = float(it["t0"]), float(it["t1"])
        cuts = sorted({t0, t1 - TIME_RES} | {float(s[k]) for s in camera for k in ("t0", "t1")
                                            if t0 < float(s[k]) < t1})
        moments = sorted(set(cuts) | {(a + b) / 2 for a, b in zip(cuts, cuts[1:])})
        for t in moments:
            if in_cards(t, excluded):
                continue
            fr = frame_at(camera, t)
            rect = map_box(it["box"], fr) if fr and it.get("box") else it.get("rect")
            if rect and not inside(rect, vp):
                found.append(f"{it.get('name', 'superficie')} en {fmt_t(t)}: {fmt_rect(rect)} cortada por el "
                             f"borde del encuadre {fmt_rect(vp)}")
                break
    return problems("N22.surface", "N22", found,
                    f"{len(surfaces)} ventanas de la extensión completas" if surfaces else "sin superficies")


def check_logo(by_kind, layout) -> dict:
    """N24: the logo on the cards is legible (contrast ≥ 3:1 against its card): `logo` items or compose's
    layout `logo` {variant, contrast}."""
    logos = by_kind.get("logo", []) + ([{"t0": 0.0, **layout["logo"]}] if isinstance(layout.get("logo"), dict) else [])
    if not logos:
        return check("N24.logo", "N24", True, "sin logo")
    low = [f"logo en {fmt_t(float(it['t0']))} con contraste {float(it['contrast']):.1f}:1"
           for it in logos if it.get("contrast") is not None and float(it["contrast"]) < LOGO_CONTRAST]
    if low:
        return problems("N24.logo", "N24", low, "")
    if any(it.get("contrast") is None for it in logos):
        return check("N24.logo", "N24", "WARN", "compose no registró el contraste del logo: revisa las capturas")
    return check("N24.logo", "N24", True, f"logo con contraste ≥ {LOGO_CONTRAST:g}:1")


def check_round_four(layout: dict, timeline: dict, tutorial: dict) -> list[dict]:
    fmt = timeline.get("format", "16:9")
    out_w, out_h = layout.get("output") or SIZES.get(fmt, (1920, 1080))
    vp = list(layout.get("viewport") or [0, 0, out_w, out_h])
    by_kind = {}
    for it in layout.get("items", []):
        by_kind.setdefault(it.get("kind"), []).append(it)
    camera = sorted(layout.get("camera") or [], key=lambda s: float(s["t0"]))
    excluded = cards(timeline)
    captions = by_kind.get("caption", [])
    return [check_named(captions, by_kind, timeline),
            check_parts(by_kind.get("chip", []), by_kind, timeline),
            check_context(by_kind, timeline, tutorial),
            check_downloads(by_kind, timeline),
            check_sentences(captions),
            check_scale(camera, layout, timeline, vp, excluded),
            check_band_height(layout, by_kind, out_h),
            check_surfaces_inside(by_kind, camera, vp, excluded),
            check_logo(by_kind, layout)]


def check_reading(layout: dict, timeline: dict) -> list[dict]:
    """P4: every text on screen lasts the time to read it. A caption or a chip under a card (a part separator)
    is not visible, so only its time outside the cards counts."""
    items = layout.get("items", [])
    covers = merge(sorted((float(i["t0"]), float(i["t1"])) for i in items if i.get("kind") in ("card", "title")))

    def visible(it) -> float:
        t0, t1 = float(it["t0"]), float(it["t1"])
        return (t1 - t0) - sum(overlap(t0, t1, a, b) for a, b in covers)

    tol = 2 * TIME_RES
    captions = [i for i in items if i.get("kind") == "caption"]
    short = [f"«{c.get('text', '')}» {visible(c):.2f} s visible (mínimo {reading_seconds(c.get('text', '')):.2f} s)"
             for c in captions if visible(c) < reading_seconds(c.get("text", "")) - tol]
    seps = separator_items({"card": [i for i in items if i.get("kind") == "card"],
                            "separator": [i for i in items if i.get("kind") == "separator"]})
    quick = [f"«{s.get('text', '')}» {float(s['t1']) - float(s['t0']):.2f} s (mínimo {PART_SECONDS:g} s)"
             for s in seps if float(s["t1"]) - float(s["t0"]) < PART_SECONDS - tol]
    chips = [i for i in items if i.get("kind") == "chip"]
    flips = [f"«{c.get('text', '')}» {visible(c):.2f} s antes de cambiar (mínimo {CHIP_MIN:g} s)"
             for c in chips if visible(c) < CHIP_MIN - tol]
    return [problems("P4.captions", "P4", short, f"{len(captions)} subtítulos visibles ≥ caracteres/15 + 0.4 s "
                                                 f"(mínimo 1.5 s)"),
            problems("P4.separators", "P4", quick, f"{len(seps)} separadores ≥ {PART_SECONDS:g} s"),
            problems("P4.chips", "P4", flips, f"{len(chips)} etiquetas de paso visibles ≥ {CHIP_MIN:g} s")]


def c4_ranges(timeline: dict, layout: dict | None) -> list[tuple[float, float]]:
    """Where C4 applies: outside the cards and the R2 result windows themselves (N6: R2 wins over C4).
    The zoom in/out around a result (`exempt`) is checked: a near-empty frame after a screen change and
    before the toast cut is a C4 failure (S1 a)."""
    total = float(timeline.get("total") or 0)
    if layout:
        windows = [(float(r["t0"]), float(r["t1"])) for r in layout.get("items", []) if r.get("kind") == "result"]
        windows += [(float(r["t0"]), float(r["t1"])) for r in layout.get("items", [])
                    if r.get("kind") == "separator" or str(r.get("card") or "").startswith("part-")]   # N16 cards
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
    """(integrated LUFS, true peak dBTP) with ffmpeg ebur128 (common.measure_loudness, shared with tts D5)."""
    return measure_loudness(path)


def check_loudness(path: Path) -> list[dict]:
    lufs, peak = loudness(path)
    return [check("A1.loudness", "A1", abs(lufs - LOUDNESS_TARGET) <= LOUDNESS_TOLERANCE,
                  f"{lufs:.1f} LUFS (objetivo {LOUDNESS_TARGET:g} ±{LOUDNESS_TOLERANCE:g})"),
            check("A1.true_peak", "A1", peak < TRUE_PEAK_MAX, f"pico {peak:.1f} dBTP (< {TRUE_PEAK_MAX:g} dBTP)")]


# D5: one voice tone. Each clip's mean F0 and loudness against the video median. A clip over TONE_SEMITONES warns
# (listen to it); over TONE_FAIL fails: one Gemini request read in one go (perseo-xml-v3, 16 clips) already spans
# -2.6..+3.3 st by intonation alone (short phrases sit higher), so only a jump beyond that is another tone.
TONE_SEMITONES, TONE_FAIL, TONE_LU = 2.0, 4.0, 3.0
PITCH_RATE, PITCH_FRAME, PITCH_HOP, PITCH_RANGE = 16000, 0.04, 0.01, (70.0, 400.0)


def clip_samples(path: Path, rate: int = PITCH_RATE) -> np.ndarray:
    """Mono float samples of an audio file at `rate` (ffmpeg decodes any clip format)."""
    out = subprocess.run([which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-i", str(path), "-ac", "1",
                          "-ar", str(rate), "-f", "f32le", "-"], capture_output=True, check=False)
    if out.returncode != 0:
        raise PipelineError(f"No pude leer {Path(path).name} (ffmpeg)")
    return np.frombuffer(out.stdout, dtype=np.float32)


def clip_pitch(path: Path) -> float | None:
    """Median F0 (Hz) of the voiced frames of a clip (autocorrelation per frame), None when nothing is voiced."""
    x = clip_samples(path)
    n, hop = int(PITCH_FRAME * PITCH_RATE), int(PITCH_HOP * PITCH_RATE)
    if len(x) < n:
        return None
    frames = np.lib.stride_tricks.sliding_window_view(x, n)[::hop]
    rms = np.sqrt((frames ** 2).mean(axis=1))
    loud = frames[rms > max(rms.max() * 0.25, 1e-4)]
    lo, hi = int(PITCH_RATE / PITCH_RANGE[1]), int(PITCH_RATE / PITCH_RANGE[0])
    f0 = []
    window = np.hanning(n)
    for frame in loud:
        f = (frame - frame.mean()) * window
        spec = np.fft.rfft(f, 2 * n)
        acf = np.fft.irfft(spec * np.conj(spec))[:n]
        if acf[0] <= 0:
            continue
        acf = acf / acf[0]
        part = acf[lo:hi]
        best = part.max()
        if best < 0.5:
            continue   # unvoiced
        # The first local peak close to the best one: multiples of the period peak as high (octave errors).
        peaks = [i for i in range(1, len(part) - 1) if part[i] >= part[i - 1] and part[i] >= part[i + 1]
                 and part[i] >= 0.9 * best]
        lag = lo + (peaks[0] if peaks else int(part.argmax()))
        if 0 < lag < n - 1:   # parabolic refinement
            a, b, c = acf[lag - 1], acf[lag], acf[lag + 1]
            den = a - 2 * b + c
            lag = lag + (0.5 * (a - c) / den if den else 0.0)
        f0.append(PITCH_RATE / lag)
    return float(np.median(f0)) if f0 else None


def voice_clips(pdir: Path, vid: str) -> list[tuple[str, Path]]:
    """(name, wav) of every narrated clip of a video, in durations.json order (tts writes it)."""
    vdir = pdir / "audio" / "voice" / vid
    path = vdir / "durations.json"
    if not path.exists():
        return []
    return [(name, vdir / f"{name}.wav") for name, seconds in read_json(path).items()
            if seconds and (vdir / f"{name}.wav").exists()]


def check_voice_tone(clips: list[tuple[str, Path]]) -> list[dict]:
    """D5: each clip's mean F0 within TONE_SEMITONES and its loudness within TONE_LU of the video median."""
    if not clips:
        return [check("D5.pitch", "D5", "WARN", "sin clips de voz (corre tts)")]
    pitch = {name: clip_pitch(path) for name, path in clips}
    level = {name: measure_loudness(path)[0] for name, path in clips}
    rows = []
    voiced = {k: v for k, v in pitch.items() if v}
    if voiced:
        mid = float(np.median(list(voiced.values())))
        dev = {k: 12 * np.log2(v / mid) for k, v in voiced.items()}
        off = [f"{k} {d:+.1f} st" for k, d in dev.items() if abs(d) > TONE_SEMITONES]
        worst = max(abs(d) for d in dev.values())
        spread = f"mediana {mid:.0f} Hz, {min(dev.values()):+.1f}..{max(dev.values()):+.1f} st en {len(dev)} clips"
        mute = [k for k, v in pitch.items() if not v]
        detail = spread + (f"; sin tono medible: {', '.join(mute)}" if mute else "")
        status = "FAIL" if worst > TONE_FAIL else "WARN" if off else "PASS"
        rows.append(check("D5.pitch", "D5", status, ("; ".join(off) + f" (aviso > ±{TONE_SEMITONES:g} st, falla > "
                                                     f"±{TONE_FAIL:g} st; {spread})") if off else detail))
    else:
        rows.append(check("D5.pitch", "D5", "WARN", "ningún clip con tono medible"))
    finite = {k: v for k, v in level.items() if np.isfinite(v) and v > -70}
    if finite:
        mid = float(np.median(list(finite.values())))
        dev = {k: v - mid for k, v in finite.items()}
        off = [f"{k} {d:+.1f} LU" for k, d in dev.items() if abs(d) > TONE_LU]
        spread = f"mediana {mid:.1f} LUFS, {min(dev.values()):+.1f}..{max(dev.values()):+.1f} LU"
        rows.append(check("D5.loudness", "D5", not off, ("; ".join(off) + f" (máximo ±{TONE_LU:g} LU; {spread})")
                          if off else spread))
    else:
        rows.append(check("D5.loudness", "D5", "WARN", "clips en silencio (tts --offline)"))
    return rows


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


def empty_tiles(frame: np.ndarray) -> np.ndarray:
    """Rows x columns of TILE×TILE tiles: True where the tile is uniform AND the frame's background colour."""
    h, w = frame.shape[0] // TILE, frame.shape[1] // TILE
    tiles = frame[:h * TILE, :w * TILE].reshape(h, TILE, w, TILE, 3).transpose(0, 2, 1, 3, 4)
    tiles = tiles.reshape(h, w, TILE * TILE, 3)
    flat = tiles.std(axis=2).max(axis=-1) < TILE_STD
    if not flat.any():
        return flat
    mean = tiles.mean(axis=2)
    keys, counts = np.unique(np.round(mean[flat] / 8), axis=0, return_counts=True)
    background = keys[counts.argmax()] * 8
    return flat & (np.abs(mean - background).max(axis=-1) < BG_DIST)


def empty_ratio(frame: np.ndarray) -> float:
    """Share of TILE×TILE tiles that are uniform AND the frame's background colour."""
    return float(empty_tiles(frame).mean())


def blank_below_header(frame: np.ndarray, vp) -> float:
    """N26: empty share of the viewport below its header strip when nothing but the header has content (a page
    that has not loaded); 0.0 for a page with content below HEADER_MAX, however sparse."""
    x, y, w, h = vp
    region = frame[y + int(h * HEADER_SHARE):y + h, x:x + w]
    if region.shape[0] < TILE or region.shape[1] < TILE:
        return 0.0
    empty = empty_tiles(region)
    below = max(0, int(h * HEADER_MAX) - int(h * HEADER_SHARE)) // TILE
    if ((~empty[below:]).sum(axis=1) >= ROW_INK).any():
        return 0.0
    return float(empty.mean())


def half_changes(prev: np.ndarray, frame: np.ndarray, vp) -> tuple[float, float]:
    """N26: mean change of the top and bottom halves of the viewport between two samples."""
    x, y, w, h = vp
    a, b = prev[y:y + h, x:x + w], frame[y:y + h, x:x + w]
    mid = h // 2
    return float(np.abs(a[:mid] - b[:mid]).mean()), float(np.abs(a[mid:] - b[mid:]).mean())


def check_empty_frames(path: Path, ranges, size, viewport=None) -> list[dict]:
    w, h = (int(size[0]) // SAMPLE_DIV, int(size[1]) // SAMPLE_DIV)
    vp = [int(round(v / SAMPLE_DIV)) for v in (viewport or [0, 0, size[0], size[1]])]
    bad, mixed, sampled = [], [], 0
    for a, b in ranges:
        if b - a <= 0:
            continue
        res = subprocess.run([which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-ss", f"{a:.3f}",
                              "-t", f"{b - a:.3f}", "-i", str(path), "-vf", f"fps={SAMPLE_FPS},scale={w}:{h}",
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
        if res.returncode != 0:
            raise PipelineError(f"ffmpeg no pudo leer {Path(path).name}: {res.stderr.decode(errors='replace')[-300:]}")
        frames = np.frombuffer(res.stdout, np.uint8)[: (len(res.stdout) // (w * h * 3)) * w * h * 3]
        prev = None
        for i, frame in enumerate(frames.reshape(-1, h, w, 3).astype(np.float32)):
            # The fps filter rounds to the nearest frame: a sample in the last half interval may already show
            # what follows the range (the closing card), so none is taken there.
            if a + i / SAMPLE_FPS >= b - 1 / (2 * SAMPLE_FPS):
                break
            sampled += 1
            at = fmt_t(a + i / SAMPLE_FPS)
            ratio = empty_ratio(frame)
            blank = blank_below_header(frame, vp)
            if ratio > EMPTY_LIMIT:
                bad.append(f"{at} {ratio:.0%} vacío")
            elif blank > BLANK_LIMIT:
                bad.append(f"{at} en blanco bajo la cabecera ({blank:.0%}, N26)")
            if prev is not None:
                top, bottom = half_changes(prev, frame, vp)
                if max(top, bottom) > MIX_CHANGE and min(top, bottom) < MIX_STILL:
                    mixed.append(f"{at} cambia solo la mitad {'superior' if top > bottom else 'inferior'}")
            prev = frame
    rows = [problems("C4.empty_frames", "C4", bad,
                     f"{sampled} fotogramas con ≤ {EMPTY_LIMIT:.0%} vacío (fuera de apertura y cierre)")]
    if mixed:
        more = f" (+{len(mixed) - 5})" if len(mixed) > 5 else ""
        rows.append(check("N26.mixed", "N26", "WARN", "posibles vistas mezcladas: " + "; ".join(mixed[:5]) + more
                          + ": revisa esos fotogramas"))
    else:
        rows.append(check("N26.mixed", "N26", True, "ningún cambio brusco en solo una mitad del cuadro"))
    return rows


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
        rows += check_empty_frames(path, ranges, (video["width"], video["height"]), (layout or {}).get("viewport"))
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
    rows += check_voice_tone(voice_clips(pdir, vid))
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
