---
name: tutorial-guion
description: "Trigger: guion, guión del tutorial, escribir guion, narración, tutorial.yaml, pasos del tutorial, partes, contexto, apertura, cierre, gancho, script tutorial, write script, narration, storyboard. Turns proyectos/<slug>/brief.md into proyectos/<slug>/tutorial.yaml v2: one step list, one entry per video (TUT/RED/PRO/NOV) with its opening, closing and narration, in español neutro de Ecuador (tú)."
license: Apache-2.0
metadata:
  author: tutoriales
  version: "2.2"
---

## Activation Contract

Use when writing or revising `proyectos/<slug>/tutorial.yaml` from `brief.md` (mode A) or a reconstructed transcript (mode B). Read brief.md whole first; if missing, run `tutorial-brief`. Rules by ID: `reglas/reglas-video.md`. Examples: `assets/ejemplo-tut-red.yaml` (TUT + RED), `proyectos/_demo/tutorial.yaml` (smoke).

## Schema v2 (no `intro`, `outro`, `summary`)

- Top: `title`, `product` (T3, exact brand name, never split), `app_url`, `viewport: [1920, 1080]`, `language: es-EC`, `device: desktop|mobile` (L2), `brand {dir, primary, background, surface?, on_surface?, text, font}` (N5: palette from the brief; accent defaults to primary, never add another color), `glossary {term: [forbidden synonyms]}` (L3, from the brief), `music {prompt}` (optional default; mood + instruments + tempo only, never genres like pop/reggaeton/rock or artists: Lyria blocks them as "recitation"), `voice {voice, style}` (optional), `parts: [{n, title}]` (N16), `censor`/`surfaces` (`tutorial-ensayo-captura`), `steps[]`, `videos[]`.
- Step: `id` (unique kebab), `title?` (brief/worklog only, not rendered, N2), `part?: N` (N16; `chapter` is the older long-TUT form), `context?: sri|extension` (N17; default: extension while a surface is open, else the page), `narration` (TUT default), `hold_ms?`, `actions[]` of one-key maps: `goto: URL` | `click: SEL` | `hover: SEL` | `press: KEY` | `scroll: PX` | `wait: SEL` | `pause: MS` | `type: {into, text: "literal"|"env:NAME", clear?}` | `select: {in, option}` | `focus: SEL` | `result: SEL` | `highlight: SEL`; inside a surface: `open: NAME`, `close: NAME`, `{click|focus|wait|result: {in: NAME, sel}}`.
- Video: `id` (→ `out/<slug>-<id>.mp4`), `type: TUT|RED|PRO|NOV`, `format: "16:9"|"9:16"`, `steps: all | [ids]` (order kept, numbering = original index + 1), `opening {narration, text?}` (required, E1; TUT opening card already shows `title`, so `text` is omitted or adds a different idea, N2), `closing {narration, text}` (required for RED/PRO/NOV; TUT: omit unless the user asks for one, N27, the video ends on the final result), `requirements {narration, text}` (TUT only, ≤ 5 s), `narration {step_id: text}` overrides, `omit: [SELECTOR, ...]` (typing/select on those selectors is cut from this video; the step stays), `music {prompt}` or `{none: true}`, `pace: normal|fast` (P2, default normal), `max_seconds: N` (P1 total cap, lint and qa fail over it), `tempo: 1.0–1.25` (voice speed; default 1.05 with `pace: fast`, P4: at most 1.05 there).
- Selectors: raw CSS, `text=Label`, `xpath=...`. No ego `@refs`, no `loc=`. Credentials only as `env:NAME`. Typed data from Datos de la serie (TUT7), fictitious.

## Steps (E2)

- N15: one step = one user action with a visible result, one task. What just happens ("Se abre el formulario", "El tipo Factura ya viene elegido") is never a step: it goes into the narration of the step before or after. Two tasks = two steps ("Abre Perseo XML" and "Configura la carpeta"). Filling a form is ONE step ("Completa los datos": every `type`/`select` of that form, top to bottom), never one step per field.
- N16: 2+ flows (even < 5 min) → `parts` with titles and `part: N` on every step, e.g. Parte 1 Configurar la carpeta / Parte 2 Comprobantes emitidos / Parte 3 Comprobantes recibidos. Same for long TUT (E3/TUT3).
- N17: set `context` on steps that switch system (`sri` on the page, `extension` in the popup); the narration says where you are ("En el SRI…", "En Perseo XML…").
- N18: show the extension's result after EVERY download (`result: {in: popup, sel: <summary>}` before `close`), not only the last one.
- N14: never narrate what is not on screen at that moment. If the narration names a screen or control ("la configuración", "Cambiar", "el resumen"), the step shows it (`follow: tab` / `focus` / `highlight`, never click what the user must not click); an effect sentence ("Aparece la lista.") only after the action that causes it.
- N10–N12: a form step becomes one still form shot with a spotlight moving field to field; do not add `focus:` per field (it would move the camera).
- End each page-changing step with `wait: SEL`. Every toast → `result: SEL` after its `wait`; every new row/card/menu item → `highlight: SEL`. `focus: SEL` when the narration reads something without clicking.
- Every element the narration mentions needs a selector in some action: the camera only frames logged boxes.
- C6, N4: short typed values (notes > 30 chars are retimed) that carry the brief's Historia (e.g. Origen "Feria"); the narration explains each chosen value.
- TUT5: login only in the first video of the series. RED/PRO/NOV leave login and obvious navigation out of `videos[].steps`; optional fields of a kept step go to `videos[].omit` (RED3, V5).
- Each part > 1 may open with a mini summary ("Hasta aquí ya tienes…").

## Structure per type

| Type | Structure | Opening example | Closing example | Duration |
| --- | --- | --- | --- | --- |
| TUT (TUT1, TUT6, N27) | objetivo → requisitos? → partes/pasos → resultado en detalle (→ siguiente video only if asked) | "Aprendes a crear contactos." | none (N27) or "Siguiente: registrar oportunidades." | free |
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
| Requirements (TUT1) | 5 s | ≤ 8; say what each thing is: "Necesitas la extensión Perseo XML instalada y tu sesión del SRI abierta." |
| RED step (RED3, C8) | ~4.5 s | ≤ 7 |

  RED ≥ 15 s: 3–4 steps of 6–7 words. A2: no silence > 1 s; a form step's sentence covers its typing.

- `pace: fast` (P2, §Parte 7; e.g. a short TUT with `max_seconds: 45`): one short sentence per step (≤ 6–7 words), only what the viewer does; opening ≤ 2 s with the requirement as the opening card `text` (no requirements card, or one ≤ 2.5 s); the voice is sped up (`tempo`). A download step that ends on a summary adds "Revisa el resumen." (it starts with the summary, N14, and covers its hold, A2); a click whose result is another screen may add a short effect sentence ("Con Change cambias la carpeta."). The badge says where you are, so "En el SRI" is only needed once. Lint's P1 budget assumes the fastest trimmed read (3 words/s): stay well under `max_seconds`, edit's real total decides.
- P4 (every pace): each caption block stays max(1.5, characters/15 + 0.4) s, each part separator 1.5 s on its own (nothing moves under it), each step ≥ 1.5 s. Budget with reading time, not voice: every step costs ~0.2 s + the reading time of its sentences + what happens after its click (new screen, result hold), every part 1.5 s. To fit `max_seconds` shorten or drop sentences ("Abre los comprobantes emitidos." instead of the full link name), never ask for shorter captions. Under `pace: fast` a one-sentence step with several actions ("Elige año, mes y día.", "Abre Consultas." over a menu path) is said over the chain and ends with its last action, so name the destination, not every click. What still plays in silence is what a click shows (a settings screen, a download summary): keep it short or give it a sentence. perseo-xml-v2 (13 steps, 3 parts, no effect sentences): 45.0 s under P4 with `max_seconds: 47` (round 5, T4).

## Narration rules (Parte 4)

- N1: the instruction comes first and short, one per step ("Haz clic en Guardar contacto."), the result sentence after; never after its result.
- N19: one sentence = one instruction = one caption (≤ 2 × 42 chars). Write short sentences; a sentence that does not fit is rewritten shorter, never split. Not "Abre Perseo XML. En Comprobantes emitidos, haz clic en XML Desde el RIDE." as one long block.
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
2. Write one `videos[]` entry per row of the brief's Tipo de video; default `tutorial` TUT 16:9 `steps: all` + `redes` RED 9:16 without login/navigation/optional steps. Group flows into `parts` (N16) and mark `context` (N17).
3. Write openings/closings per type (N2, N8, N27), narration overrides (N1, N4) and `omit` for RED; estimate each video's length with the budget above.
4. Run lint; fix every error and warning. Mark guessed selectors for `tutorial-ensayo-captura`.

## Output Contract

Report: tutorial.yaml path, step count, per video (id, type, format, steps, estimated duration), lint result, `env:NAME` names used (exists in `acceso.local.yaml`/`.env`, names only), selectors still unverified.
