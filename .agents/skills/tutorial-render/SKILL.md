---
name: tutorial-render
description: "Trigger: render, renderizar, exportar video, armar video, subtítulos, zoom, cámara, cursor, logo, marca, colores, vertical, reels, tiktok, 9:16, 16:9, compose, captions, branding, export, layout. Builds one HyperFrames composition per video (compose.py: camera, cursor, overlays, real 9:16 reframe, layout.json) and renders out/<slug>-<video>.mp4 (render.py)."
license: Apache-2.0
metadata:
  author: tutoriales
  version: "2.0"
---

## Activation Contract

Use after mix. For every entry in `videos:`, compose builds `proyectos/<slug>/hf-<video>/` (+ `layout.json`) and render writes `out/<slug>-<video>.mp4`. Rules by ID: `reglas/reglas-video.md`.

## Hard Rules

- `.venv/Scripts/python.exe tools/compose.py <slug>` — builds every video and runs `hyperframes check`; any error fails the stage, warnings are counted.
- `.venv/Scripts/python.exe tools/render.py <slug> [--quality draft|looks|delivery] [--video <id>]` → `out/<slug>-<id>.mp4`, always with `--page-motion-blur off` (C2 ghosting). It verifies resolution, duration ≈ timeline total (±0.3 s) and an audio track.
- Quality: `draft` while iterating; `looks` (default) for review; `delivery` for the final file.
- Brand only from tutorial.yaml `brand:` + `proyectos/<slug>/<brand.dir>/logo.svg|logo.png`. "sin logo" → ask the user for it before the final render.
- Never edit `hf-*/index.html` or `layout.json` by hand: compose regenerates them. Fix the input (tutorial.yaml, timing stages) or `templates/composition.html` only on an explicit design request.

## What compose guarantees (do not re-implement; verify in QA)

| Rules | Guarantee |
| --- | --- |
| C1, R1 | context 1.0× ≤ 1.0 s; detail 1.8–2.5× on every type/click/select/focus/result/highlight event |
| C2 | 400–600 ms ease-in-out pans/zooms, never a cross-fade between framings of the same screen |
| C3 | click target fully in frame ≥ 500 ms before the click |
| C4 | blank frames cut by edit; loads covered |
| C5 | cursor ~48 px in output pixels at any zoom, soft halo on click |
| O1 | step chip 100 % opacity, contrast ≥ 4.5:1, never over logo/menu/header (attached to the caption block or a reserved zone) |
| O2, R2 | captions and cursor never over the active element, a toast or a mentioned field: the framing moves |
| O3 | one caption + chip style in every video of the slug |
| R3 | new element outlined/pulsed in the accent color, contrast ≥ 3:1 |
| T1, T2 | captions ≤ 2 lines × 42 chars, ≥ 1.2 s, no line ending in article/preposition/conjunction, never across steps; font ≥ 44 px at 1080 |
| T3 | `product` never split across lines |
| E3, TUT3 | long TUT: "Parte N · Paso M" chip; PRO/NOV: no step chip (PRO4) |
| V1–V4 | 9:16 is a full-bleed real crop of the 1920x1080 source following the active element (UI ≥ 70 % of height); nothing important in top 15 % / bottom 20 %; title only in the opening ≤ 3 s |
| V5 | duration comes from the RED step subset (edit) |

`hf-<video>/layout.json` (read by qa.py): `output`, `viewport`, `cursor_px`, `font_px`, `camera[{t0,t1,scale,kind}]` and `items[{kind: caption|chip|title|card|cursor|active|result|highlight, t0, t1, rect, text, lines, step}]`, rects in output pixels.

## Execution Steps

1. compose, then `render.py <slug> --quality draft`; or `.venv/Scripts/python.exe tools/pipeline.py <slug> --from compose --quality draft` (`--video <id>` for one video).
2. Run `tutorial-qa`. After it passes: `.venv/Scripts/python.exe tools/pipeline.py <slug> --from compose --quality delivery`.
3. Failures: `No existe hf-<video>/index.html` → run compose; check errors → read the listed lines, fix the input, recompose; duration mismatch → rerun from `edit`.
4. The first HyperFrames run may download fonts/Chrome components; let it finish.

## Output Contract

Per video: output path, type, resolution, duration, quality preset, and hyperframes check warnings.
