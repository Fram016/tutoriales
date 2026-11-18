"""Stage: render. Renders the HyperFrames projects from compose.py to the final MP4s.

Usage: python tools/render.py <slug> [--quality draft|looks|delivery] [--video ID]
       python tools/render.py --project DIR [--out FILE.mp4] [--quality ...] [--snap 1.5,4,9.2]

Writes proyectos/<slug>/out/<slug>-<video>.mp4 for every hf-<video>/, then verifies each with
ffprobe: resolution (16:9 -> 1920x1080, 9:16 -> 1080x1920), duration ≈ timeline total (±0.3 s)
and an audio track. Renders with --page-motion-blur off (C2: no smeared or doubled frames) and
PNG frame extraction (crisp UI text).
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from common import ROOT, PipelineError, load_tutorial, main_guard, project_dir, read_json, run, which
from compose import FORMATS, hyperframes

# Back-compat for readers keyed by format.
OUTPUTS = {"16:9": "16x9", "9:16": "9x16"}
DURATION_TOLERANCE = 0.3


def hf_dir(pdir: Path, video: str) -> Path:
    path = pdir / f"hf-{video}"
    if not (path / "index.html").exists() or not (path / "layout.json").exists():
        raise PipelineError(f"No existe {path.name}/index.html con layout.json. Corré antes compose.py.")
    return path


def probe(path: Path) -> dict:
    out = run([which("ffprobe"), "-v", "error", "-show_entries",
               "stream=codec_type,codec_name,width,height:format=duration", "-of", "json", str(path)],
              quiet=True).stdout
    return json.loads(out)


def expected_size(layout: dict) -> list[int]:
    fmt = layout.get("format")
    return list(FORMATS[fmt]["size"]) if fmt in FORMATS else list(layout["output"])


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


def render_project(src: Path, out: Path, quality: str) -> dict:
    """Renders one hf-* project to `out` and checks it against its layout.json."""
    layout = read_json(src / "layout.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"[render] {src.name}: renderizando ({quality})...")
    hyperframes("render", src, "-o", out, "--quality", quality, "--video-frame-format", "png",
                "--page-motion-blur", "off", "--quiet")
    if not out.exists():
        raise PipelineError(f"HyperFrames terminó sin escribir {out}")
    result = verify(out, expected_size(layout), layout["total"])
    print(f"[render] {src.name}: {result['width']}x{result['height']}, {result['duration']:.2f} s, "
          f"{result['video']} + {result['audio']} -> {out}")
    return result


def videos(pdir: Path) -> list[str]:
    return sorted(p.parent.name[3:] for p in pdir.glob("hf-*/layout.json"))


def render(slug: str, quality: str = "looks", video: str | None = None) -> dict:
    load_tutorial(slug)
    pdir = project_dir(slug)
    names = [video] if video else videos(pdir)
    if not names:
        raise PipelineError("No hay proyectos hf-*/ con layout.json. Corré antes compose.py.")
    return {v: render_project(hf_dir(pdir, v), pdir / "out" / f"{slug}-{v}.mp4", quality) for v in names}


def snapshot_project(src: Path, times: list[float]) -> list[Path]:
    """PNG stills at the given seconds in a new numbered folder (earlier rounds are kept)."""
    base = src / ".hyperframes" / "artifacts" / "snapshots"
    base.mkdir(parents=True, exist_ok=True)
    taken = [int(m.group(1)) for p in base.glob("qa-*") if (m := re.fullmatch(r"qa-(\d+)", p.name))]
    out = base / f"qa-{max(taken, default=0) + 1:02d}"
    out.mkdir()
    at = ",".join(f"{t:g}" for t in times)
    hyperframes("snapshot", src, "--at", at, "--no-end", "--keep", "-o", out)
    paths = [out / f"at-{round(t, 3):g}s.png" for t in times]
    missing = [p.name for p in paths if not p.exists()]
    if missing:
        raise PipelineError(f"hyperframes snapshot no escribió: {', '.join(missing)}")
    return paths


def snapshots(slug: str, video: str, times: list[float]) -> list[Path]:
    """PNG stills of hf-<video> at the given seconds (for QA). Returns their paths in time order."""
    return snapshot_project(hf_dir(project_dir(slug), video), times)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--quality", choices=["draft", "looks", "delivery"], default="looks")
    ap.add_argument("--video", help="id del video (por defecto: todos los hf-*/)")
    ap.add_argument("--project", type=Path, help="render a single hf-* folder (e.g. a compose --fixture)")
    ap.add_argument("--out", type=Path, help="output mp4 for --project (default: <project>.mp4)")
    ap.add_argument("--snap", help="with --project: comma-separated seconds to snapshot instead of rendering")
    args = ap.parse_args()
    if args.project:
        if args.snap:
            for path in snapshot_project(args.project, [float(t) for t in args.snap.split(",")]):
                print(path)
        else:
            render_project(args.project, args.out or args.project.with_suffix(".mp4"), args.quality)
    elif args.slug:
        render(args.slug, args.quality, args.video)
    else:
        ap.error("falta el slug (o --project)")


if __name__ == "__main__":
    main_guard(main)
