---
name: tutorial
description: "Trigger: hacer un tutorial, crear tutorial, grabar tutorial, video tutorial, tutorial en video, replicar video, mejorar video, rehacer tutorial, make a tutorial, record tutorial, tutorial video, replicate video. Entry point: produces a tutorial video end to end (16:9 full + 9:16 summary) from an app + flow (mode A) or an existing video (mode B)."
license: Apache-2.0
metadata:
  author: tutoriales
  version: "1.0"
---

## Activation Contract

Use when the user asks for a tutorial video of a web app or browser extension, or to replicate/improve an existing tutorial video. This skill orchestrates; stage skills do the work.

## Hard Rules

- Run everything from the repo root with `.venv/Scripts/python.exe tools/<stage>.py ...`.
- Never write `.env` yourself (the harness blocks it). Tell the user which `NAME=value` lines to add; reference them in tutorial.yaml as `env:NAME`.
- Demo accounts and demo data only. Never record real customer data or personal tabs.
- Brand is per tutorial: logo and colors go in `proyectos/<slug>/brand/` + `brand:` in tutorial.yaml, never global.
- Lyria is billed (≈ USD 0.08/track) and TTS is billed per character: iterate with `--offline` / `--quality draft` and ask before regenerating music with `--force`.

## Decision Gates

| Input | Mode | Next skill |
| --- | --- | --- |
| App URL + flow description | A | `tutorial-guion` |
| Existing video file | B | `tutorial-replicar`, then continue as A |
| Missing URL, credentials, flow or brand | — | Ask one consolidated question first |

## Execution Steps

1. Preflight: `.venv/Scripts/python.exe tools/doctor.py` (add `--online` once GEMINI_API_KEY exists). Fix or report every failure before continuing.
2. Gather: app URL; demo credentials (ask the user to add them to `.env`, e.g. `CRM_DEMO_USER=`); brand assets (logo.png|logo.svg, primary/accent/background/text colors, font); flow in natural language; target length (16:9 full; 9:16 summary ≤ 60-70 s).
3. Pick a kebab-case slug; create `proyectos/<slug>/` and `proyectos/<slug>/brand/` (copy the logo there). Use `proyectos/_demo/tutorial.yaml` as the reference shape.
4. Mode B only: run `tutorial-replicar`.
5. Run in order: `tutorial-guion` → `tutorial-ensayo-captura` → `tutorial-voz` → `tutorial-edicion` → `tutorial-render` → `tutorial-qa`.
   After the take works, the rest can run in one go: `.venv/Scripts/python.exe tools/pipeline.py <slug> --from tts --quality draft`. Run it again with `--quality delivery` (from `compose`) for the final render.
6. Loop `tutorial-qa` fixes until every snapshot passes.

## Output Contract

Deliver a summary with: `proyectos/<slug>/out/<slug>-16x9.mp4` and `<slug>-9x16.mp4` with their durations (from qa.py/render.py output), voice + music used, QA status, and a cost note (Lyria ≈ USD 0.08 per track generated, TTS billed per narrated character; offline runs cost nothing). List any pending items (e.g. offline placeholder music still in use).
