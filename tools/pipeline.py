"""Orchestrator: runs the stages of one tutorial in order.

Usage: python tools/pipeline.py <slug> [--from S] [--to S] [--only S] [--offline]
                                       [--quality draft|looks|delivery] [--video ID]

Stages: lint → capture → tts → edit → music → mix → compose → render.
lint validates tutorial.yaml against reglas/reglas-video.md before anything else; it runs first on every run, partial ones included.
capture and tts always cover every video (one take, shared voice cache);
--video ID limits edit, music, mix, compose and render to that video.
--offline applies to tts and music (silent voice + test pad, no API key needed).
Stops at the first failing stage and names it in the error; prints a table of stage timings at the end.

Fast workflow (odd/tasks/reglas-ronda2.md L4): `--to compose`, then `python tools/qa.py <slug> --pre`
(no MP4) and the fix loop, then ONE `--only render --quality delivery` (`--video ID` re-renders only
a failing video).
"""
from __future__ import annotations

import argparse
import inspect
import time
from pathlib import Path

import capture
import compose
import edit
import mix
import music
import render
import tts
from common import ROOT, PipelineError, load_tutorial, main_guard, videos

STAGES = ["lint", "capture", "tts", "edit", "music", "mix", "compose", "render"]


def select(start: str | None, stop: str | None, only: str | None) -> list[str]:
    """The stages to run; lint always runs first (seconds) so a partial run never builds on a broken tutorial.yaml."""
    if only:
        if start or stop:
            raise PipelineError("--only no se combina con --from/--to")
        stages = [only]
    else:
        first = STAGES.index(start) if start else 0
        last = STAGES.index(stop) if stop else len(STAGES) - 1
        if first > last:
            raise PipelineError(f"--from {start} va después de --to {stop}")
        stages = STAGES[first:last + 1]
    return stages if stages[0] == "lint" else ["lint", *stages]


def run_lint(slug: str) -> list[str]:
    try:
        import lint  # written separately (tools/lint.py); the pipeline still imports without it
    except ImportError as exc:
        raise PipelineError(f"no encontré tools/lint.py ({exc}); sin lint no se valida tutorial.yaml "
                            "contra las reglas. Usa --from capture para saltarla.") from exc
    warnings = lint.lint(slug) or []
    for w in warnings:
        print(f"  aviso: {w}")
    return warnings


def timing_table(timings: list[tuple[str, float, str]]) -> str:
    """etapa | seconds | share | status, so the agent sees where the time goes (S2)."""
    total = sum(t for _, t, _ in timings)
    rows = [f"  {'etapa':<9} {'s':>7} {'%':>5}  estado"]
    rows += [f"  {name:<9} {t:7.1f} {100 * t / (total or 1):4.0f}%  {status}" for name, t, status in timings]
    rows.append(f"  {'total':<9} {total:7.1f}")
    return "\n[pipeline] tiempos por etapa:\n" + "\n".join(rows)


def run_stage(name: str, slug: str, offline: bool, quality: str, video: str | None = None):
    if name == "lint":
        return run_lint(slug)
    if name == "capture":
        return capture.capture(slug)
    if name == "tts":
        return tts.tts(slug, offline)
    if name == "edit":
        return edit.edit(slug, video)
    if name == "music":
        return music.music(slug, offline, video=video)
    if name == "mix":
        return mix.mix(slug, video)
    if name == "compose":
        if video and "video" in inspect.signature(compose.compose).parameters:
            return compose.compose(slug, video=video)
        return compose.compose(slug)
    return render.render(slug, quality, video)


def pipeline(slug: str, stages: list[str], offline: bool = False, quality: str = "looks",
             video: str | None = None) -> dict:
    tut = load_tutorial(slug)
    if video:
        videos(tut, video)  # unknown id fails before any stage runs
    print(f"[pipeline] {tut['title']} ({slug}): {' → '.join(stages)}"
          f"{f' [video {video}]' if video else ''}{' [offline]' if offline else ''}")
    started = time.monotonic()
    results, timings = {}, []
    for i, name in enumerate(stages, 1):
        print(f"\n=== [{i}/{len(stages)}] {name} ===")
        t0 = time.monotonic()
        try:
            results[name] = run_stage(name, slug, offline, quality, video)
        except PipelineError as exc:
            timings.append((name, time.monotonic() - t0, "falló"))
            print(timing_table(timings))
            raise PipelineError(f"etapa '{name}' falló: {exc}") from exc
        timings.append((name, time.monotonic() - t0, "ok"))
        print(f"--- {name}: {timings[-1][1]:.1f} s")
    print(f"\n[pipeline] ok en {time.monotonic() - started:.1f} s")
    print(timing_table(timings))
    rendered = results.get("render")
    if isinstance(rendered, dict):
        for vid, info in rendered.items():
            if isinstance(info, dict) and info.get("path"):
                print(f"  {vid}: {Path(info['path']).relative_to(ROOT)} ({info.get('duration', 0):.1f} s)")
    return results


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug")
    ap.add_argument("--from", dest="start", choices=STAGES)
    ap.add_argument("--to", dest="stop", choices=STAGES)
    ap.add_argument("--only", choices=STAGES)
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--quality", choices=["draft", "looks", "delivery"], default="looks")
    ap.add_argument("--video", help="solo este video en edit..render (id de tutorial.yaml)")
    a = ap.parse_args()
    pipeline(a.slug, select(a.start, a.stop, a.only), a.offline, a.quality, a.video)


if __name__ == "__main__":
    main_guard(main)
