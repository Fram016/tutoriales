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
"""
from __future__ import annotations

import json
import shutil
import subprocess
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


def cut_screen() -> None:
    parts = "".join(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS"
                    + (f",tpad=start_duration={PRE_HOLD[sid]}:start_mode=clone" if sid in PRE_HOLD else "")
                    + f"[v{i}];" for i, (sid, a, b) in enumerate(SEGMENTS))
    chain = "".join(f"[v{i}]" for i in range(len(SEGMENTS)))
    graph = f"{parts}{chain}concat=n={len(SEGMENTS)}:v=1:a=0,fps=30,format=yuv420p[out]"
    subprocess.run([shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", str(SOURCE),
                    "-filter_complex", graph, "-map", "[out]", "-c:v", "libx264", "-crf", "30",
                    "-preset", "veryfast", "-movflags", "+faststart", str(HERE / "screen.mp4")], check=True)


def timeline(video: str) -> dict:
    spec = VIDEOS[video]
    start = spec["opening"]
    steps, cursor = [], start
    for sid, a, b in SEGMENTS:
        hold = PRE_HOLD.get(sid, 0)
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


def main() -> None:
    cut_screen()
    for video in VIDEOS:
        (HERE / f"{video}.timeline.json").write_text(
            json.dumps(timeline(video), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (HERE / "brand.json").write_text(json.dumps(BRAND, indent=2) + "\n", encoding="utf-8")
    print(f"fixture -> {HERE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
