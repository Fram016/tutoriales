---
name: tutorial-guion
description: "Trigger: guion, guión del tutorial, escribir guion, narración, tutorial.yaml, pasos del tutorial, script tutorial, write script, narration, storyboard. Turns a natural-language flow into proyectos/<slug>/tutorial.yaml with Latin American Spanish commercial narration and 9:16 summary steps."
license: Apache-2.0
metadata:
  author: tutoriales
  version: "1.0"
---

## Activation Contract

Use when writing or revising `proyectos/<slug>/tutorial.yaml` from the user's flow description (mode A) or a reconstructed transcript (mode B).

## Hard Rules

- Follow the schema of `proyectos/_demo/tutorial.yaml` exactly: `title, subtitle, app_url, viewport [1920,1080], language: es, brand {dir: brand, primary, accent, background, text, font}, intro {seconds}, outro {text, seconds}, voice {model, voice, style}` (optional), `music {prompt, model}` (optional), `steps[]`.
- Step: `id` (short kebab, unique), `title?`, `narration`, `summary?: true`, `hold_ms?`, `actions[]`. Each action is a one-key map: `goto: URL` | `click: SEL` | `hover: SEL` | `type: {into: SEL, text: "literal" | "env:NAME", clear?: true}` | `select: {in: SEL, option: "Label"}` | `press: Enter` | `scroll: 600` | `wait: SEL` | `pause: 800`.
- Selectors: raw CSS (`#id`, `[name=email]`), `text=Visible text` (`text="Exact"` is exact), `xpath=...`. No ego `@refs`, no `loc=`.
- Secrets only as `env:NAME` (also allowed in `app_url`/`goto`). Typed data must be fictitious demo data (María González, maria@empresa.com).
- End each step that changes the page with `wait: SEL` for the result, so the take never races the app.

## Narration style (Latin American Spanish, commercial voice)

- One idea per step; 1-2 short sentences; ~2.6 words/s, so a 13-word line ≈ 5 s.
- Second person plural, present tense: "Ingresamos…", "Tocamos el botón Guardar…", "Completamos…".
- Name what is on screen with its visible label; no jargon, no "haga clic aquí".
- Neutral Latin American Spanish (no voseo, no Spain-only terms). Write numbers as they should be spoken.
- The intro title carries the hook; the outro text closes with the result in neutral Spanish ("¡Listo! Ya puedes crear clientes en…").
- Clip timing is per step: edit.py sizes each cut to its narration, so a long line on a fast action holds the last frame.

## Execution Steps

1. Split the flow into steps: one visible outcome per step.
2. Mark `summary: true` on the essential steps for the 9:16 cut. Budget: sum of their words / 2.6 + intro + outro ≤ 60-70 s. With no summary steps the short cut uses every step.
3. Estimate the full length the same way and compare with the user's target; trim narration, not steps.
4. Write selectors as best guesses, flagged for confirmation in `tutorial-ensayo-captura`.

## Output Contract

Report: path of tutorial.yaml, step count, estimated full and summary durations, which `env:NAME` variables the user must add to `.env`, and selectors still unverified.
