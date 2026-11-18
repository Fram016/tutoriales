---
name: tutorial-guion
description: "Trigger: guion, guión del tutorial, escribir guion, narración, tutorial.yaml, pasos del tutorial, apertura, cierre, gancho, script tutorial, write script, narration, storyboard. Turns proyectos/<slug>/brief.md into proyectos/<slug>/tutorial.yaml v2: one step list, one entry per video (TUT/RED/PRO/NOV) with its opening, closing and narration, in español neutro de Ecuador (tú)."
license: Apache-2.0
metadata:
  author: tutoriales
  version: "2.1"
---

## Activation Contract

Use when writing or revising `proyectos/<slug>/tutorial.yaml` from `brief.md` (mode A) or a reconstructed transcript (mode B). Read brief.md whole first; if missing, run `tutorial-brief`. Rules by ID: `reglas/reglas-video.md`. Examples: `assets/ejemplo-tut-red.yaml` (TUT + RED), `proyectos/_demo/tutorial.yaml` (smoke).

## Schema v2 (no `intro`, `outro`, `summary`)

- Top: `title`, `product` (T3, exact brand name, never split), `app_url`, `viewport: [1920, 1080]`, `language: es-EC`, `device: desktop|mobile` (L2), `brand {dir, primary, background, surface?, on_surface?, text, font}` (N5: palette from the brief; accent defaults to primary, never add another color), `glossary {term: [forbidden synonyms]}` (L3, from the brief), `music {prompt}` (optional default; mood + instruments + tempo only, never genres like pop/reggaeton/rock or artists: Lyria blocks them as "recitation"), `voice {voice, style}` (optional), `steps[]`, `videos[]`.
- Step: `id` (unique kebab), `title?` (brief/worklog only, not rendered, N2), `chapter?`, `narration` (TUT default), `hold_ms?`, `actions[]` of one-key maps: `goto: URL` | `click: SEL` | `hover: SEL` | `press: KEY` | `scroll: PX` | `wait: SEL` | `pause: MS` | `type: {into, text: "literal"|"env:NAME", clear?}` | `select: {in, option}` | `focus: SEL` | `result: SEL` | `highlight: SEL`.
- Video: `id` (→ `out/<slug>-<id>.mp4`), `type: TUT|RED|PRO|NOV`, `format: "16:9"|"9:16"`, `steps: all | [ids]` (order kept, numbering = original index + 1), `opening {narration, text?}` and `closing {narration, text}` (both required, E1; TUT opening card already shows `title`, so `text` is omitted or adds a different idea, N2), `requirements {narration, text}` (TUT only, ≤ 5 s), `narration {step_id: text}` overrides, `omit: [SELECTOR, ...]` (typing/select on those selectors is cut from this video; the step stays), `music {prompt}` or `{none: true}`.
- Selectors: raw CSS, `text=Label`, `xpath=...`. No ego `@refs`, no `loc=`. Credentials only as `env:NAME`. Typed data from Datos de la serie (TUT7), fictitious.

## Steps (E2)

- One step = one action with a visible result. Filling a form is ONE step ("Completa los datos": every `type`/`select` of that form, top to bottom), never one step per field.
- N10–N12: a form step becomes one still form shot with a spotlight moving field to field; do not add `focus:` per field (it would move the camera).
- End each page-changing step with `wait: SEL`. Every toast → `result: SEL` after its `wait`; every new row/card/menu item → `highlight: SEL`. `focus: SEL` when the narration reads something without clicking.
- Every element the narration mentions needs a selector in some action: the camera only frames logged boxes.
- C6, N4: short typed values (notes > 30 chars are retimed) that carry the brief's Historia (e.g. Origen "Feria"); the narration explains each chosen value.
- TUT5: login only in the first video of the series. RED/PRO/NOV leave login and obvious navigation out of `videos[].steps`; optional fields of a kept step go to `videos[].omit` (RED3, V5).
- Long TUT (> ~5 min, E3/TUT3): `chapter: N` per step; each chapter > 1 opens with a mini summary ("Hasta aquí ya tienes…").

## Structure per type

| Type | Structure | Opening example | Closing example | Duration |
| --- | --- | --- | --- | --- |
| TUT (TUT1, TUT6) | objetivo → requisitos? → pasos → resultado en detalle → siguiente video | "Aprendes a crear contactos." | "Siguiente: registrar oportunidades." | free |
| RED (RED1, RED4, N7, N8) | gancho 1–2 s → 3–4 acciones → resultado → CTA con destino 2 s; sin "Paso N" | "¿Contacto de feria?" | "Mira nuestro perfil." (N8) | 15–35 s |
| PRO (PRO1, PRO3, N8) | problema → solución → beneficio visible → CTA con destino; ≤ 2 interacciones seguidas | "¿Pierdes contactos?" | "Pruébalo en nexocrm.demo." | 20–60 s |
| NOV (NOV1, NOV3) | qué cambió → dónde está → para qué sirve; un cambio | "Nuevo: filtro por etapa." | "Tutorial en el enlace." | 15–30 s |

- Never open or close with only the title or "¡Listo!" (E1). TUT informs, does not sell (TUT6). RED/PRO/NOV write their own shorter `narration` overrides, understandable without sound (RED4).
- Voice budget (lint): words ≤ (seconds − 0.5) × 1.9 per clip:

| Clip | Max | Words |
| --- | --- | --- |
| TUT opening (E1) | 3 s | ≤ 4 |
| RED hook (RED1) | 2 s | ≤ 2 |
| Closing (A2) | 2.5 s | ≤ 3 (the card `text` carries the rest) |
| Requirements (TUT1) | 5 s | ≤ 8 |
| RED step (RED3, C8) | ~4.5 s | ≤ 7 |

  RED ≥ 15 s: 3–4 steps of 6–7 words. A2: no silence > 1 s; a form step's sentence covers its typing.

## Narration rules (Parte 4)

- N1: the instruction comes first and short, one per step ("Haz clic en Guardar contacto."), the result sentence after; never after its result.
- N2: never narrate the step `title` literally; opening narration and card never repeat the same idea or paraphrase `title`.
- N4: hook, data and narration tell one story ("Origen Feria, porque lo conociste ahí").
- N7: RED/PRO/NOV narration never says "paso 3" or step numbers.
- N8: RED/PRO closing names the brief's destination ("Mira nuestro perfil." + text "Tutorial completo en el enlace de nuestro perfil").
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
3. Write openings/closings per type (N2, N8), narration overrides (N1, N4) and `omit` for RED; estimate each video's length with the budget above.
4. Run lint; fix every error and warning. Mark guessed selectors for `tutorial-ensayo-captura`.

## Output Contract

Report: tutorial.yaml path, step count, per video (id, type, format, steps, estimated duration), lint result, `env:NAME` names used (exists in `acceso.local.yaml`/`.env`, names only), selectors still unverified.
