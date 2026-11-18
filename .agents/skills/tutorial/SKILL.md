---
name: tutorial
description: "Trigger: hacer un tutorial, crear tutorial, grabar tutorial, video tutorial, tutorial en video, video para redes, reel, promocional, novedad, replicar video, mejorar video, rehacer tutorial, make a tutorial, record tutorial, tutorial video, replicate video, video de uso, código fuente, enfoque. Entry point: decides the video type (TUT/RED/PRO/NOV) and produces every requested video end to end from one step list (default TUT 16:9 + RED 9:16), always starting from a brief."
license: Apache-2.0
metadata:
  author: tutoriales
  version: "2.1"
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
- Lyria (≈ USD 0.08/track) and TTS (per character) are billed; both cache, so rerunning unchanged text costs nothing. Ask before `music.py --force`. Iterate on `qa.py --pre`, never on renders.
- Long commands (capture, pipeline, render, anything that may exceed ~1 min): never under a short shell timeout. Use the harness background runner (`bash_background`) or an explicit timeout ≥ 900 s; then check the exit code and the log tail. Never assume a silent command is still running.
- Music prompts describe mood, instruments and tempo only; never genres tied to commercial music (pop, reggaeton, rock…) or artists (Lyria blocks them as "recitation"; music.py retries once with a neutral prompt and logs it).

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
3. `tutorial-brief`: inputs, Tipo de video per output, Dispositivo, Glosario, Paleta (N5), Historia (N4), Destino del CTA (N8), Datos de la serie; verifies the login.
4. Mode B only: `tutorial-replicar`.
5. `tutorial-guion` → `.venv/Scripts/python.exe tools/lint.py <slug>`. Fix every error and warning until lint passes; never record with lint errors.
6. `tutorial-ensayo-captura` (rehearsal + one take for all videos).
7. FAST WORKFLOW (target ≤ 12 min for a ~1 min TUT + ~20 s RED; report the stage timings pipeline prints):
   1. `.venv/Scripts/python.exe tools/pipeline.py <slug> --from tts --to compose` (tts → edit → music → mix → compose; tts/music reuse caches, so only changed text or prompts cost time/money).
   2. `.venv/Scripts/python.exe tools/qa.py <slug> --pre` (no MP4: timeline.json + layout.json checks) and open EVERY snapshot it prints (`tutorial-qa`). Fix loop happens HERE: change tutorial.yaml, rerun from the stage `tutorial-qa` names (`--to compose`), `qa.py --pre` again. Max 3 rounds; never render inside the loop.
   3. ONE render at final quality: `.venv/Scripts/python.exe tools/pipeline.py <slug> --only render --quality delivery` (all videos render in parallel).
   4. `.venv/Scripts/python.exe tools/qa.py <slug>` (MP4 checks: A1, C4 pixels, duration, resolution).
   5. Only a failing video is fixed and re-rendered: `... --only render --quality delivery --video <id>` (or `--from <stage> --video <id>`), then `qa.py <slug> --video <id>`.
   - Recapture only when the take itself is wrong (selector, missing `wait:`/`result:`/`highlight:`, private data, wrong screen). Voice and music rerun only when their text/prompt changed.

## Output Contract

Per video id: `proyectos/<slug>/out/<slug>-<id>.mp4`, type, format, duration (from render/qa), steps included, QA status (`qa.py --pre` + MP4 `qa/<id>.json` result + visual verdict), and rules still failing. Stage timings (total vs the ≤ 12 min target) and renders used (1 + per-video re-renders). Then voice + music per video, fix rounds used, and a cost note (Lyria ≈ USD 0.08 per track, TTS per narrated character; offline runs cost nothing). List pending items (offline silent voice or placeholder music still in use).
