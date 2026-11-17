"""Orchestrator: runs the stages of one tutorial in order.

Usage: python tools/pipeline.py <slug> [--from S] [--to S] [--only S] [--offline]
                                       [--quality draft|looks|delivery]

Stages: capture → tts → edit → music → mix → compose → render.
--offline applies to tts and music (silent voice + test pad, no API key needed).
Stops at the first failing stage and names it in the error.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import capture
import compose
import edit
import mix
import music
import render
import tts
from common import ROOT, PipelineError, load_tutorial, main_guard

STAGES = ["capture", "tts", "edit", "music", "mix", "compose", "render"]


def select(start: str | None, stop: str | None, only: str | None) -> list[str]:
    if only:
        if start or stop:
            raise PipelineError("--only no se combina con --from/--to")
        return [only]
    first = STAGES.index(start) if start else 0
    last = STAGES.index(stop) if stop else len(STAGES) - 1
    if first > last:
        raise PipelineError(f"--from {start} va después de --to {stop}")
    return STAGES[first:last + 1]


def run_stage(name: str, slug: str, offline: bool, quality: str):
    if name == "capture":
        return capture.capture(slug)
    if name == "tts":
        return tts.tts(slug, offline)
    if name == "edit":
        return edit.edit(slug)
    if name == "music":
        return music.music(slug, offline)
    if name == "mix":
        return mix.mix(slug)
    if name == "compose":
        return compose.compose(slug)
    return render.render(slug, quality)


def pipeline(slug: str, stages: list[str], offline: bool = False, quality: str = "looks") -> dict:
    tut = load_tutorial(slug)
    print(f"[pipeline] {tut['title']} ({slug}): {' → '.join(stages)}"
          f"{' [offline]' if offline else ''}")
    started = time.monotonic()
    results = {}
    for i, name in enumerate(stages, 1):
        print(f"\n=== [{i}/{len(stages)}] {name} ===")
        t0 = time.monotonic()
        try:
            results[name] = run_stage(name, slug, offline, quality)
        except PipelineError as exc:
            raise PipelineError(f"etapa '{name}' falló: {exc}") from exc
        print(f"--- {name}: {time.monotonic() - t0:.1f} s")
    print(f"\n[pipeline] ok en {time.monotonic() - started:.1f} s")
    for variant, info in (results.get("render") or {}).items():
        print(f"  {variant}: {Path(info['path']).relative_to(ROOT)} ({info['duration']:.1f} s)")
    return results


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug")
    ap.add_argument("--from", dest="start", choices=STAGES)
    ap.add_argument("--to", dest="stop", choices=STAGES)
    ap.add_argument("--only", choices=STAGES)
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--quality", choices=["draft", "looks", "delivery"], default="looks")
    a = ap.parse_args()
    pipeline(a.slug, select(a.start, a.stop, a.only), a.offline, a.quality)


if __name__ == "__main__":
    main_guard(main)
