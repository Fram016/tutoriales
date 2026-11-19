---
name: tutorial-render
description: "Trigger: render, renderizar, exportar video, armar video, subtítulos, zoom, cámara, cursor, logo, marca, colores, vertical, reels, tiktok, 9:16, 16:9, compose, captions, branding, export, layout. Builds one HyperFrames composition per video (compose.py: camera, cursor, caption band, brand palette, real 9:16 reframe, layout.json) and renders every out/<slug>-<video>.mp4 in parallel, once, at final quality (render.py)."
license: Apache-2.0
metadata:
  author: tutoriales
  version: "2.2"
---

## Activation Contract

Use after mix. For every entry in `videos:`, compose builds `proyectos/<slug>/hf-<video>/` (+ `layout.json`); render writes `out/<slug>-<video>.mp4` only after `tutorial-qa` PRE passes. Rules by ID: `reglas/reglas-video.md`.

## Hard Rules

- `.venv/Scripts/python.exe tools/compose.py <slug>` — builds every video and runs `hyperframes check`; any error fails the stage, warnings are counted.
- `.venv/Scripts/python.exe tools/render.py <slug> [--quality draft|looks|delivery] [--video <id>]` → `out/<slug>-<id>.mp4`, always with `--page-motion-blur off` (C2 ghosting). All requested videos render in parallel (one process per video, workers split across cores). It verifies resolution, duration ≈ timeline total (±0.3 s) and an audio track.
- Render ONCE, at `delivery`, after `qa.py <slug> --pre` and the snapshots pass: `.venv/Scripts/python.exe tools/pipeline.py <slug> --only render --quality delivery`. Never render to iterate. A video failing the MP4 checks re-renders alone with `--video <id>`.
- Render and compose take minutes: run them with the harness background runner (`bash_background`) or a timeout ≥ 900 s, never a short shell timeout; check the exit code and the log tail.
- Brand only from tutorial.yaml `brand:` + `proyectos/<slug>/<brand.dir>/logo.svg|logo.png`. "sin logo" → ask the user for it before the final render. N24: on a dark card the logo must read (light variant, contrast ≥ 3:1); check the opening snapshot.
- Never edit `hf-*/index.html` or `layout.json` by hand: compose regenerates them. Fix the input (tutorial.yaml, timing stages) or `templates/composition.html` only on an explicit design request.

## What compose guarantees (do not re-implement; verify in QA)

| Rules | Guarantee |
| --- | --- |
| C1, R1 | context 1.0× ≤ 1.0 s; detail 1.4–1.8× on every click/focus/result/highlight event outside a form |
| N20 | no pillarbox/black borders around the page; UI text ≥ 16 px in the output; zoom in a stable range, no abrupt jumps |
| N10 | type/select inside a form container (`form_box`): ONE form shot fitted to the whole form (1.1–1.5×, ≤ 1.8×), camera still while its fields are filled; a form too tall to read is split into the fewest shots, top to bottom |
| N11 | inside a form shot the active field gets a brand-primary outline + spotlight (rest dimmed ≤ 25 %), moving 250–400 ms between fields; that move counts as a change for C8 |
| N12 | in 9:16 the whole form width is framed; no field or label cut at the edges (V2, neighbors included) |
| C7 | each new screen opens with an establishing full-screen shot (≤ 1.0 s), then an interpolated zoom to the first element |
| C8 | no identical framing > 4 s (TUT) / 3 s (RED); in a form shot the spotlight move is the change (N11), never per-field camera moves |
| C9 | a field's framing uses its `frame_box` (control + visible label); nothing of the active control is cut |
| C10 | a screen change is a hard cut to the new framing or straight to the result/toast (no pan over empty areas, no click on nothing, no near-empty frames, C4) |
| C2 | 400–600 ms ease-in-out pans/zooms, never a cross-fade between framings of the same screen |
| C3 | click target fully in frame ≥ 500 ms before the click |
| C4 | blank frames cut by edit; loads covered |
| C5 | cursor ~48 px in output pixels at any zoom, soft halo on click |
| O1, N2, N7 | step chip only "Paso N" (TUT; "Parte N · Paso M" with parts), 100 % opacity, contrast ≥ 4.5:1, never over logo/menu/header; no chip in RED/PRO/NOV |
| N16 | with `parts`: a "Parte N: título" separator card before each part |
| N17 | context badge "En el SRI" / "En Perseo XML" per step; brand primary only for the product and highlights, page context in a neutral color |
| N3, N21 | captions in a fixed band outside the UI (bottom in 16:9, dedicated band in 9:16); band ≤ 1/8 of the height (≤ 135 px at 1080) |
| N22 | an extension surface (popup) is always fully inside the frame |
| N23 | promos listed in `surfaces.<name>.hide` never appear (hidden by the recorder) |
| N24 | logo light variant on dark cards, contrast ≥ 3:1 |
| N26 | no blank screens or two pages mixed in one frame (edit cuts loads and transitions) |
| N27 | TUT without `closing` ends on the final result, no closing card |
| N5 | chip, lines, highlight and band from `brand` (accent = primary; band = `surface`, text = `on_surface`); no pure black boxes |
| N6, R2 | the confirmation toast is always framed ≥ 800 ms clean at 1.0× speed, exempt from C4 |
| O2 | captions and cursor never over the active element, a toast or a mentioned field: the framing moves |
| O3 | one caption + chip style in every video of the slug |
| R3 | new element outlined/pulsed in the brand color, contrast ≥ 3:1 |
| T1, T2, N19 | one caption = one sentence (items carry `sentence`), ≤ 2 lines × 42 chars, ≥ 1.2 s, never split across blocks or steps, no line ending in article/preposition/conjunction; font ≥ 44 px at 1080 |
| T3 | `product` never split across lines |
| N9, V1–V4 | 9:16 is one stable composition (never alternating full screen and bands), a real crop of the 1920x1080 source following the active element (UI ≥ 70 % of height); nothing important in top 15 % / bottom 20 %; title only in the opening ≤ 3 s |
| V5 | duration comes from the RED step subset (edit) |

`pace: fast` (timeline `pace`, P3): detail 1.15–1.4× (C1/R1 in qa too), forms whole at 1.0–1.2× (a form wider than the viewport is fitted to the width at 1.0× and cropped beyond the used fields), the popup at the scale that keeps it whole, no framing frozen > 2.5 s (C8), part separators of 0.8 s, and the whole-form shot is the establishing shot of its screen (hard cut to it). Still no pillarbox (N20). layout.json then records `pace` and `legible_scale` (1.0). Known limit: C4 (≤ 70 % empty) flags sparse real pages at this zoom (SRI forms and link pages, the Chrome settings page: 71–77 %).

`hf-<video>/layout.json` (read by qa.py): `output`, `viewport`, `cursor_px`, `font_px`, `camera[{t0,t1,scale,kind,reason?,form_box?}]` (establishing shots: kind `context`, reason `establishing`; form shots: kind `form` + `form_box`) and `items[{kind: caption|band|chip|title|card|cursor|active|result|highlight|spotlight, t0, t1, rect, text, lines, step, color, dim?}]`, rects in output pixels (`spotlight.rect` = active field frame_box); caption items carry `sentence`; part separators and the context badge are items too.

## Execution Steps

1. compose (`.venv/Scripts/python.exe tools/pipeline.py <slug> --only compose`), then `tutorial-qa` PRE (`qa.py <slug> --pre` + snapshots, ≤ 3 rounds).
2. One render: `.venv/Scripts/python.exe tools/pipeline.py <slug> --only render --quality delivery`, then `qa.py <slug>`; a failing video only: `--only render --quality delivery --video <id>`.
3. Failures: `No existe hf-<video>/index.html` → run compose; check errors → read the listed lines, fix the input, recompose; duration mismatch → rerun from `edit`.
4. The first HyperFrames run may download fonts/Chrome components; let it finish.

## Output Contract

Per video: output path, type, resolution, duration, quality preset, and hyperframes check warnings.
