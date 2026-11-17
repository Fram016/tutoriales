---
name: tutorial-render
description: "Trigger: render, renderizar, exportar video, armar video, subtítulos, zoom, cursor, logo, marca, colores, vertical, reels, tiktok, 9:16, 16:9, compose, captions, branding, export. Builds HyperFrames compositions (compose.py) and renders the 16:9 full and 9:16 summary MP4s (render.py)."
license: Apache-2.0
metadata:
  author: tutoriales
  version: "1.0"
---

## Activation Contract

Use after mix. compose builds `proyectos/<slug>/hf-full/` (1920x1080) and `hf-short/` (1080x1920); render writes the MP4s.

## Hard Rules

- `.venv/Scripts/python.exe tools/compose.py <slug>` — adds intro (logo, title, subtitle), outro text, synthetic cursor with click ripples, automatic zoom on action boxes (max 2x), step chips and captions (7 words per chunk). It runs `hyperframes check`; any error fails the stage, warnings are counted.
- `.venv/Scripts/python.exe tools/render.py <slug> [--quality draft|looks|delivery] [--variant full|short]` → `proyectos/<slug>/out/<slug>-16x9.mp4` and `<slug>-9x16.mp4`. It verifies resolution, duration ≈ timeline total (±0.3 s) and an audio track.
- Quality: `draft` while iterating; `looks` (default) for review; `delivery` for the final file.
- Brand comes only from tutorial.yaml `brand:` + `proyectos/<slug>/<brand.dir>/logo.svg|logo.png` (svg preferred). Missing values fall back to defaults; compose prints "sin logo" when no logo was found — ask the user for it before the final render.
- Never edit `hf-*/index.html` by hand: compose regenerates it. Change tutorial.yaml (texts, brand) or the template `templates/composition.html` only if the user asks for a design change.

## Execution Steps

1. compose, then `render.py <slug> --quality draft`; or `.venv/Scripts/python.exe tools/pipeline.py <slug> --from compose --quality draft`.
2. Run `tutorial-qa`. After it passes, render the final: `.venv/Scripts/python.exe tools/pipeline.py <slug> --from compose --quality delivery`.
3. Failures: `No existe hf-<variant>/index.html` → run compose; check errors → read the listed lines, fix the input (usually tutorial.yaml text or brand), recompose; duration mismatch → rerun from `edit`.
4. The first HyperFrames run may download fonts/Chrome components; let it finish.

## Output Contract

Report output paths, resolution and duration of each MP4, quality preset used, and hyperframes check warnings.
