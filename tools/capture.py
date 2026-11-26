"""Stage: capture. Runs the tutorial.yaml actions in ego-lite while recording frames.

Usage: python tools/capture.py <slug>

Writes proyectos/<slug>/capture/{frames/, frames.json, actions.json} and, for every surface of
tutorial.yaml (an extension popup), capture/surfaces/<name>/{frames/, frames.json}.
Credentials referenced as env:NAME are injected into a temporary take script that is
deleted right after the run, so secrets never stay on disk next to the project. The same goes
for censor patterns written as env:NAME (a person's name kept in acceso.local.yaml).
A previous take is never wiped: it is moved to capture.prev-<timestamp>/ (the newest KEEP_PREVIOUS kept),
so a failed take (e.g. a captcha) does not leave the project without a usable take.
D4: `show_download_dir.path` may name environment variables (%USERPROFILE%); they are expanded here and the path is
never printed (it carries the Windows user name). Display only: the recorder writes it into the settings row; the
browser's download folder is never changed.
I3 (§Parte 9): `--config install.yaml --out takes/install` records another take config of the project (same schema)
into its own take dir, merged later with tools/merge_takes.py. I2: a `simulate_dialog.icon` path (relative to the
project) is sent to the recorder as a data URL; top-level `hide` hides notices of the recording browser on the page.
S7 (one take per part): `--by-part` records each `part` of tutorial.yaml (its steps only) into takes/part-<n> and
merges them in part order into capture/ (merge_takes); `--part N` re-records only part N (the previous take kept as
takes/part-N.prev-<timestamp>) and merges again. Each part opens a new tab at app_url with the app as it is (session,
data: nothing is reset); a part that needs another screen starts with its own `goto`. A failed part leaves the other
takes and capture/ untouched and names the command that re-records it.

Usage: python tools/capture.py <slug> [--config FILE] [--out DIR] | [--by-part | --part N]
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import time
from pathlib import Path

from common import (PipelineError, ROOT, is_secret_ref, load_tutorial, main_guard, project_dir,
                    read_json, resolve_env_ref, run, which)

RECORDER = ROOT / "tools" / "capture" / "recorder.mjs"


ENV_VAR = re.compile(r"%([A-Za-z_][A-Za-z0-9_]*)%")


def expand_path(path: str) -> str:
    """D4: %NAME% replaced by the environment variable NAME. A missing one names only the variable."""
    def value(m):
        found = os.environ.get(m.group(1))
        if not found:
            raise PipelineError(f"show_download_dir: falta la variable de entorno {m.group(1)}")
        return found
    return ENV_VAR.sub(value, path)


def icon_data_url(pdir: Path | None, path: str) -> str:
    """I2: the dialog icon (a PNG of the project) as a data URL the page can show."""
    file = (pdir or ROOT) / path
    if not file.is_file():
        raise PipelineError(f"simulate_dialog: no existe el ícono {path}")
    return "data:image/png;base64," + base64.b64encode(file.read_bytes()).decode("ascii")


def resolve_actions(steps: list[dict], pdir: Path | None = None) -> list[dict]:
    resolved = []
    for step in steps:
        actions = []
        for action in step.get("actions", []):
            if not isinstance(action, dict) or len(action) != 1:
                raise PipelineError(f"Paso {step['id']}: cada acción es un mapa de una sola clave, p.ej. {{click: '#btn'}}")
            kind, arg = next(iter(action.items()))
            if kind == "type":
                arg = dict(arg)
                arg["secret"] = is_secret_ref(arg.get("text"))
                arg["text"] = resolve_env_ref(arg.get("text", ""))
            elif kind == "goto":
                arg = resolve_env_ref(arg)
            elif kind == "show_download_dir":
                arg = {**arg, "path": expand_path(arg["path"])}
            elif kind == "simulate_dialog" and arg.get("icon"):
                arg = {**arg, "icon": icon_data_url(pdir, arg["icon"])}
            actions.append({kind: arg})
        resolved.append({"id": step["id"], "actions": actions, "hold_ms": step.get("hold_ms", 600)})
    return resolved


def resolve_censor(censor: dict | None) -> dict | None:
    """S3: censor for the recorder, env:NAME patterns resolved (never printed); N25 regex_flags as `flags`."""
    if not censor:
        return None
    return {"selectors": list(censor.get("selectors") or []),
            "text": [resolve_env_ref(p) for p in censor.get("text") or []],
            "flags": censor.get("regex_flags", "i")}


def resolve_surfaces(surfaces: dict | None) -> dict:
    """S5: what the recorder needs of each surface (compose reads `icon` from tutorial.yaml); N23 `hide`."""
    return {name: {"url": resolve_env_ref(spec["url"]), "size": list(spec["size"]), "dpr": spec.get("dpr", 1),
                   "anchor": spec.get("anchor", "top-right"), "target_tab": spec.get("target_tab"),
                   "hide": list(spec.get("hide") or [])}
            for name, spec in (surfaces or {}).items()}


KEEP_PREVIOUS = 2


def keep_previous_take(pdir: Path, now: float | None = None, out_dir: Path | None = None) -> Path | None:
    """Move capture/ (or the take dir `out_dir`, if it holds a take) to <name>.prev-<timestamp>/ next to it; prune
    the oldest beyond KEEP_PREVIOUS."""
    out_dir = out_dir or pdir / "capture"
    if not (out_dir / "actions.json").exists():
        return None
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now if now is not None else time.time()))
    parent, name = out_dir.parent, out_dir.name
    dest = parent / f"{name}.prev-{stamp}"
    n = 1
    while dest.exists():
        n += 1
        dest = parent / f"{name}.prev-{stamp}-{n}"
    out_dir.rename(dest)
    for old in sorted(parent.glob(f"{name}.prev-*"))[:-KEEP_PREVIOUS]:
        shutil.rmtree(old, ignore_errors=True)
    return dest


PYTHON = ".venv/Scripts/python.exe"


def part_steps(tut: dict, n: int) -> list[dict]:
    """S7: the steps of part n, in order."""
    steps = [s for s in tut["steps"] if s.get("part") == n]
    if not steps:
        raise PipelineError(f"la parte {n} no tiene pasos en tutorial.yaml (partes: "
                            f"{', '.join(map(str, part_numbers(tut)))})")
    return steps


def part_numbers(tut: dict) -> list[int]:
    """S7: the parts that have steps, in order."""
    if not tut.get("parts"):
        raise PipelineError(f"tutorial.yaml no tiene 'parts' (N16): graba la toma entera con "
                            f"{PYTHON} tools/capture.py {tut['slug']}")
    return sorted({s["part"] for s in tut["steps"] if "part" in s})


def part_take_dir(n: int) -> str:
    return f"takes/part-{n}"


def rerecord_command(slug: str, n: int) -> str:
    return f"{PYTHON} tools/capture.py {slug} --part {n}"


def take_config(slug: str, file: str = "tutorial.yaml", out: str | None = None,
                part: int | None = None) -> tuple[dict, Path, dict]:
    """(tutorial, take dir, recorder config) of a take: tutorial.yaml into capture/ by default; I3: another take
    config of the project (install.yaml) into a take dir inside the project (takes/install); S7: only the steps of
    `part`."""
    tut = load_tutorial(slug, file)
    pdir = project_dir(slug)
    out_dir = pdir / out if out else pdir / "capture"
    if out and pdir.resolve() not in out_dir.resolve().parents:
        raise PipelineError("--out tiene que quedar dentro del proyecto (p.ej. takes/install)")
    config = {
        "outDir": out_dir.as_posix(),
        "steps": resolve_actions(tut["steps"] if part is None else part_steps(tut, part), pdir),
        "viewport": tut.get("viewport", [1920, 1080]),
        "startUrl": resolve_env_ref(tut.get("app_url")),
        "censor": resolve_censor(tut.get("censor")),
        "surfaces": resolve_surfaces(tut.get("surfaces")),
        "hide": list(tut.get("hide") or []),
    }
    return tut, out_dir, config


def capture(slug: str, file: str = "tutorial.yaml", out: str | None = None, part: int | None = None) -> dict:
    tut, out_dir, config = take_config(slug, file, out, part)
    pdir = project_dir(slug)
    previous = keep_previous_take(pdir, out_dir=out_dir)
    if previous:
        print(f"[capture] toma anterior guardada en {previous.name}")
    build = pdir / "build"
    build.mkdir(parents=True, exist_ok=True)
    take = build / "take.mjs"
    # Config on its own line: a Node error that echoes the failing call line shows no secrets.
    take.write_text(
        f"const {{ take }} = await import({json.dumps(RECORDER.as_uri())});\n"
        f"const config = {json.dumps(config, ensure_ascii=False)};\n"
        f"const task = await taskSpace({json.dumps('tutorial ' + slug)});\n"
        f"try {{\n  await take(task, config);\n"
        f"}} finally {{\n  await task.finish({{ keep: [] }});\n}}\n",
        encoding="utf-8",
    )
    try:
        which_part = f", parte {part}" if part is not None else ""
        print(f"[capture] grabando '{tut['title']}' en ego-lite ({len(config['steps'])} pasos{which_part})...")
        result = run([which("ego-browser"), "nodejs", "-e", f"await import({json.dumps(take.as_uri())})"],
                     quiet=True, timeout=1800)
        for line in result.stdout.splitlines():
            if line.startswith("[take]"):
                print("  " + line)
    finally:
        take.unlink(missing_ok=True)
    actions = read_json(out_dir / "actions.json")
    frames = read_json(out_dir / "frames.json")["frames"]
    if actions.get("failure"):
        raise PipelineError(f"La toma se cortó: {actions['failure']}. Revisa el selector en tutorial.yaml y repite.")
    if len(frames) < 10:
        raise PipelineError(f"Solo se capturaron {len(frames)} cuadros")
    fps = len(frames) / max(frames[-1]["t"], 0.001)
    print(f"[capture] ok: {len(frames)} cuadros (~{fps:.1f} fps), {len(actions['steps'])} pasos")
    for name, surface in (actions.get("surfaces") or {}).items():
        print(f"[capture] superficie {name}: {surface['frames']} cuadros en {len(surface['windows'])} apertura(s)")
    for step in actions["steps"]:
        for ev in step["events"]:
            if ev.get("tab") == "follow" and ev.get("censor"):
                print(f"[capture] pestaña seguida en {step['id']}: censura por {ev['censor']} (N25)")
    if actions.get("censor_regions"):
        print(f"[capture] {len(actions['censor_regions'])} región(es) de censura para compose (N25)")
    return actions


def capture_parts(slug: str, part: int | None = None) -> dict:
    """S7: record every part (or only `part`) into takes/part-<n>, then merge all part takes into capture/."""
    import merge_takes  # merge_takes imports this module (keep_previous_take)
    tut = load_tutorial(slug)
    pdir = project_dir(slug)
    numbers = part_numbers(tut)
    if part is not None:
        part_steps(tut, part)
    todo = numbers if part is None else [part]
    for n in todo:
        try:
            capture(slug, out=part_take_dir(n), part=n)
        except PipelineError as exc:
            pending = [str(m) for m in todo if m > n]
            then = f" y después graba las partes que faltan: {', '.join(pending)} (--part N)." if pending else ""
            raise PipelineError(f"La parte {n} falló: {exc} Las tomas de las otras partes quedan intactas y "
                                f"capture/ no cambió. Regrábala sola con: {rerecord_command(slug, n)}{then}") from exc
    missing = [n for n in numbers if not (pdir / part_take_dir(n) / "actions.json").is_file()]
    if missing:
        raise PipelineError(f"La toma de la parte {part} quedó en {part_take_dir(part)}, pero capture/ no se unió: "
                            f"faltan las tomas de las partes {', '.join(map(str, missing))}. Grábalas con: "
                            + "; ".join(rerecord_command(slug, n) for n in missing))
    return merge_takes.merge_takes(pdir, [pdir / part_take_dir(n) for n in numbers])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug")
    ap.add_argument("--config", default="tutorial.yaml", help="otra configuración de toma del proyecto (I3: install.yaml)")
    ap.add_argument("--out", help="carpeta de la toma dentro del proyecto (I3: takes/install); por defecto capture/")
    by = ap.add_mutually_exclusive_group()
    by.add_argument("--by-part", action="store_true",
                    help="S7: una toma por parte de tutorial.yaml en takes/part-<n>, unidas en capture/")
    by.add_argument("--part", type=int, metavar="N",
                    help="S7: regraba solo la parte N en takes/part-N y vuelve a unir capture/")
    a = ap.parse_args()
    if a.by_part or a.part is not None:
        if a.config != "tutorial.yaml" or a.out:
            ap.error("--by-part y --part graban tutorial.yaml en takes/part-<n>: no van con --config ni --out")
        capture_parts(a.slug, a.part)
    else:
        capture(a.slug, a.config, a.out)


if __name__ == "__main__":
    main_guard(main)
