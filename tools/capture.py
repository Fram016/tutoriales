"""Stage: capture. Runs the tutorial.yaml actions in ego-lite while recording frames.

Usage: python tools/capture.py <slug>

Writes proyectos/<slug>/capture/{frames/, frames.json, actions.json}.
Credentials referenced as env:NAME are injected into a temporary take script that is
deleted right after the run, so secrets never stay on disk next to the project.
"""
from __future__ import annotations

import argparse
import json

from common import (PipelineError, ROOT, is_secret_ref, load_tutorial, main_guard, project_dir,
                    read_json, resolve_env_ref, run, which)

RECORDER = ROOT / "tools" / "capture" / "recorder.mjs"


def resolve_actions(steps: list[dict]) -> list[dict]:
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
            actions.append({kind: arg})
        resolved.append({"id": step["id"], "actions": actions, "hold_ms": step.get("hold_ms", 600)})
    return resolved


def capture(slug: str) -> dict:
    tut = load_tutorial(slug)
    pdir = project_dir(slug)
    out_dir = pdir / "capture"
    build = pdir / "build"
    build.mkdir(parents=True, exist_ok=True)
    config = {
        "outDir": out_dir.as_posix(),
        "steps": resolve_actions(tut["steps"]),
        "viewport": tut.get("viewport", [1920, 1080]),
        "startUrl": resolve_env_ref(tut.get("app_url")),
    }
    take = build / "take.mjs"
    take.write_text(
        f"const {{ take }} = await import({json.dumps(RECORDER.as_uri())});\n"
        f"const task = await taskSpace({json.dumps('tutorial ' + slug)});\n"
        f"try {{\n  await take(task, {json.dumps(config, ensure_ascii=False)});\n"
        f"}} finally {{\n  await task.finish({{ keep: [] }});\n}}\n",
        encoding="utf-8",
    )
    try:
        print(f"[capture] grabando '{tut['title']}' en ego-lite ({len(config['steps'])} pasos)...")
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
        raise PipelineError(f"La toma se cortó: {actions['failure']}. Revisá el selector en tutorial.yaml y repetí.")
    if len(frames) < 10:
        raise PipelineError(f"Solo se capturaron {len(frames)} cuadros")
    fps = len(frames) / max(frames[-1]["t"], 0.001)
    print(f"[capture] ok: {len(frames)} cuadros (~{fps:.1f} fps), {len(actions['steps'])} pasos")
    return actions


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug")
    capture(ap.parse_args().slug)


if __name__ == "__main__":
    main_guard(main)
