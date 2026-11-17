"""Stage: render. Renders the HyperFrames projects from compose.py to the final MP4s.

Usage: python tools/render.py <slug> [--quality draft|looks|delivery] [--variant full|short]

Writes proyectos/<slug>/out/<slug>-16x9.mp4 (full) and <slug>-9x16.mp4 (short), then
verifies each with ffprobe: resolution, duration ≈ timeline total (±0.3 s) and an audio track.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import ROOT, PipelineError, load_tutorial, main_guard, project_dir, read_json, run, which
from compose import LAYOUTS, hyperframes

OUTPUTS = {"full": "16x9", "short": "9x16"}
DURATION_TOLERANCE = 0.3


def hf_dir(pdir: Path, variant: str) -> Path:
    path = pdir / f"hf-{variant}"
    if not (path / "index.html").exists():
        raise PipelineError(f"No existe {path.name}/index.html. Corré antes compose.py.")
    return path


def probe(path: Path) -> dict:
    out = run([which("ffprobe"), "-v", "error", "-show_entries",
               "stream=codec_type,codec_name,width,height:format=duration", "-of", "json", str(path)],
              quiet=True).stdout
    return json.loads(out)


def verify(path: Path, size: list[int], total: float) -> dict:
    info = probe(path)
    video = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    audio = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    duration = float(info["format"]["duration"])
    problems = []
    if not video or [video["width"], video["height"]] != list(size):
        got = f"{video['width']}x{video['height']}" if video else "sin video"
        problems.append(f"resolución {got} (esperaba {size[0]}x{size[1]})")
    if abs(duration - total) > DURATION_TOLERANCE:
        problems.append(f"duración {duration:.2f} s (esperaba {total:.2f} s)")
    if not audio:
        problems.append("no tiene pista de audio")
    if problems:
        raise PipelineError(f"{path.name}: " + "; ".join(problems))
    return {"path": str(path), "width": video["width"], "height": video["height"], "duration": duration,
            "video": video["codec_name"], "audio": audio["codec_name"]}


def render_variant(slug: str, pdir: Path, variant: str, quality: str) -> dict:
    src = hf_dir(pdir, variant)
    timeline = read_json(pdir / "edit" / variant / "timeline.json")
    out = pdir / "out" / f"{slug}-{OUTPUTS[variant]}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"[render] {variant}: renderizando ({quality})...")
    hyperframes("render", src, "-o", out, "--quality", quality, "--video-frame-format", "png", "--quiet")
    if not out.exists():
        raise PipelineError(f"HyperFrames terminó sin escribir {out}")
    result = verify(out, list(LAYOUTS[variant]["size"]), timeline["total"])
    print(f"[render] {variant}: {result['width']}x{result['height']}, {result['duration']:.2f} s, "
          f"{result['video']} + {result['audio']} → {out.relative_to(ROOT)}")
    return result


def render(slug: str, quality: str = "looks", variant: str | None = None) -> dict:
    load_tutorial(slug)
    pdir = project_dir(slug)
    names = [variant] if variant else [v for v in OUTPUTS if (pdir / f"hf-{v}").exists()]
    if not names:
        raise PipelineError("No hay proyectos hf-*/. Corré antes compose.py.")
    return {v: render_variant(slug, pdir, v, quality) for v in names}


def snapshots(slug: str, variant: str, times: list[float]) -> list[Path]:
    """PNG stills of hf-<variant> at the given seconds (for QA). Returns their paths in time order."""
    src = hf_dir(project_dir(slug), variant)
    out = src / ".hyperframes" / "artifacts" / "snapshots" / "qa"
    out.mkdir(parents=True, exist_ok=True)
    at = ",".join(f"{t:g}" for t in times)
    hyperframes("snapshot", src, "--at", at, "--no-end", "--keep", "-o", out)
    paths = [out / f"at-{round(t, 3):g}s.png" for t in times]
    missing = [p.name for p in paths if not p.exists()]
    if missing:
        raise PipelineError(f"hyperframes snapshot no escribió: {', '.join(missing)}")
    return paths


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug")
    ap.add_argument("--quality", choices=["draft", "looks", "delivery"], default="looks")
    ap.add_argument("--variant", choices=list(OUTPUTS))
    args = ap.parse_args()
    render(args.slug, args.quality, args.variant)


if __name__ == "__main__":
    main_guard(main)
