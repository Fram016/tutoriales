"""Builds the compose/render fixture: screen.mp4 + timeline.json v2 for a TUT 16:9 and a RED 9:16.

Usage: python templates/fixtures/build_fixture.py

Cuts three steps (nuevo, datos, guardar) out of proyectos/nexo-crm-contacto/edit/full/screen.mp4
(a local, gitignored render of the Nexo CRM demo) and writes, next to this file:
  screen.mp4               1920x1080, 30 fps, shared by both videos
  tutorial.timeline.json   TUT 16:9 (opening 3.0 s, closing 2.5 s)
  redes.timeline.json      RED 9:16 (hook 1.5 s, CTA 2.0 s)
  brand.json               brand colors of the demo (no accent: it defaults to the primary, N5)
The boxes and points are the real ones recorded by capture for those frames. Like edit's output (N1,
C10), the first step opens with a hold before its click, clicks happen just before the page changes,
clicks carry `screen_at` (the new screen) and fields carry `frame_box` (control + label, C9). Like
capture (reglas-ronda3 L3), the actions inside the "Nuevo contacto" card carry its `form_box` (N10).

       python templates/fixtures/build_fixture.py partes

Writes only the round-4 fixture (reglas-ronda4 T2), leaving the files above untouched:
  partes-screen.mp4             the three steps plus a "descargar" step on the contact list, with held frames
                                under the two part separators
  partes-surface-popup.mp4      a stand-in extension popup (420x640 CSS px at DPR 2) on the screen's clock
  partes-logo.png               a dark logo (black square with a white letter, a black word, a brand dot)
  partes.timeline.json          TUT 16:9 in two parts (N16), the popup (S5/N17/N22), a censor region over
                                the e-mail column (N25), no closing card (N27)
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / "proyectos" / "nexo-crm-contacto" / "edit" / "full" / "screen.mp4"

# (step id, source start, source end) in seconds of SOURCE.
SEGMENTS = [("nuevo", 12.76, 17.28), ("datos", 17.28, 25.08), ("guardar", 39.68, 48.52)]
# N1: edit holds the first frame of a step while the narration asks for the action.
PRE_HOLD = {"nuevo": 1.5}

# N10: the "Nuevo contacto" card (fields + buttons), measured on the recording.
FORM = {"x": 273, "y": 152, "w": 878, "h": 585}

# Events per step, times in seconds of SOURCE.
EVENTS = {
    "nuevo": [
        {"type": "click", "t": 13.79, "screen_c": 13.827, "selector": "#btn-nuevo-contacto",
         "box": {"x": 1721.1, "y": 96, "w": 166.9, "h": 43}, "point": {"x": 1805, "y": 118}},
        {"type": "focus", "t": 14.747, "selector": "#c-nombre",
         "box": {"x": 301, "y": 203, "w": 400, "h": 45}, "point": {"x": 501, "y": 226},
         "frame_box": {"x": 301, "y": 181, "w": 400, "h": 67}, "form_box": FORM},
    ],
    "datos": [
        {"type": "type", "t": 17.575, "t_end": 18.48, "chars": 5, "selector": "#c-nombre",
         "box": {"x": 301, "y": 203, "w": 400, "h": 45}, "point": {"x": 501, "y": 226},
         "frame_box": {"x": 301, "y": 181, "w": 400, "h": 67}, "form_box": FORM},
        {"type": "type", "t": 18.842, "t_end": 20.126, "chars": 7, "selector": "#c-apellido",
         "box": {"x": 723, "y": 203, "w": 400, "h": 45}, "point": {"x": 923, "y": 226},
         "frame_box": {"x": 723, "y": 181, "w": 400, "h": 67}, "form_box": FORM},
        {"type": "type", "t": 20.532, "t_end": 24.496, "chars": 29, "selector": "#c-email",
         "box": {"x": 301, "y": 375, "w": 400, "h": 45}, "point": {"x": 501, "y": 398},
         "frame_box": {"x": 301, "y": 353, "w": 400, "h": 67}, "form_box": FORM},
    ],
    "guardar": [
        {"type": "click", "t": 40.46, "screen_c": 40.494, "selector": "#btn-guardar",
         "box": {"x": 960.75, "y": 664, "w": 162.25, "h": 45}, "point": {"x": 1042, "y": 687}, "form_box": FORM},
        {"type": "result", "t": 41.611, "selector": "#toast",
         "box": {"x": 1594, "y": 999, "w": 294, "h": 49}},
        {"type": "highlight", "t": 43.04, "selector": "tr.new",
         "box": {"x": 273, "y": 267, "w": 1613, "h": 52}},
    ],
}

STEPS = {
    "nuevo": {"number": 3, "title": "Abre el formulario",
              "TUT": "Haz clic en Nuevo contacto para abrir el formulario.",
              "RED": "Abre Nuevo contacto."},
    "datos": {"number": 4, "title": "Completa los datos",
              "TUT": "Escribe el nombre, el apellido y el correo con el que vas a contactar a la persona.",
              "RED": "Escribe nombre, apellido y correo."},
    "guardar": {"number": 5, "title": "Guarda el contacto",
                "TUT": "Haz clic en Guardar contacto. Sale el aviso verde y el contacto nuevo aparece "
                       "primero en la lista, resaltado.",
                "RED": "Guarda y tu contacto aparece primero en la lista de Nexo CRM."},
}

VIDEOS = {
    "tutorial": {"type": "TUT", "format": "16:9", "output": [1920, 1080], "opening": 3.0, "closing": 2.5,
                 "opening_text": "Aprende a crear un contacto en Nexo CRM",
                 "opening_narration": "En este video aprendes a crear un contacto en Nexo CRM.",
                 "closing_text": "Siguiente: registra una oportunidad en Nexo CRM",
                 "closing_narration": "En el siguiente video aprendes a registrar una oportunidad."},
    "redes": {"type": "RED", "format": "9:16", "output": [1080, 1920], "opening": 1.5, "closing": 2.0,
              "opening_text": "¿Conociste a alguien en una feria?",
              "opening_narration": "¿Conociste a alguien en una feria?",
              "closing_text": "Mira el tutorial completo en el enlace del perfil",
              "closing_narration": "Mira el tutorial completo en el enlace del perfil."},
}

BRAND = {"primary": "#7c3aed", "background": "#1f1235", "text": "#ffffff", "font": "Segoe UI"}


def cut_screen(segments=SEGMENTS, holds=PRE_HOLD, out: Path = HERE / "screen.mp4") -> None:
    parts = "".join(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS"
                    + (f",tpad=start_duration={holds[sid]}:start_mode=clone" if sid in holds else "")
                    + f"[v{i}];" for i, (sid, a, b) in enumerate(segments))
    chain = "".join(f"[v{i}]" for i in range(len(segments)))
    graph = f"{parts}{chain}concat=n={len(segments)}:v=1:a=0,fps=30,format=yuv420p[out]"
    subprocess.run([shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", str(SOURCE),
                    "-filter_complex", graph, "-map", "[out]", "-c:v", "libx264", "-crf", "30",
                    "-preset", "veryfast", "-movflags", "+faststart", str(out)], check=True)


def timeline(video: str, segments=SEGMENTS, holds=PRE_HOLD) -> dict:
    spec = VIDEOS[video]
    start = spec["opening"]
    steps, cursor = [], start
    for sid, a, b in segments:
        hold = holds.get(sid, 0)
        dur = round(b - a + hold, 3)
        meta = STEPS[sid]
        events = []
        for ev in EVENTS[sid]:
            ev = json.loads(json.dumps(ev))
            ev["t"] = round(cursor + hold + ev["t"] - a, 3)
            if "t_end" in ev:
                ev["t_end"] = round(cursor + hold + ev["t_end"] - a, 3)
            if "screen_c" in ev:
                ev["screen_at"] = round(cursor + hold + ev.pop("screen_c") - a, 3)
            events.append(ev)
        steps.append({"id": sid, "number": meta["number"], "chapter": None, "title": meta["title"],
                      "narration": meta[spec["type"]], "start": round(cursor, 3), "duration": dur,
                      "voice_start": round(cursor + 0.25, 3), "voice_duration": round(dur - 0.6, 3),
                      "events": events})
        cursor += dur
    screen_end = round(cursor, 3)
    total = round(screen_end + spec["closing"], 3)
    return {"video": video, "type": spec["type"], "format": spec["format"], "source": [1920, 1080],
            "output": spec["output"], "total": total, "product": "Nexo CRM",
            "title": "Cómo crear un contacto en Nexo CRM",
            "opening": {"start": 0, "duration": spec["opening"], "text": spec["opening_text"],
                        "narration": spec["opening_narration"], "voice_start": 0.2,
                        "voice_duration": spec["opening"] - 0.4},
            "requirements": None,
            "closing": {"start": screen_end, "duration": spec["closing"], "text": spec["closing_text"],
                        "narration": spec["closing_narration"], "voice_start": screen_end,
                        "voice_duration": spec["closing"] - 0.3},
            "screen_start": start, "screen_end": screen_end, "steps": steps}


# --- round 4 (reglas-ronda4 T2): parts, popup, context badge, censor region, no closing, dark logo ---------

# A fourth step on the contact list (source 49.5-55.5 s) where the popup downloads; the part separators
# (1.2 s) cover held frames at the start of "nuevo" (part 1) and "guardar" (part 2).
PARTES_SEGMENTS = SEGMENTS + [("descargar", 49.5, 55.5)]
PARTES_HOLDS = {"nuevo": 2.7, "guardar": 1.5}
SEPARATOR = 1.2
PARTS = [{"n": 1, "title": "Crear el contacto", "steps": ("nuevo", "datos")},
         {"n": 2, "title": "Guardar y descargar", "steps": ("guardar", "descargar")}]
# Popup boxes in popup CSS px (420x640), like the recorder writes them for a surface.
POPUP = {"size": [420, 640], "dpr": 2, "anchor": "top-right", "file": "partes-surface-popup.mp4"}
BOTON = {"x": 24, "y": 150, "w": 176, "h": 56}
ESTADO = {"x": 24, "y": 380, "w": 372, "h": 60}
POPUP_TIMES = (1.0, 2.6, 3.8, 5.6)      # open, click, result, close: seconds after "descargar" starts
# The e-mail column of the contact list (N25: third-party data blurred during the step).
CORREO = {"x": 830, "y": 268, "w": 300, "h": 104}
FONTS = Path("C:/Windows/Fonts")


def partes_timeline() -> dict:
    VIDEOS["partes"] = {**VIDEOS["tutorial"], "closing": 0.5}
    STEPS["descargar"] = {"number": 6, "title": "Descarga con la extensión",
                          "TUT": "Abre Perseo XML y haz clic en XML. Al terminar, el resumen muestra los "
                                 "descargados y los errores."}
    EVENTS["descargar"] = []
    tl = timeline("partes", PARTES_SEGMENTS, PARTES_HOLDS)
    steps = {s["id"]: s for s in tl["steps"]}
    for part in PARTS:
        for sid in part["steps"]:
            steps[sid]["part"] = part["n"]
    tl["parts"] = [{"n": p["n"], "title": p["title"], "start": steps[p["steps"][0]]["start"], "duration": SEPARATOR}
                   for p in PARTS]
    for sid in ("nuevo", "guardar"):        # the voice starts after the separator
        steps[sid]["voice_start"] = round(steps[sid]["start"] + SEPARATOR + 0.1, 3)
        steps[sid]["voice_duration"] = round(steps[sid]["duration"] - SEPARATOR - 0.5, 3)
    d0 = steps["descargar"]["start"]
    t_open, t_click, t_result, t_close = (round(d0 + t, 3) for t in POPUP_TIMES)

    def mid(b):
        return {"x": b["x"] + b["w"] / 2, "y": b["y"] + b["h"] / 2}

    steps["descargar"]["events"] = [
        {"type": "open", "t": t_open, "t_end": t_open, "surface": "popup", "target_ok": True},
        {"type": "click", "t": t_click, "t_end": t_click, "surface": "popup", "selector": "#boton1", "box": BOTON,
         "point": mid(BOTON), "frame_box": BOTON, "form_box": {"x": 0, "y": 0, "w": 420, "h": 640},
         "target_ok": True, "target_text": "XML Para importar"},
        {"type": "result", "t": t_result, "t_end": round(t_result + 1.5, 3), "surface": "popup",
         "selector": "#estado", "box": ESTADO, "point": mid(ESTADO), "target_ok": True},
        {"type": "close", "t": t_close, "t_end": t_close, "surface": "popup"}]
    tl["surfaces"] = {"popup": {**POPUP, "windows": [[t_open, t_close]]}}
    tl["censor_regions"] = [{"t0": d0, "t1": round(d0 + steps["descargar"]["duration"], 3), "box": CORREO}]
    # Fixture stand-ins for the Perseo XML labels (the screen is the Nexo CRM demo).
    tl["context_labels"] = {"page": "En el SRI", "extension": "En Perseo XML"}
    tl["closing"] = None                    # N27: ends on the result, the last 0.5 s held
    tl["video"] = "partes"
    return tl


def _font(name: str) -> str:
    """A font path for ffmpeg drawtext (the drive colon escaped)."""
    return (FONTS / name).as_posix().replace(":", "\\:")


def popup_track(tl: dict) -> None:
    """A stand-in popup on the screen's clock: header, four download buttons, a status line that turns to
    "En proceso" on the click and to the summary on the result, and the folder link at the bottom."""
    ss = tl["screen_start"]
    ev = {e["type"]: e["t"] - ss for s in tl["steps"] for e in s["events"] if e.get("surface")}
    reg, bold = _font("segoeui.ttf"), _font("segoeuib.ttf")

    def text(t, x, y, size, color, font=reg, enable=None):
        on = f":enable='{enable}'" if enable else ""
        return f"drawtext=fontfile='{font}':text='{t}':x={x}:y={y}:fontsize={size}:fontcolor={color}{on}"

    def box(b, color):
        return f"drawbox=x={2 * b['x']}:y={2 * b['y']}:w={2 * b['w']}:h={2 * b['h']}:color={color}:t=fill"

    buttons = [(BOTON, "0xfff1e8", "XML", "Para importar"), ({**BOTON, "x": 220}, "0xf4f4f5", "PDF", "RIDE recibidos"),
               ({**BOTON, "y": 270}, "0xf4f4f5", "PDF", "RIDE emitidos"),
               ({**BOTON, "x": 220, "y": 270}, "0xf4f4f5", "XML", "Desde el RIDE")]
    chain = [text("PERSEO", 300, 40, 64, "0x09090b", bold),
             text("Descarga de comprobantes del SRI", 190, 120, 28, "0xca4100"),
             text("COMPROBANTES RECIBIDOS", 48, 250, 26, "0x52525b", bold),
             text("COMPROBANTES EMITIDOS", 48, 490, 26, "0x52525b", bold), box(ESTADO, "0xf4f4f5")]
    for b, color, title, sub in buttons:
        chain += [box(b, color), text(title, 2 * b["x"] + 32, 2 * b["y"] + 18, 34, "0x09090b", bold),
                  text(sub, 2 * b["x"] + 32, 2 * b["y"] + 58, 24, "0x52525b")]
    chain += [text("Listo para descargar", 80, 788, 30, "0x52525b", enable=f"lt(t,{ev['click']:.3f})"),
              text("En proceso", 80, 788, 30, "0xca4100", bold, f"between(t,{ev['click']:.3f},{ev['result']:.3f})"),
              text("6 descargados, 0 con error", 80, 788, 30, "0x15803d", bold, f"gte(t,{ev['result']:.3f})"),
              text("Carpeta de descargas", 250, 1180, 28, "0xca4100", bold)]
    length = tl["screen_end"] - ss
    subprocess.run([shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    f"color=c=white:s=840x1280:r=30:d={length:.3f}", "-vf", ",".join(chain), "-c:v", "libx264",
                    "-crf", "30", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                    str(HERE / POPUP["file"])], check=True)


def dark_logo() -> None:
    """N24: a logo that is invisible on the dark brand background unless compose makes its light variant."""
    from PIL import Image, ImageDraw, ImageFont
    im = Image.new("RGBA", (640, 200), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((10, 10, 190, 190), radius=36, fill=(2, 2, 2, 255))
    letter, word = (ImageFont.truetype(str(FONTS / "segoeuib.ttf"), size) for size in (140, 110))
    d.text((52, 6), "N", font=letter, fill=(255, 255, 255, 255))
    d.text((220, 30), "Nexo", font=word, fill=(2, 2, 2, 255))
    d.ellipse((560, 120, 600, 160), fill=(124, 58, 237, 255))
    im.save(HERE / "partes-logo.png")


def build_partes() -> None:
    cut_screen(PARTES_SEGMENTS, PARTES_HOLDS, HERE / "partes-screen.mp4")
    tl = partes_timeline()
    popup_track(tl)
    dark_logo()
    (HERE / "partes.timeline.json").write_text(json.dumps(tl, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"fixture partes -> {HERE.relative_to(ROOT)}")


def main() -> None:
    if sys.argv[1:] == ["partes"]:
        build_partes()
        return
    cut_screen()
    for video in VIDEOS:
        (HERE / f"{video}.timeline.json").write_text(
            json.dumps(timeline(video), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (HERE / "brand.json").write_text(json.dumps(BRAND, indent=2) + "\n", encoding="utf-8")
    print(f"fixture -> {HERE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
