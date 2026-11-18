---
name: tutorial-guion
description: "Trigger: guion, guión del tutorial, escribir guion, narración, tutorial.yaml, pasos del tutorial, apertura, cierre, gancho, script tutorial, write script, narration, storyboard. Turns proyectos/<slug>/brief.md into proyectos/<slug>/tutorial.yaml v2: one step list, one entry per video (TUT/RED/PRO/NOV) with its opening, closing and narration, in español neutro de Ecuador (tú)."
license: Apache-2.0
metadata:
  author: tutoriales
  version: "2.0"
---

## Activation Contract

Use when writing or revising `proyectos/<slug>/tutorial.yaml` from `brief.md` (mode A) or a reconstructed transcript (mode B). Read brief.md whole first; if missing, run `tutorial-brief`. Rules by ID: `reglas/reglas-video.md`. Complete example (TUT + RED from one list): `assets/ejemplo-tut-red.yaml`; smoke example: `proyectos/_demo/tutorial.yaml`. Then run `.venv/Scripts/python.exe tools/lint.py <slug>` and fix everything it reports.

## Schema v2 (no `intro`, `outro`, `summary`)

- Top: `title`, `product` (T3, exact brand name, never split), `app_url`, `viewport: [1920, 1080]`, `language: es-EC`, `device: desktop|mobile` (L2), `brand {dir, primary, accent, background, text, font}`, `glossary {term: [forbidden synonyms]}` (L3, from the brief), `music {prompt}` (optional default), `voice {voice, style}` (optional), `steps[]`, `videos[]`.
- Step: `id` (unique kebab), `title?`, `chapter?`, `narration` (TUT default), `hold_ms?`, `actions[]` of one-key maps: `goto: URL` | `click: SEL` | `hover: SEL` | `press: KEY` | `scroll: PX` | `wait: SEL` | `pause: MS` | `type: {into, text: "literal"|"env:NAME", clear?}` | `select: {in, option}` | `focus: SEL` | `result: SEL` | `highlight: SEL`.
- Video: `id` (→ `out/<slug>-<id>.mp4`), `type: TUT|RED|PRO|NOV`, `format: "16:9"|"9:16"`, `steps: all | [ids]` (order kept, numbering = original index + 1), `opening {narration, text}` and `closing {narration, text}` (both required, E1), `requirements {narration, text}` (TUT only, ≤ 5 s), `narration {step_id: text}` overrides, `music {prompt}` or `{none: true}`.
- Selectors: raw CSS, `text=Label`, `xpath=...`. No ego `@refs`, no `loc=`. Credentials only as `env:NAME`. Typed data from Datos de la serie (TUT7), fictitious.

## Steps (E2)

- One step = one action with a visible result. Never split one action: filling a form is ONE step ("Completa los datos": every `type`/`select` of that form), not one step per field.
- End each page-changing step with `wait: SEL`. Every confirmation toast → `result: SEL` after its `wait`; every new row/card/menu item → `highlight: SEL` (e.g. `#rows tr:first-child`). Use `focus: SEL` when the narration reads something without clicking (C1 detail).
- Every element the narration mentions needs a selector in some action: the camera only frames logged boxes.
- C6: keep typed demo values short; notes > 30 chars are retimed (×3 after 15 chars) — prefer short notes.
- TUT5: include login only in the first video of the series; RED/PRO/NOV omit login, obvious navigation and optional fields (RED3, V5) by leaving those steps out of `videos[].steps`.
- Long TUT (> ~5 min, E3/TUT3): set `chapter: N` per step; the first step of each chapter > 1 opens with a mini summary ("Hasta aquí ya tienes…") every 2–3 min.

## Structure per type

| Type | Structure | Opening example | Closing example | Duration |
| --- | --- | --- | --- | --- |
| TUT (TUT1, TUT6) | objetivo → requisitos? → pasos → resultado en detalle → siguiente video | "En este video aprendes a crear contactos." | "Siguiente video: registrar una oportunidad." | free |
| RED (RED1, RED4) | gancho 1–2 s → 3–4 acciones → resultado → CTA 2 s | "¿Un contacto nuevo de la feria?" | "Mira el tutorial completo." | 15–35 s |
| PRO (PRO1, PRO3) | problema → solución → beneficio visible → CTA; ≤ 2 interacciones seguidas | "¿Pierdes contactos en tus hojas?" | "Pruébalo gratis en nexocrm.demo." | 20–60 s |
| NOV (NOV1, NOV3) | qué cambió → dónde está → para qué sirve; un cambio | "Nuevo: filtra contactos por etapa." | "Tutorial completo en el enlace." | 15–30 s |

- Never open or close with only the title or "¡Listo!" (E1). TUT informs, does not sell (TUT6).
- RED/PRO/NOV write their own `narration` overrides: shorter, punchier, understandable without sound (RED4: `text` carries the message).
- Budget ≈ 2.6 words/s (lint estimates with it). Opening ≤ 3 s (≤ 7 words; RED hook 1–2 s, ≤ 5 words). Closing ≤ 2.5 s (≤ 6 words, A2). RED needs ≥ 15 s: 3–4 steps of ~10 words each.
- A2: no silence > 1 s — each step's narration must cover its action span (a form-filling step needs a sentence long enough for the typing); one idea, 1–2 short sentences.
- T3: write `product` exactly; keep `title`/`text` short enough that the product name fits on one line.

## Language (L1–L4)

- Español neutro de Ecuador, trato de tú, present tense, imperative or "tú" second person. Name on-screen labels exactly; use only glossary terms.

| Forbidden | Use |
| --- | --- |
| voseo: "ingresá", "completá", "hacé", "tocá", "tenés", "podés", "sabés", "vos" | "ingresa", "completa", "haz", "toca", "tienes", "puedes", "sabes", "tú" |
| plural/usted: "ingresamos", "tocamos", "haga clic" | "ingresa", "haz clic" |
| desktop: "toca", "tocamos", "pulsa", "pincha" | "haz clic" |
| mobile: "haz clic" | "toca" |
| "acá", "allá" | "aquí", "ahí" |
| "cargar" (datos), "rellenar", "ordenador" | "registrar", "completar", "computadora" |
| glossary synonyms (e.g. "cliente" when the term is "contacto") | the glossary term |

## Execution Steps

1. Build `steps` from the brief's Flujo propuesto (E2), with result/highlight/focus actions.
2. Write one `videos[]` entry per row of the brief's Tipo de video; default `tutorial` TUT 16:9 `steps: all` + `redes` RED 9:16 without login/navigation/optional steps.
3. Write openings/closings per type and narration overrides; estimate each video's length against its target.
4. Run lint; fix every error and warning. Mark guessed selectors for `tutorial-ensayo-captura`.

## Output Contract

Report: tutorial.yaml path, step count, per video (id, type, format, steps, estimated duration), lint result, `env:NAME` names used (exists in `acceso.local.yaml`/`.env`, names only), selectors still unverified.
