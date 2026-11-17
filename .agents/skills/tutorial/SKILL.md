---
name: tutorial
description: "Trigger: hacer un tutorial, crear tutorial, grabar tutorial, video tutorial, tutorial en video, replicar video, mejorar video, rehacer tutorial, make a tutorial, record tutorial, tutorial video, replicate video, video de uso, código fuente, enfoque. Entry point: produces a tutorial video end to end (16:9 full + 9:16 summary) from a live app, demo credentials, a usage video, a running project's source or an existing video (mode B), always starting from a brief."
license: Apache-2.0
metadata:
  author: tutoriales
  version: "1.0"
---

## Activation Contract

Use when the user asks for a tutorial video of a web app or browser extension, or to replicate/improve an existing tutorial video. This skill orchestrates; stage skills do the work.

## Hard Rules

- Run everything from the repo root with `.venv/Scripts/python.exe tools/<stage>.py ...`.
- Every tutorial starts with `tutorial-brief` → `proyectos/<slug>/brief.md`; no tutorial.yaml before it.
- Credentials: demo accounts only. Sent by chat → `proyectos/<slug>/acceso.local.yaml` (gitignored, flat `NAME: value`, overrides `.env`); tutorial.yaml references `env:NAME`. Confirm by name only; never put values in the brief, tutorial.yaml, commits, memory, subagent prompts, logs or summaries. Never write `.env` (the harness blocks it).
- A running project is only accessed: never install, build, run, migrate or seed it; read its source read-only.
- Demo accounts and demo data only. Never record real customer data or personal tabs.
- Brand is per tutorial: logo and colors go in `proyectos/<slug>/brand/` + `brand:` in tutorial.yaml, never global.
- Lyria is billed (≈ USD 0.08/track) and TTS is billed per character: iterate with `--offline` / `--quality draft` and ask before regenerating music with `--force`.

## Decision Gates

| Input | Mode | Next skill |
| --- | --- | --- |
| App URL (+ credentials by chat) + flow | A | `tutorial-brief` → `tutorial-guion` |
| Usage video + instructions (reference only) | A | `tutorial-brief` (`transcribe.py --ref`) → `tutorial-guion` |
| Project path, "ya está levantado" | A | `tutorial-brief` (source read-only) → `tutorial-guion` |
| "Replicar/mejorar este video" | B | `tutorial-brief` → `tutorial-replicar` → continue as A |
| Missing URL, access, objective or brand | — | Ask one consolidated question first |

## Execution Steps

1. Preflight: `.venv/Scripts/python.exe tools/doctor.py` (add `--online` once GEMINI_API_KEY exists). Fix or report every failure before continuing.
2. Pick a kebab-case slug; create `proyectos/<slug>/` and `proyectos/<slug>/brand/` (copy the logo there). Use `proyectos/_demo/tutorial.yaml` as the reference shape.
3. Run `tutorial-brief` for every input: app URL, demo credentials, usage videos, instructions, project source, focus, target length (16:9 full; 9:16 summary ≤ 60-70 s). It verifies the login. Also gather brand assets (logo.png|logo.svg, primary/accent/background/text colors, font).
4. Mode B only: run `tutorial-replicar`.
5. Run in order: `tutorial-guion` → `tutorial-ensayo-captura` → `tutorial-voz` → `tutorial-edicion` → `tutorial-render` → `tutorial-qa`.
   After the take works, the rest can run in one go: `.venv/Scripts/python.exe tools/pipeline.py <slug> --from tts --quality draft`. Run it again with `--quality delivery` (from `compose`) for the final render.
6. Loop `tutorial-qa` fixes until every snapshot passes.

## Output Contract

Deliver a summary with: `proyectos/<slug>/out/<slug>-16x9.mp4` and `<slug>-9x16.mp4` with their durations (from qa.py/render.py output), voice + music used, QA status, and a cost note (Lyria ≈ USD 0.08 per track generated, TTS billed per narrated character; offline runs cost nothing). List any pending items (e.g. offline placeholder music still in use).
