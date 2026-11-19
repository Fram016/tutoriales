"""Merge takes into one capture (I3, reglas/reglas-video.md §Parte 9; odd/tasks/perseo-instalacion.md T1).

Usage: python tools/merge_takes.py <out_project> <take_dir> [<take_dir> ...]

<out_project> is a project dir (or a slug under proyectos/). Writes <out_project>/capture/{frames/, frames.json,
actions.json, surfaces/<name>/...} as if one take had recorded the takes in order: each take's frames are renamed
with its prefix (t0_, t1_, ...) and every time (frames, steps t0/t1, events t/ts/t_end, surface windows and frames,
censor regions) is offset by the end of the previous takes plus GAP seconds. Step ids must be unique across takes.
Followed-tab info (`tab`, `censor`) is kept as recorded. Idempotent: a previous merge is replaced; a recorded take in
the way is moved to capture.prev-<timestamp>/ (capture.keep_previous_take). The source takes are only read.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from capture import keep_previous_take
from common import PROJECTS, PipelineError, main_guard, read_json, write_json

GAP = 0.2          # seconds between the end of a take and the start of the next
MARK = "merged.json"
EVENT_TIMES = ("t", "ts", "t_end", "t_down")


def _r(x: float) -> float:
    return round(x, 4)


def _shift(item: dict, keys, offset: float) -> dict:
    out = dict(item)
    for k in keys:
        if isinstance(out.get(k), (int, float)) and not isinstance(out.get(k), bool):
            out[k] = _r(out[k] + offset)
    return out


def read_take(take: Path) -> dict:
    """actions, frames and surface frames of a take dir; fails clearly on a missing or broken take."""
    if not (take / "actions.json").is_file() or not (take / "frames.json").is_file():
        raise PipelineError(f"{take} no es una toma (falta actions.json o frames.json)")
    actions = read_json(take / "actions.json")
    if actions.get("failure"):
        raise PipelineError(f"la toma {take.name} se cortó ({actions['failure']}): repítela antes de unirla")
    frames = read_json(take / "frames.json")
    surfaces = {name: read_json(take / spec.get("dir", f"surfaces/{name}") / "frames.json")["frames"]
                for name, spec in (actions.get("surfaces") or {}).items()}
    return {"dir": take, "actions": actions, "frames": frames, "surfaces": surfaces}


def take_end(t: dict) -> float:
    """Last time on the take's clock (frames, steps, surface windows and frames, censor regions)."""
    a = t["actions"]
    times = [f["t"] for f in t["frames"]["frames"]]
    times += [s.get("t1") or s.get("t0") or 0 for s in a.get("steps", [])]
    times += [w["t1"] for spec in (a.get("surfaces") or {}).values() for w in spec.get("windows", [])]
    times += [f["t"] for frames in t["surfaces"].values() for f in frames]
    times += [r["t1"] for r in a.get("censor_regions") or [] if r.get("t1") is not None]
    return max(times, default=0.0)


def project_path(arg: str) -> Path:
    path = Path(arg)
    return path if path.is_dir() else PROJECTS / arg


def merge_takes(out_project, take_dirs) -> dict:
    pdir = Path(out_project)
    takes = [Path(t) for t in take_dirs]
    if not takes:
        raise PipelineError("falta al menos una toma para unir")
    out = pdir / "capture"
    for take in takes:
        if take.resolve() == out.resolve() or out.resolve() in take.resolve().parents:
            raise PipelineError(f"una toma no puede ser la salida: {take}")
        if not take.is_dir():
            raise PipelineError(f"no existe la toma {take}")
    loaded = [read_take(t) for t in takes]
    viewports = {tuple(t["actions"].get("viewport") or (1920, 1080)) for t in loaded}
    if len(viewports) > 1:
        raise PipelineError(f"las tomas tienen distinto viewport: {sorted(viewports)}")
    seen: dict[str, str] = {}
    for t in loaded:
        for step in t["actions"].get("steps", []):
            if step["id"] in seen:
                raise PipelineError(f"el paso '{step['id']}' está en dos tomas ({seen[step['id']]} y {t['dir'].name}): "
                                    "los ids tienen que ser únicos")
            seen[step["id"]] = t["dir"].name

    work = pdir / "capture.merging"
    shutil.rmtree(work, ignore_errors=True)
    (work / "frames").mkdir(parents=True)
    frames, errors, steps, regions = [], 0, [], []
    surfaces: dict[str, dict] = {}
    surface_frames: dict[str, list] = {}
    offset, summary = 0.0, []
    for i, t in enumerate(loaded):
        prefix, a = f"t{i}_", t["actions"]
        for f in t["frames"]["frames"]:
            shutil.copy2(t["dir"] / "frames" / f["file"], work / "frames" / (prefix + f["file"]))
            frames.append({"file": prefix + f["file"], "t": _r(f["t"] + offset)})
        errors += int(t["frames"].get("errors") or 0)
        for step in a.get("steps", []):
            moved = _shift(step, ("t0", "t1"), offset)
            moved["events"] = [_shift(ev, EVENT_TIMES, offset) for ev in step.get("events", [])]
            steps.append(moved)
        regions += [_shift(r, ("t0", "t1"), offset) for r in a.get("censor_regions") or []]
        for name, spec in (a.get("surfaces") or {}).items():
            shape = {k: spec.get(k) for k in ("size", "dpr", "anchor")}
            merged = surfaces.setdefault(name, {**shape, "dir": f"surfaces/{name}", "windows": [], "frames": 0})
            if {k: merged[k] for k in shape} != shape:
                raise PipelineError(f"la superficie '{name}' tiene otro tamaño o posición en {t['dir'].name}")
            merged["windows"] += [_shift(w, ("t0", "t1"), offset) for w in spec.get("windows", [])]
            src = t["dir"] / spec.get("dir", f"surfaces/{name}") / "frames"
            dst = work / "surfaces" / name / "frames"
            dst.mkdir(parents=True, exist_ok=True)
            for f in t["surfaces"][name]:
                shutil.copy2(src / f["file"], dst / (prefix + f["file"]))
                surface_frames.setdefault(name, []).append({"file": prefix + f["file"], "t": _r(f["t"] + offset)})
            merged["frames"] += len(t["surfaces"][name])
        summary.append({"take": t["dir"].as_posix(), "prefix": prefix, "offset": _r(offset),
                        "steps": len(a.get("steps", []))})
        offset += take_end(t) + GAP
    actions = {"viewport": list(next(iter(viewports))), "steps": steps, "failure": None}
    if surfaces:
        actions["surfaces"] = surfaces
    if regions:
        actions["censor_regions"] = regions
    (work / "frames.json").write_text(json.dumps({"frames": frames, "errors": errors}, indent=1), encoding="utf-8")
    (work / "actions.json").write_text(json.dumps(actions, indent=1, ensure_ascii=False), encoding="utf-8")
    for name, items in surface_frames.items():
        (work / "surfaces" / name / "frames.json").write_text(json.dumps({"frames": items}, indent=1),
                                                                encoding="utf-8")
    write_json(work / MARK, {"takes": summary, "gap": GAP})

    if (out / MARK).exists():
        shutil.rmtree(out)                     # our own previous merge: replaced (idempotent)
    elif out.exists():
        moved = keep_previous_take(pdir, out_dir=out)
        if moved:
            print(f"[merge] toma anterior guardada en {moved.name}")
        elif any(out.iterdir()):
            raise PipelineError(f"{out} existe y no es una toma ni una unión: muévela antes de unir")
        else:
            out.rmdir()
    work.rename(out)
    print(f"[merge] {len(loaded)} tomas → {out.as_posix()}: {len(frames)} cuadros, {len(steps)} pasos, "
          f"{offset - GAP:.1f} s")
    return actions


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out_project", help="carpeta del proyecto (o slug) que recibe capture/")
    ap.add_argument("takes", nargs="+", help="carpetas de las tomas, en orden")
    a = ap.parse_args()
    merge_takes(project_path(a.out_project), a.takes)


if __name__ == "__main__":
    main_guard(main)
