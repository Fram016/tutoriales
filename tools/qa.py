"""Stage: QA. Automatic checks of reglas/reglas-video.md on every rendered video, plus stills for review.

Usage: python tools/qa.py <slug> [--video ID]

For each video of tutorial.yaml (or only --video ID) it reads proyectos/<slug>/:
  out/<slug>-<video>.mp4   resolution by format, duration vs timeline total (±0.3 s), audio track,
                           A1 integrated loudness −14 ±1 LUFS and true peak < −1 dBTP (ebur128),
                           A2 silences > 1.0 s (silencedetect), C4 near-empty frames every 0.25 s
                           outside the opening and closing (> 70 % of 32 px tiles uniform background)
  edit/<video>/timeline.json  type duration (RED 15–35, PRO 20–60, NOV 15–30, TUT > 5 min needs
                           chapters), A2 voice gaps > 1.0 s and closing card ≤ 2.5 s
  hf-<video>/layout.json   O1, O2, R1, R2, T1, T2, C1, C5, V1, V3, V4 and L1–L4 on the captions
Then snapshots at the opening, the middle of each step, every result/highlight and the closing;
their PNG paths are printed for the mandatory visual review. Writes qa/<video>.json with every
check {id, rule, status PASS|FAIL|WARN, detail}, prints a table and exits 1 on any FAIL.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import yaml

from common import PipelineError, main_guard, project_dir, read_json, run, which, write_json
from lint import language_issues, wrap

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
CONTEXT_MAX, MIN_RESULT, MIN_CAPTION = 1.0, 0.8, 1.2
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
    return rows


def snapshot_times(timeline: dict) -> list[float]:
    times = []
    for name in ("opening", "requirements"):
        if span := block_span(timeline.get(name)):
            times.append((span[0] + span[1]) / 2)
    for step in timeline.get("steps", []):
        times.append(float(step["start"]) + float(step["duration"]) / 2)
        for ev in step.get("events", []):
            if ev.get("type") in ("result", "highlight"):
                t, t_end = float(ev["t"]), float(ev.get("t_end") or 0)
                times.append((t + t_end) / 2 if t_end > t else t + 0.4)
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
    return rows


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


def check_media(path: Path, timeline: dict) -> list[dict]:
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
        ranges = subtract([(0.0, min(total, duration))], cards(timeline))
        rows += check_empty_frames(path, ranges, (video["width"], video["height"]))
    return rows


# ---------- driver ----------

def take_snapshots(slug: str, video: str, times: list[float]) -> list[Path]:
    from render import snapshots  # render/compose are only needed for this step
    return snapshots(slug, video, times)


def check_video(slug: str, pdir: Path, tutorial: dict, video: dict) -> tuple[list[dict], list[Path]]:
    vid = video["id"]
    rows: list[dict] = []
    timeline_path = pdir / "edit" / vid / "timeline.json"
    if not timeline_path.exists():
        return [check("timeline", "S3", False, f"falta edit/{vid}/timeline.json: corre antes el pipeline")], []
    timeline = read_json(timeline_path)
    out = pdir / "out" / f"{slug}-{vid}.mp4"
    if out.exists():
        rows += check_media(out, timeline)
    else:
        rows.append(check("tech.file", "S3", False, f"falta out/{out.name}: corre render.py"))
    rows += check_timeline(timeline)
    layout_path = pdir / f"hf-{vid}" / "layout.json"
    if layout_path.exists():
        rows.append(check("layout", "L5", True, f"hf-{vid}/layout.json"))
        rows += check_layout(read_json(layout_path), timeline, tutorial)
    else:
        rows.append(check("layout", "L5", False, f"falta hf-{vid}/layout.json: compose.py v2 lo escribe; sin él "
                                                 "no se pueden validar O1, O2, R2, T1, T2, C1, C5, V1, V3, V4"))
    shots: list[Path] = []
    if out.exists():
        try:
            shots = take_snapshots(slug, vid, snapshot_times(timeline))
            rows.append(check("snapshots", "QA", True, f"{len(shots)} PNG para revisión visual"))
        except (PipelineError, ImportError) as exc:
            rows.append(check("snapshots", "QA", False, str(exc).splitlines()[0]))
    return rows, shots


def qa(slug: str, video: str | None = None) -> bool:
    pdir = project_dir(slug)
    tutorial = yaml.safe_load((pdir / "tutorial.yaml").read_text(encoding="utf-8")) or {}
    videos = tutorial.get("videos") or []
    if video:
        videos = [v for v in videos if v.get("id") == video]
        if not videos:
            raise PipelineError(f"tutorial.yaml no tiene un video '{video}'")
    if not videos:
        raise PipelineError("tutorial.yaml no tiene videos (formato v2)")
    passed = True
    print(f"[qa] {slug}")
    print(f"  {'video':<10} {'regla':<8} {'chequeo':<19} {'estado':<6} detalle")
    all_shots = {}
    for v in videos:
        vid = v["id"]
        rows, shots = check_video(slug, pdir, tutorial, v)
        ok = not any(r["status"] == "FAIL" for r in rows)
        passed &= ok
        all_shots[vid] = shots
        write_json(pdir / "qa" / f"{vid}.json", {"video": vid, "type": v.get("type"), "format": v.get("format"),
                                                 "status": "PASS" if ok else "FAIL", "checks": rows,
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
    a = ap.parse_args()
    if not qa(a.slug, a.video):
        sys.exit(1)


if __name__ == "__main__":
    main_guard(main)
