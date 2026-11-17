"""Stage: compose. Builds one HyperFrames project per variant from the edit + mix artifacts.

Usage: python tools/compose.py <slug>

Writes proyectos/<slug>/hf-<variant>/ (index.html, meta.json, hyperframes.json, assets/):
full → 1920x1080, short → 1080x1920 (Reels/TikTok). The composition adds intro/outro,
a synthetic cursor with click ripples, automatic zooms on the action boxes, step chips
and captions. Everything is local (GSAP copied from node_modules) so renders work offline.
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

from common import (ROOT, PipelineError, load_tutorial, main_guard, project_dir, read_json, run,
                    which, write_json)

TEMPLATE = ROOT / "templates" / "composition.html"
GSAP = ROOT / "node_modules" / "gsap" / "dist" / "gsap.min.js"
HYPERFRAMES = ROOT / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs"

SRC_W, SRC_H = 1920, 1080
BRAND_DEFAULTS = {"primary": "#2563eb", "accent": "#facc15", "background": "#0f172a",
                  "text": "#ffffff", "font": "Segoe UI"}
CURSOR_MOVE = 0.55      # cursor travel time to each event point
ZOOM_MOVE = 0.6         # camera travel time between framings
ZOOM_MIN_MOVE = 0.25    # shortest camera tween when events are close together
ZOOM_LEAD = 0.12        # camera settles this long before the event
CLICK_HOLD = 0.7        # how long a click/hover framing is held after the event
MAX_ZOOM = 2.0
CAPTION_WORDS = 7
BOXED = {"click", "hover", "type"}

LAYOUTS = {
    # Landscape: the camera viewport is the whole frame.
    "full": {"orientation": "landscape", "size": (1920, 1080), "view": (0, 0, 1920, 1080),
             "caption": 44, "caption_bottom": 70, "caption_top": 0, "caption_max_w": 1500,
             "chip_y": 0, "logo_h": 160, "title": 92, "subtitle": 46, "outro": 72},
    # Portrait: a 1080x1080 window between a title band and the caption area.
    "short": {"orientation": "portrait", "size": (1080, 1920), "view": (0, 330, 1080, 1080),
              "caption": 56, "caption_bottom": 0, "caption_top": 1435, "caption_max_w": 900,
              "chip_y": 236, "logo_h": 200, "title": 84, "subtitle": 50, "outro": 68},
}


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


# --- camera -----------------------------------------------------------------------------------

class Camera:
    """Framing math for a viewport of view_w x view_h looking at the 1920x1080 recording."""

    def __init__(self, view_w: int, view_h: int):
        self.w, self.h = view_w, view_h
        # Smallest scale at which the source still covers the viewport.
        self.cover = max(view_w / SRC_W, view_h / SRC_H)

    def frame(self, cx: float, cy: float, scale: float) -> dict:
        scale = max(scale, self.cover)
        x = min(0.0, max(self.w - SRC_W * scale, self.w / 2 - cx * scale))
        y = min(0.0, max(self.h - SRC_H * scale, self.h / 2 - cy * scale))
        return {"x": round(x, 1), "y": round(y, 1), "scale": round(scale, 3)}

    def base(self, focus: dict | None) -> dict:
        fx, fy = (focus["x"], focus["y"]) if focus else (SRC_W / 2, SRC_H / 2)
        return self.frame(fx, fy, self.cover)

    def zoom(self, box: dict) -> dict:
        scale = min(self.w * 0.55 / max(box["w"], 1), self.h * 0.5 / max(box["h"], 1))
        scale = min(max(scale, 1.0), MAX_ZOOM)
        return self.frame(box["x"] + box["w"] / 2, box["y"] + box["h"] / 2, scale)


def camera_plan(timeline: dict, cam: Camera) -> list[tuple[dict, float, float]]:
    """(framing, arrive_at, hold_until) targets in time order."""
    plan = []
    focus = None
    for step in timeline["steps"]:
        end = step["start"] + step["duration"]
        events = sorted(step["events"], key=lambda e: e["t"])
        for i, ev in enumerate(events):
            t = ev["t"]
            if ev["type"] in BOXED and ev.get("box"):
                focus = ev.get("point") or focus
                hold = ev.get("t_end", t) if ev["type"] == "type" else t
                plan.append((cam.zoom(ev["box"]), t - ZOOM_LEAD, min(hold + CLICK_HOLD, end)))
                # A click usually changes the screen (new page, modal, list): pull back right
                # after it instead of staying zoomed on a spot that may now be empty.
                next_boxed = next((e["t"] for e in events[i + 1:] if e["type"] in BOXED and e.get("box")), None)
                if ev["type"] == "click" and (next_boxed is None or next_boxed - t > 1.5):
                    back = min(t + CLICK_HOLD + ZOOM_MOVE, end)
                    plan.append((cam.base(focus), back, back))
            elif ev["type"] in ("goto", "scroll"):
                plan.append((cam.base(focus), t, t))
            elif ev.get("point"):
                focus = ev["point"]
                plan.append((cam.base(focus), t, t))
        plan.append((cam.base(focus), end, end))
    return plan


def camera_tweens(timeline: dict, cam: Camera) -> list[str]:
    intro = timeline["intro"]
    screen_end = intro + timeline["screen_duration"]
    first = next((e.get("point") for s in timeline["steps"] for e in s["events"] if e.get("point")), None)
    state = cam.base(first)
    lines = [f'tl.set("#cam", {{transformOrigin: "0 0", x: {state["x"]}, y: {state["y"]}, '
             f'scale: {state["scale"]}}}, 0);']
    cursor = intro  # end of the last camera tween/hold: tweens never overlap
    for framing, arrive, hold in camera_plan(timeline, cam):
        if framing == state:
            cursor = max(cursor, min(hold, screen_end))
            continue
        start = max(cursor, arrive - ZOOM_MOVE)
        end = max(arrive, start + ZOOM_MIN_MOVE)
        if start >= screen_end:
            break
        end = min(end, screen_end)
        lines.append(f'tl.to("#cam", {{x: {framing["x"]}, y: {framing["y"]}, scale: {framing["scale"]}, '
                     f'duration: {num(end - start)}, ease: "power2.inOut"}}, {num(start)});')
        state = framing
        cursor = max(end, min(hold, screen_end))
    return lines


# --- cursor -----------------------------------------------------------------------------------

def cursor_parts(timeline: dict) -> tuple[list[str], list[str]]:
    """GSAP lines for the cursor + ripple markup for every click."""
    intro = timeline["intro"]
    events = sorted((e for s in timeline["steps"] for e in s["events"] if e.get("point")),
                    key=lambda e: e["t"])
    if not events:
        return ['tl.set("#cursor", {opacity: 0}, 0);'], []
    p0 = events[0]["point"]
    lines = [f'tl.set("#cursor", {{x: {num(min(p0["x"] + 220, SRC_W - 60))}, '
             f'y: {num(min(p0["y"] + 160, SRC_H - 60))}}}, 0);']
    ripples = []
    last = intro
    for i, ev in enumerate(events):
        t, p = ev["t"], ev["point"]
        start = max(last, t - CURSOR_MOVE)
        if t - start >= 0.05:
            lines.append(f'tl.to("#cursor", {{x: {num(p["x"])}, y: {num(p["y"])}, duration: {num(t - start)}, '
                         f'ease: "power2.inOut"}}, {num(start)});')
        else:
            lines.append(f'tl.set("#cursor", {{x: {num(p["x"])}, y: {num(p["y"])}}}, {num(max(t, last))});')
        last = max(t, last)
        if ev["type"] == "click":
            rid = f"ripple-{i}"
            ripples.append(f'            <div class="ripple" id="{rid}" '
                           f'style="left: {num(p["x"])}px; top: {num(p["y"])}px"></div>')
            # set + to (not fromTo): a fromTo renders its start state immediately, so every
            # ripple would already be visible before its click.
            lines.append(f'tl.set("#{rid}", {{scale: 0.25, opacity: 0.95}}, {num(t)});')
            lines.append(f'tl.to("#{rid}", {{scale: 1.7, opacity: 0, duration: 0.55, ease: "power2.out"}}, {num(t)});')
            lines.append(f'tl.to("#cursor-arrow", {{scale: 0.78, duration: 0.08, ease: "power1.out"}}, {num(t)});')
            lines.append(f'tl.to("#cursor-arrow", {{scale: 1, duration: 0.14, ease: "power1.in"}}, {num(t + 0.08)});')
            last = max(last, t + 0.22)
    return lines, ripples


# --- captions + chips -------------------------------------------------------------------------

def caption_chunks(text: str) -> list[str]:
    """Balanced chunks of ≤ CAPTION_WORDS words; a break may move one word to land on punctuation."""
    words = text.split()
    if not words:
        return []
    count = math.ceil(len(words) / CAPTION_WORDS)
    chunks, i = [], 0
    for k in range(count, 0, -1):
        size = math.ceil((len(words) - i) / k)
        if k > 1:
            for alt in (size - 1, size + 1):
                if 2 <= alt <= CAPTION_WORDS and re.search(r"[.,;:!?]$", words[i + alt - 1]) \
                        and not re.search(r"[.,;:!?]$", words[i + size - 1]):
                    size = alt
                    break
        chunks.append(" ".join(words[i:i + size]))
        i += size
    return [c for c in chunks if c]


def captions(timeline: dict) -> tuple[list[str], list[str]]:
    markup, lines = [], []
    n = 0
    for step in timeline["steps"]:
        chunks = caption_chunks(step.get("narration") or "")
        if not chunks or step["voice_duration"] <= 0:
            continue
        total_chars = sum(len(c) for c in chunks)
        t = step["voice_start"]
        for chunk in chunks:
            dur = step["voice_duration"] * len(chunk) / total_chars
            cid = f"cap-{n}"
            markup.append(f'      <div id="{cid}" class="clip cap-layer" data-start="{num(t)}" '
                          f'data-duration="{num(dur)}"><span class="cap" id="{cid}-text">{esc(chunk)}</span></div>')
            lines.append(f'tl.from("#{cid}-text", {{y: 18, opacity: 0, duration: 0.16, ease: "power2.out"}}, '
                         f'{num(t)});')
            t += dur
            n += 1
    return markup, lines


def chips(timeline: dict) -> tuple[list[str], list[str]]:
    markup, lines = [], []
    for i, step in enumerate(timeline["steps"], 1):
        title = f' <span>{esc(step["title"])}</span>' if step.get("title") else ""
        cid = f"chip-{i}"
        markup.append(f'      <div id="{cid}" class="clip chip-layer" data-start="{num(step["start"])}" '
                      f'data-duration="{num(step["duration"])}"><div class="chip" id="{cid}-pill">'
                      f'<b>Paso {i}</b>{title}</div></div>')
        lines.append(f'tl.from("#{cid}-pill", {{opacity: 0, x: -24, duration: 0.3, ease: "power2.out"}}, '
                     f'{num(step["start"])});')
    return markup, lines


# --- project ----------------------------------------------------------------------------------

def fill(template: str, values: dict) -> str:
    def sub(m):
        key = m.group(1)
        if key not in values:
            raise PipelineError(f"templates/composition.html: falta el valor '{key}'")
        return str(values[key])
    return re.sub(r"\{\{([A-Z_]+)\}\}", sub, template)


def build_html(tut: dict, brand: dict, timeline: dict, variant: str, logo_src: str | None) -> str:
    lay = LAYOUTS[variant]
    width, height = lay["size"]
    vx, vy, vw, vh = lay["view"]
    intro, screen, outro = timeline["intro"], timeline["screen_duration"], timeline["outro"]
    total = timeline["total"]
    cam = Camera(vw, vh)

    cam_lines = camera_tweens(timeline, cam)
    cursor_lines, ripples = cursor_parts(timeline)
    cap_markup, cap_lines = captions(timeline)
    chip_markup, chip_lines = chips(timeline)
    logo_tag = (lambda cls: f'        <img class="{cls}" id="{{}}" src="{logo_src}" alt="" />') if logo_src else None

    topband = ""
    if lay["orientation"] == "portrait":
        img = f'<img id="band-logo" src="{logo_src}" alt="" />' if logo_src else ""
        topband = f'      <div id="topband">{img}<h2 id="band-title">{esc(tut["title"])}</h2></div>'

    # The title is already on screen at frame 0 (social players use it as the thumbnail).
    scene_in = [
        'tl.from("#intro-bar", {scaleX: 0, duration: 0.5, ease: "power3.out"}, 0.2);',
        'tl.from("#intro-title", {y: 40, scale: 0.96, duration: 0.8, ease: "power3.out"}, 0);',
        'tl.from("#intro-subtitle", {y: 30, opacity: 0, duration: 0.6, ease: "power3.out"}, 0.6);',
        f'tl.from("#outro-text", {{y: 40, opacity: 0, duration: 0.6, ease: "power3.out"}}, {num(intro + screen + 0.15)});',
        f'tl.from("#outro-bar", {{scaleX: 0, duration: 0.5, ease: "power3.out"}}, {num(intro + screen + 0.35)});',
    ]
    if logo_src:
        scene_in += ['tl.from("#intro-logo", {scale: 0.8, opacity: 0, duration: 0.6, ease: "back.out(1.6)"}, 0.05);',
                     f'tl.from("#outro-logo", {{scale: 0.8, opacity: 0, duration: 0.6, ease: "back.out(1.6)"}}, '
                     f'{num(intro + screen + 0.05)});']

    script = scene_in + cam_lines + cursor_lines + chip_lines + cap_lines
    values = {
        "WIDTH": width, "HEIGHT": height, "ORIENTATION": lay["orientation"],
        "PRIMARY": brand["primary"], "ACCENT": brand["accent"], "BACKGROUND": brand["background"],
        "TEXT": brand["text"], "FONT": f'"{brand["font"]}", "Segoe UI", Arial, sans-serif',
        "CAPTION_SIZE": lay["caption"], "CAPTION_BOTTOM": lay["caption_bottom"],
        "CAPTION_TOP": lay["caption_top"], "CAPTION_MAX_W": lay["caption_max_w"], "CHIP_Y": lay["chip_y"],
        "LOGO_H": lay["logo_h"], "TITLE_SIZE": lay["title"], "SUBTITLE_SIZE": lay["subtitle"],
        "OUTRO_SIZE": lay["outro"],
        "VIEW_X": vx, "VIEW_Y": vy, "VIEW_W": vw, "VIEW_H": vh,
        "TOTAL": num(total), "INTRO": num(intro), "SCREEN": num(screen),
        "OUTRO_START": num(intro + screen), "OUTRO": num(outro),
        "TITLE": esc(tut["title"]), "SUBTITLE": esc(tut.get("subtitle")),
        "OUTRO_TEXT": esc((tut.get("outro") or {}).get("text") or "¡Gracias por ver!"),
        "INTRO_LOGO": logo_tag("logo").format("intro-logo") if logo_tag else "",
        "OUTRO_LOGO": logo_tag("logo").format("outro-logo") if logo_tag else "",
        "TOPBAND": topband, "RIPPLES": "\n".join(ripples),
        "CHIPS": "\n".join(chip_markup), "CAPTIONS": "\n".join(cap_markup),
        "TIMELINE": "\n".join("      " + line for line in script),
    }
    return fill(TEMPLATE.read_text(encoding="utf-8"), values)


def compose_variant(slug: str, pdir, tut: dict, brand: dict, variant: str) -> dict:
    edit_dir = pdir / "edit" / variant
    mix = pdir / "audio" / variant / "mix.wav"
    for path in (edit_dir / "timeline.json", edit_dir / "screen.mp4", mix):
        if not path.exists():
            raise PipelineError(f"Falta {path.relative_to(pdir)}. Corré antes edit.py y mix.py.")
    if not GSAP.exists():
        raise PipelineError("Falta node_modules/gsap. Corré: npm install")
    timeline = read_json(edit_dir / "timeline.json")
    out = pdir / f"hf-{variant}"
    assets = out / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(edit_dir / "screen.mp4", assets / "screen.mp4")
    shutil.copyfile(mix, assets / "mix.wav")
    shutil.copyfile(GSAP, assets / "gsap.min.js")
    logo_src = None
    if brand["logo"]:
        logo_src = f"assets/{brand['logo'].name}"
        shutil.copyfile(brand["logo"], assets / brand["logo"].name)

    (out / "index.html").write_text(build_html(tut, brand, timeline, variant, logo_src), encoding="utf-8")
    write_json(out / "meta.json", {"id": f"{slug}-{variant}", "name": f"{tut['title']} ({variant})"})
    write_json(out / "hyperframes.json", {
        "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
        "paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"},
        "media": {"autoProxy": True},
    })
    warnings = check(out)
    w, h = LAYOUTS[variant]["size"]
    print(f"[compose] {variant}: {w}x{h}, {timeline['total']:.1f} s, {len(timeline['steps'])} pasos"
          f"{'' if logo_src else ', sin logo'}, check OK ({warnings} avisos) → {out.relative_to(ROOT)}")
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
        raise PipelineError(f"hyperframes check encontró errores en {out.name}:\n{lines}")
    return sum(p.get("warningCount", 0) for p in passes)


def compose(slug: str) -> dict:
    tut = load_tutorial(slug)
    pdir = project_dir(slug)
    brand = brand_of(tut, pdir)
    variants = [v for v in ("full", "short") if (pdir / "edit" / v / "timeline.json").exists()]
    if not variants:
        raise PipelineError("No hay cortes en edit/. Corré antes edit.py.")
    return {v: compose_variant(slug, pdir, tut, brand, v) for v in variants}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug")
    compose(ap.parse_args().slug)


if __name__ == "__main__":
    main_guard(main)
