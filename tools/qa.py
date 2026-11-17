"""Stage: QA. Checks the rendered outputs and takes stills for a visual review.

Usage: python tools/qa.py <slug> [--variant full|short]

For each proyectos/<slug>/out/<slug>-16x9.mp4 (full) / -9x16.mp4 (short): resolution,
duration vs edit/<variant>/timeline.json total (±0.3 s), audio track present and integrated
loudness within ±1 LU of LOUDNESS_TARGET (default -14). Then snapshots at the intro midpoint,
the middle of each step and the outro midpoint; their PNG paths are printed so an agent can
look at them. Prints a PASS/FAIL table and exits 1 if any check fails.
"""
from __future__ import annotations

import argparse
import sys

from common import ROOT, PipelineError, env, load_tutorial, main_guard, project_dir, read_json
from compose import LAYOUTS
from mix import measure
from render import DURATION_TOLERANCE, OUTPUTS, probe, snapshots

LOUDNESS_TOLERANCE = 1.0


def snapshot_times(timeline: dict) -> list[float]:
    times = [timeline["intro"] / 2]
    times += [s["start"] + s["duration"] / 2 for s in timeline["steps"]]
    times.append(timeline["total"] - timeline["outro"] / 2)
    return [round(t, 3) for t in times]


def check_variant(slug: str, pdir, variant: str) -> tuple[list[tuple[str, bool, str]], list]:
    out = pdir / "out" / f"{slug}-{OUTPUTS[variant]}.mp4"
    rows = []
    if not out.exists():
        return [("archivo", False, f"no existe {out.relative_to(ROOT)}")], []
    timeline = read_json(pdir / "edit" / variant / "timeline.json")
    info = probe(out)
    video = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    audio = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    w, h = LAYOUTS[variant]["size"]
    got = f"{video['width']}x{video['height']}" if video else "sin video"
    rows.append(("resolución", got == f"{w}x{h}", f"{got} (esperado {w}x{h})"))
    duration = float(info["format"]["duration"])
    rows.append(("duración", abs(duration - timeline["total"]) <= DURATION_TOLERANCE,
                 f"{duration:.2f} s (esperado {timeline['total']:.2f} ±{DURATION_TOLERANCE} s)"))
    rows.append(("audio", audio is not None, audio["codec_name"] if audio else "sin pista de audio"))
    if audio:
        target = float(env("LOUDNESS_TARGET", "-14"))
        lufs = float(measure(out)["input_i"])
        rows.append(("sonoridad", abs(lufs - target) <= LOUDNESS_TOLERANCE,
                     f"{lufs:.1f} LUFS (objetivo {target:g} ±{LOUDNESS_TOLERANCE:g} LU)"))
    shots = []
    try:
        shots = snapshots(slug, variant, snapshot_times(timeline))
        rows.append(("capturas", True, f"{len(shots)} PNG"))
    except PipelineError as exc:
        rows.append(("capturas", False, str(exc).splitlines()[0]))
    return rows, shots


def qa(slug: str, variant: str | None = None) -> bool:
    load_tutorial(slug)
    pdir = project_dir(slug)
    names = [variant] if variant else [v for v in OUTPUTS if (pdir / "edit" / v / "timeline.json").exists()]
    if not names:
        raise PipelineError("No hay timelines en edit/. Corré antes el pipeline.")
    passed = True
    print(f"[qa] {slug}")
    print(f"  {'variante':<8} {'chequeo':<11} {'estado':<6} detalle")
    all_shots = {}
    for name in names:
        rows, shots = check_variant(slug, pdir, name)
        all_shots[name] = shots
        for check, ok, detail in rows:
            passed &= ok
            print(f"  {name:<8} {check:<11} {'PASS' if ok else 'FAIL':<6} {detail}")
    for name, shots in all_shots.items():
        if shots:
            print(f"[qa] capturas {name} (revisalas visualmente):")
            for path in shots:
                print(f"  {path}")
    print(f"[qa] {'PASS' if passed else 'FAIL'}")
    return passed


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug")
    ap.add_argument("--variant", choices=list(OUTPUTS))
    a = ap.parse_args()
    if not qa(a.slug, a.variant):
        sys.exit(1)


if __name__ == "__main__":
    main_guard(main)
