---
name: tutorial
description: "Trigger: hacer un tutorial, crear tutorial, grabar tutorial, video tutorial, tutorial en video, video para redes, reel, promocional, novedad, replicar video, mejorar video, rehacer tutorial, make a tutorial, record tutorial, tutorial video, replicate video, video de uso, código fuente, enfoque. Entry point: decides the video type (TUT/RED/PRO/NOV) and produces every requested video end to end from one step list (default TUT 16:9 + RED 9:16), always starting from a brief."
license: Apache-2.0
metadata:
  author: tutoriales
  version: "2.0"
---

## Activation Contract

Use when the user asks for a tutorial, social, promo or feature-announcement video of a web app or browser extension, or to replicate/improve an existing one. This skill orchestrates; stage skills do the work. Normative rules: `reglas/reglas-video.md` (cite rule IDs; never restate them).

## Hard Rules

- Run everything from the repo root with `.venv/Scripts/python.exe tools/<stage>.py ...`.
- Every video starts with `tutorial-brief` → `proyectos/<slug>/brief.md`; no tutorial.yaml before it.
- Decide the video type before the script (Parte 3): every entry in `videos:` declares `type` and `format`.
- One take, one step list (E2): all videos of a slug come from the same `steps:`; each video picks `steps: all` or a subset.
- Credentials: demo accounts only. Sent by chat → `proyectos/<slug>/acceso.local.yaml` (gitignored, flat `NAME: value`, overrides `.env`); tutorial.yaml references `env:NAME`. Confirm by name only; never put values in the brief, tutorial.yaml, commits, memory, subagent prompts, logs or summaries. Never write `.env`.
- A running project is only accessed: never install, build, run, migrate or seed it; read its source read-only.
- Demo data only. Never record real customer data or personal tabs.
- Brand is per tutorial: `proyectos/<slug>/brand/` + `brand:` in tutorial.yaml, never global.
- Lyria (≈ USD 0.08/track) and TTS (per character) are billed: iterate with `--offline` / `--quality draft`; ask before `music.py --force`.

## Decide the video type (mandatory)

| Request | videos: |
| --- | --- |
| "Haz un tutorial" (default) | `tutorial` TUT 16:9 `steps: all` + `redes` RED 9:16 subset (no login, no obvious navigation, no optional fields) |
| Only how-to / only horizontal | TUT 16:9 |
| Reel, TikTok, Stories, "para redes" | RED 9:16 (15–35 s) |
| Sell the product or a feature | PRO, format of the channel (20–60 s) |
| Tell current users about a change | NOV, 16:9 or 9:16 (15–30 s, one change) |

- The vertical is always RED, never a cropped TUT (S3, V1). The horizontal is TUT.
- Type sets opening, closing, pace, step chip, login and music (Tabla de decisión). If the user gave no type, apply the default and state it in the brief as proposed.

## Decision Gates

| Input | Mode | Next skill |
| --- | --- | --- |
| App URL (+ credentials by chat) + flow | A | `tutorial-brief` → `tutorial-guion` |
| Usage video + instructions (reference only) | A | `tutorial-brief` (`transcribe.py --ref`) → `tutorial-guion` |
| Project path, "ya está levantado" | A | `tutorial-brief` (source read-only) → `tutorial-guion` |
| "Replicar/mejorar este video" | B | `tutorial-brief` → `tutorial-replicar` → continue as A |
| Missing URL, access, objective or brand | — | Ask one consolidated question first |

## Execution Steps

1. Preflight: `.venv/Scripts/python.exe tools/doctor.py` (add `--online` once GEMINI_API_KEY exists). Fix or report every failure.
2. Pick a kebab-case slug; create `proyectos/<slug>/brand/` (copy the logo). Reference shape: `proyectos/_demo/tutorial.yaml`.
3. `tutorial-brief`: inputs, Tipo de video per output, Dispositivo, Glosario, Datos de la serie; verifies the login.
4. Mode B only: `tutorial-replicar`.
5. `tutorial-guion` → `.venv/Scripts/python.exe tools/lint.py <slug>`. Fix every error and warning in tutorial.yaml until lint passes; never record with lint errors.
6. `tutorial-ensayo-captura` (one take for all videos) → `tutorial-voz` → `tutorial-edicion` → `tutorial-render` → `tutorial-qa`.
   After the take works: `.venv/Scripts/python.exe tools/pipeline.py <slug> --from tts --quality draft` (stages: lint, capture, tts, edit, music, mix, compose, render; `--video ID` limits to one video).
7. `tutorial-qa`: automatic checks + visual review per video. Fix and rerun from the stage it names; at most 3 fix rounds, then stop and report the remaining failures.
8. Final: `.venv/Scripts/python.exe tools/pipeline.py <slug> --from compose --quality delivery`, then qa again.

## Output Contract

Per video id: `proyectos/<slug>/out/<slug>-<id>.mp4`, type, format, duration (from render/qa), steps included, QA status (`qa/<id>.json` result + visual verdict), and rules still failing. Then voice + music per video, fix rounds used, and a cost note (Lyria ≈ USD 0.08 per track, TTS per narrated character; offline runs cost nothing). List pending items (offline silent voice or placeholder music still in use).
