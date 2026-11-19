"""A video of the user as a take (F2, reglas/reglas-video.md §Parte 10; odd/tasks/perseo-resultado.md T1).

Usage: python tools/import_video_take.py <video> --spec <spec.yaml> --out <take_dir>

Writes <take_dir>/{frames/, frames.json, actions.json} in the format of tools/capture.py (no surfaces), so
merge_takes, edit and compose take it like a recorded take. The video's audio is not used (D5).

Spec (times in seconds of the source video, boxes in its pixels):
  fps: 12                      frames per second of the take
  trim: [start, end]           optional; the take clock starts at `start`
  viewport: [1920, 1080]       size of the frames (the source, or its crop, is scaled to it)
  crop: [x, y, w, h]           optional region of interest (e.g. without the taskbar), scaled to the viewport
  blur: [{box: [x, y, w, h], from: s, to: s}, ...]   F3: strong blur of the box while from <= t <= to (both
                               optional: the whole video), applied before a frame is written
  steps: [{id, t0, t1, events: [{type, t, box: {x, y, w, h}, selector?, target_ok?, target_text?}]}]
                               type: focus | highlight | hover | click | press_visual (a click shown, `visual`)
                               | result; selector defaults to manual:<step id>, target_ok to true.
F3: the unblurred frames are extracted into a temporary dir that is deleted when the import ends (also on a
failure); only blurred frames reach <take_dir>. The source path is never written or printed (it may carry the
Windows user name). A previous take in <take_dir> is moved aside like capture.py does (keep_previous_take).
The first step opens with a `goto` at its t0 (a new screen: compose cuts to the take, C7/C10).
Every step is marked `cursor: "recorded"`: the frames show the user's own pointer, so compose hides its arrow there
(one cursor, C5) and keeps the click halo.
"""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import yaml
from PIL import Image, ImageFilter

from capture import keep_previous_take
from common import PipelineError, main_guard, media_duration, run, which

EVENT_TYPES = ("click", "focus", "highlight", "hover", "press_visual", "result")
POINTER = ("click", "press_visual")   # capture.py logs frame_box for these (C9)
PIXELATE = 12      # F3: the box is reduced 12x, enlarged back and blurred: no glyph survives
BLUR_RADIUS = 6
QUALITY = 90


def _r(x: float) -> float:
    return round(x, 4)


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _box_list(v) -> bool:
    return isinstance(v, (list, tuple)) and len(v) == 4 and all(_num(x) for x in v) and v[2] > 0 and v[3] > 0


def _box_map(v) -> bool:
    return isinstance(v, dict) and all(_num(v.get(k)) for k in "xywh") and v["w"] > 0 and v["h"] > 0


def validate_spec(spec: dict, duration: float | None = None) -> dict:
    """The spec with defaults; PipelineError names the first problem (nothing is written before)."""
    if not isinstance(spec, dict):
        raise PipelineError("la especificación tiene que ser un mapa (fps, trim, viewport, blur, steps)")
    fps = spec.get("fps", 12)
    if not _num(fps) or fps <= 0:
        raise PipelineError("'fps' tiene que ser un número mayor que 0")
    trim = spec.get("trim")
    if trim is not None and not (isinstance(trim, (list, tuple)) and len(trim) == 2 and all(_num(x) for x in trim)
                                 and 0 <= trim[0] < trim[1]):
        raise PipelineError("'trim' tiene que ser [inicio, fin] con inicio < fin")
    if trim is not None and duration is not None and trim[1] > duration + 0.05:
        raise PipelineError(f"'trim' termina en {trim[1]:g} s pero el video dura {duration:.1f} s")
    start, end = (trim[0], trim[1]) if trim else (0.0, duration if duration is not None else float("inf"))
    viewport = spec.get("viewport", spec.get("scale", [1920, 1080]))
    if not (isinstance(viewport, (list, tuple)) and len(viewport) == 2 and all(_num(x) and x > 0 for x in viewport)):
        raise PipelineError("'viewport' tiene que ser [ancho, alto]")
    crop = spec.get("crop")
    if crop is not None and not _box_list(crop):
        raise PipelineError("'crop' tiene que ser [x, y, ancho, alto]")
    blur = spec.get("blur") or []
    if not isinstance(blur, list):
        raise PipelineError("'blur' tiene que ser una lista de {box, from?, to?}")
    for i, item in enumerate(blur):
        if not isinstance(item, dict) or not _box_list(item.get("box")):
            raise PipelineError(f"blur[{i}]: 'box' tiene que ser [x, y, ancho, alto]")
        if any(k in item and not _num(item[k]) for k in ("from", "to")):
            raise PipelineError(f"blur[{i}]: 'from' y 'to' son segundos del video")
    steps = spec.get("steps")
    if not isinstance(steps, list) or not steps:
        raise PipelineError("'steps' tiene que ser una lista con al menos un paso")
    seen = set()
    for step in steps:
        sid = step.get("id") if isinstance(step, dict) else None
        if not isinstance(sid, str) or not sid:
            raise PipelineError("cada paso necesita un 'id'")
        if sid in seen:
            raise PipelineError(f"el paso '{sid}' está repetido")
        seen.add(sid)
        t0, t1 = step.get("t0"), step.get("t1")
        if not (_num(t0) and _num(t1) and t0 < t1):
            raise PipelineError(f"paso {sid}: necesita t0 < t1 (segundos del video)")
        if t0 < start - 1e-9 or t1 > end + 1e-9:
            raise PipelineError(f"paso {sid}: t0/t1 tienen que quedar dentro de trim ({start:g}-{end:g} s)")
        events = step.get("events") or []
        if not isinstance(events, list):
            raise PipelineError(f"paso {sid}: 'events' tiene que ser una lista")
        for ev in events:
            kind = ev.get("type") if isinstance(ev, dict) else None
            if kind not in EVENT_TYPES:
                raise PipelineError(f"paso {sid}: evento '{kind}' desconocido (válidos: {', '.join(EVENT_TYPES)})")
            if not _num(ev.get("t")):
                raise PipelineError(f"paso {sid}: el evento {kind} necesita 't'")
            if not t0 <= ev["t"] <= t1:
                raise PipelineError(f"paso {sid}: el evento {kind} ({ev['t']:g} s) queda fuera del paso "
                                    f"({t0:g}-{t1:g} s)")
            if not _box_map(ev.get("box")):
                raise PipelineError(f"paso {sid}: el evento {kind} necesita box {{x, y, w, h}}")
    return {"fps": fps, "start": float(start), "end": end if trim else None, "viewport": [int(v) for v in viewport],
            "crop": list(crop) if crop else None, "blur": blur, "steps": steps}


class Mapper:
    """Source pixels -> viewport pixels (crop, then scale)."""

    def __init__(self, source: tuple[int, int], viewport, crop=None):
        self.cx, self.cy, cw, ch = crop or (0, 0, source[0], source[1])
        self.sx, self.sy = viewport[0] / cw, viewport[1] / ch

    def box(self, x, y, w, h) -> dict:
        return {"x": round((x - self.cx) * self.sx), "y": round((y - self.cy) * self.sy),
                "w": round(w * self.sx), "h": round(h * self.sy)}


def censor_frame(img: Image.Image, boxes: list[dict]) -> Image.Image:
    """F3: every box pixelated and blurred (viewport pixels)."""
    W, H = img.size
    for b in boxes:
        x0, y0 = max(0, b["x"]), max(0, b["y"])
        x1, y1 = min(W, b["x"] + b["w"]), min(H, b["y"] + b["h"])
        if x1 <= x0 or y1 <= y0:
            continue
        region = img.crop((x0, y0, x1, y1))
        small = region.resize((max(1, (x1 - x0) // PIXELATE), max(1, (y1 - y0) // PIXELATE)), Image.BOX)
        region = small.resize(region.size, Image.BILINEAR).filter(ImageFilter.GaussianBlur(BLUR_RADIUS))
        img.paste(region, (x0, y0))
    return img


def video_size(video: Path) -> tuple[int, int]:
    out = run([which("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
               "-of", "csv=p=0", str(video)], quiet=True).stdout
    w, h = out.strip().split(",")[:2]
    return int(w), int(h)


def event_out(sid: str, ev: dict, start: float, mapper: Mapper) -> dict:
    kind = "click" if ev["type"] == "press_visual" else ev["type"]
    box = mapper.box(*(ev["box"][k] for k in "xywh"))
    out = {"type": kind, "t": _r(ev["t"] - start), "selector": ev.get("selector") or f"manual:{sid}", "box": box,
           "point": {"x": round(box["x"] + box["w"] / 2), "y": round(box["y"] + box["h"] / 2)},
           "target_ok": bool(ev.get("target_ok", True))}
    if ev.get("target_text"):
        out["target_text"] = str(ev["target_text"])
    if ev["type"] in POINTER:
        out["frame_box"] = dict(box)
    if ev["type"] == "press_visual":
        out["visual"] = True
    if _box_map(ev.get("form_box")):
        out["form_box"] = mapper.box(*(ev["form_box"][k] for k in "xywh"))
    return out


def import_video(video, spec: dict, out_dir) -> dict:
    video, out_dir = Path(video), Path(out_dir)
    if not video.is_file():
        raise PipelineError(f"no existe el video {video.name}")
    cfg = validate_spec(spec, media_duration(video))
    source = video_size(video)
    mapper = Mapper(source, cfg["viewport"], cfg["crop"])
    windows = [(item.get("from", float("-inf")), item.get("to", float("inf")), mapper.box(*item["box"]))
               for item in cfg["blur"]]
    vw, vh = cfg["viewport"]
    filters = [f"fps={cfg['fps']}"]
    if cfg["crop"]:
        filters.append("crop={2}:{3}:{0}:{1}".format(*cfg["crop"]))
    filters.append(f"scale={vw}:{vh}:flags=lanczos")
    trim = ["-ss", f"{cfg['start']:.3f}"] + (["-to", f"{cfg['end']:.3f}"] if cfg["end"] is not None else [])
    raw = Path(tempfile.mkdtemp(prefix="import-take-"))
    work = out_dir.parent / f"{out_dir.name}.importing"
    try:
        # -ss/-to before -i: output timestamps start at 0 = trim start; frame k shows source time start + k/fps.
        run([which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", *trim, "-i", str(video), "-an",
             "-vf", ",".join(filters), str(raw / "%06d.png")], quiet=True)
        shutil.rmtree(work, ignore_errors=True)
        (work / "frames").mkdir(parents=True)
        frames = []
        for k, path in enumerate(sorted(raw.glob("*.png"))):
            t = cfg["start"] + k / cfg["fps"]
            boxes = [box for a, b, box in windows if a - 1e-6 <= t <= b + 1e-6]
            with Image.open(path) as img:
                frame = censor_frame(img.convert("RGB"), boxes)
            path.unlink()
            name = f"f{k:06d}.jpg"
            frame.save(work / "frames" / name, quality=QUALITY)
            frames.append({"file": name, "t": _r(k / cfg["fps"])})
        if not frames:
            raise PipelineError("el video no dio cuadros en el tramo de 'trim'")
        steps = [{"id": s["id"], "t0": _r(s["t0"] - cfg["start"]),
                  "events": [event_out(s["id"], ev, cfg["start"], mapper)
                             for ev in sorted(s.get("events") or [], key=lambda e: e["t"])],
                  "t1": _r(s["t1"] - cfg["start"]), "cursor": "recorded"} for s in cfg["steps"]]
        # A take of its own starts a new screen (like a recorder `goto`): compose cuts to it after the previous take.
        steps[0]["events"].insert(0, {"type": "goto", "t": steps[0]["t0"]})
        actions = {"viewport": [vw, vh], "steps": steps, "failure": None}
        (work / "frames.json").write_text(json.dumps({"frames": frames, "errors": 0}, indent=1), encoding="utf-8")
        (work / "actions.json").write_text(json.dumps(actions, indent=1, ensure_ascii=False), encoding="utf-8")
    except BaseException:
        shutil.rmtree(work, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(raw, ignore_errors=True)    # F3: the unblurred frames never stay on disk
    moved = keep_previous_take(out_dir.parent, out_dir=out_dir)
    if moved:
        print(f"[import] toma anterior guardada en {moved.name}")
    elif out_dir.exists():
        if any(out_dir.iterdir()):
            shutil.rmtree(work, ignore_errors=True)
            raise PipelineError(f"{out_dir} existe y no es una toma: muévela antes de importar")
        out_dir.rmdir()
    work.rename(out_dir)
    print(f"[import] {len(frames)} cuadros ({cfg['fps']:g} fps), {len(steps)} pasos, "
          f"{len(windows)} zonas difuminadas → {out_dir.as_posix()}")
    return actions


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", help="video del usuario (su audio no se usa)")
    ap.add_argument("--spec", required=True, help="especificación YAML (fps, trim, viewport, crop, blur, steps)")
    ap.add_argument("--out", required=True, help="carpeta de la toma (p.ej. proyectos/<slug>/takes/resultado)")
    a = ap.parse_args()
    path = Path(a.spec)
    if not path.is_file():
        raise PipelineError(f"no existe la especificación {path}")
    import_video(a.video, yaml.safe_load(path.read_text(encoding="utf-8")), a.out)


if __name__ == "__main__":
    main_guard(main)
