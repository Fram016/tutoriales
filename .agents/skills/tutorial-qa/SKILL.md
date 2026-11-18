---
name: tutorial-qa
description: "Trigger: revisar video, control de calidad, verificar tutorial, revisar zoom, revisar subtítulos, revisar reglas, está bien el video, QA, quality check, review video, snapshots, qa --pre. Runs tools/qa.py --pre before any render (timeline + layout checks + snapshots, fix loop max 3 rounds), then the MP4 checks after the single final render; visual review against Parte 1 errors and Parte 4 observations."
license: Apache-2.0
metadata:
  author: tutoriales
  version: "2.1"
---

## Activation Contract

Use after compose (before any render) and after the final render; always before delivering. Never report a video as done without the automatic checks and the visual review passing. Rules by ID: `reglas/reglas-video.md` (Parte 1 errors, Parte 2–3 rules, Parte 4 observations and C7–C10, N1–N9).

## Hard Rules

- PRE (no MP4): `.venv/Scripts/python.exe tools/qa.py <slug> --pre [--video <id>]` runs every check that needs only `edit/<id>/timeline.json` + `hf-<id>/layout.json` (O1/O2/R2, T1, L1–L4, durations, C7–C10, N1–N3, N5–N7, N9) and prints snapshot PNG paths. The fix loop lives here.
- MP4: `.venv/Scripts/python.exe tools/qa.py <slug> [--video <id>]` after the single render: ffprobe resolution/duration/audio, A1 loudness, C4 blank-frame pixels (and any other check that needs the MP4). Writes `proyectos/<slug>/qa/<id>.json`.
- Read every failure: each names the rule ID; fix it before the visual review.
- Visual: open EVERY printed PNG with the image-reading tool. Never pass QA on text output alone.
- Any visible personal data, real credentials, notifications or personal tabs = fail; fix and re-record.
- Bound: at most 3 PRE fix rounds per slug, no render inside the loop; after the 3rd, stop and report the rules still failing. After the render, re-render only the failing video (`--video <id>`).

## Visual checklist (Parte 1 errors → what to look for)

| # | Rule | Look for |
| --- | --- | --- |
| 1, 18 | E1 | first 3 s say the goal (TUT) / pose the problem (RED); last 2–3 s show next video / CTA; not only title or "¡Listo!" |
| 2 | E2 | same step names and numbering in every video; one form = one step |
| 3 | C3 | the clicked element is fully in frame before the click |
| 4 | C4 | no near-empty screen (loads, spinners) |
| 5 | C2 | no duplicated fields or loose text fragments between zooms |
| 6 | C1 | no wide shot with unreadable text longer than 1 s |
| 7 | C5 | cursor the same size at every zoom |
| 8, 9 | O1 | step chip ("Paso N" only, TUT) off the logo/menu/header, fully opaque, readable |
| 10 | O2, R2 | toast in detail, without caption or cursor on top |
| 11 | O2, N3 | caption in its band, not covering the active or mentioned fields |
| 12 | T1 | no caption line ending in "el/la/de/con/y/…"; no caption across steps |
| 13 | O3 | same caption/chip style in every video |
| 14 | R3, N5 | new row/element clearly outlined in the brand color (accent = primary) |
| 15 | C6 | long text not typed slowly in full |
| 16 | A2 | no still closing card; no silence > 1 s |
| 17 | T3 | product name on one line |
| 19 | L1 | tú everywhere: narration, captions and the app's own texts |
| 20 | L2 | "haz clic" on desktop, "toca" on mobile |
| 21 | L3 | only glossary terms |
| 22 | V1 | 9:16 is a real crop: UI fills ≥ 70 % of the height, no shrunken horizontal |
| 23 | V2 | no button/field/label cut by the edge |
| 24 | V3 | title only in the opening |
| 25 | V4 | nothing important in top 15 % / bottom 20 % |
| 26 | V5, RED3 | RED has no login or obvious navigation; 15–35 s |

## Parte 4 observations (rule → what to look at in the --pre snapshots)

| Observation | Rule | Look for |
| --- | --- | --- |
| Todo en zoom, no se ubica la pantalla | C7 | each new screen opens with a full-screen 1.0× shot (≤ 1.0 s), then a zoom to the first element |
| Formulario fijo ~12 s | C8 | consecutive snapshots of a form change framing field by field (≤ 4 s TUT, ≤ 3 s RED) |
| Etiqueta "Nombre" cortada; campos cortados "Ape", "Telé" | C9, V2 | every active field shows its label and the whole control |
| Clic sobre la nada; paneo sobre zonas vacías | C10, C3 | after a screen change the camera cuts to the new framing; the click target is visible |
| "Haz clic en…" con el formulario ya abierto | N1 | the instruction caption is on screen before the action; never over its result |
| Etiqueta y subtítulo dicen lo mismo; apertura repetida | N2 | chip shows only "Paso N" (TUT); opening card text ≠ title idea |
| Subtítulos flotando sobre Notas y la tabla | N3 | captions in the fixed band (bottom in 16:9, dedicated band in 9:16), never over the UI |
| Se perdió la historia de la feria | N4 | the hook's story appears in the typed data and narration (e.g. Origen "Feria", note) |
| Naranja y cajas negras: parece otra marca | N5 | chip, lines, highlight and band in the app palette (`brand.primary`/`surface`); no black boxes, no foreign color |
| No se ve el aviso de confirmación | N6, R2 | the toast is framed ≥ 800 ms, clean |
| RED abre en "Paso 3"; texto repetido en RED | N7, N2 | no "Paso N" chip anywhere in RED/PRO/NOV |
| "Mira el tutorial completo" sin decir dónde | N8 | RED/PRO closing names the destination (from the brief) |
| Salta entre pantalla llena y franjas | N9 | one 9:16 composition across the whole RED |
| "Vera" en un campo que no se ve | C9, V2 | in RED every typed field is in frame; fields cut with `videos[].omit` do not appear |

Keep working (regression = fail): new row highlight clearly visible (now in the brand color, R3); the RED hook works as opening; RED ≈ 20 s (15–35 s); TUT closes with the next video; tú everywhere (L1).

Also per snapshot: cursor on the used element; screen shows the step's expected state; brand (logo, colors, font) correct in opening/closing.

## Fix → rerun from the right stage

| Failing rule | Change | Rerun (`tools/pipeline.py <slug> --from … --to compose`) |
| --- | --- | --- |
| E1, N2 (opening), N8 | `videos[].opening` / `closing` | `tts` |
| E2, V5, RED2, RED3 | `steps`, `videos[].steps` subset, `videos[].omit` | `capture` if `steps` actions changed, else `edit` (omit) / `tts` |
| C3, C4, C9 (no `frame_box`), wrong screen, private data | actions, `wait:`, selectors | `capture` |
| C6, N4 (data) | typed text (short, carries the story) | `capture` |
| C1, R1, R2, R3, N6, O2, V2 | missing `result:` / `highlight:` / `focus:` selector | `capture` |
| N1, A2, TUT4, silences | step narration: one instruction, short enough to end before its action | `tts` |
| A1 | music level/prompt (`music.py --force` if the track is the problem) | `mix` |
| L1–L4, T1, N4 (narration) | narration / `text` wording, glossary; app voseo → report to the user | `tts` (wording) or `compose` (`text` only) |
| T3 | `product`, shorter `title`/`text` | `compose` |
| N5, brand, logo | `brand:` (palette from the app) / `brand/` | `compose` |
| C2, C5, C7, C8, C10, N3, N7, N9, O1, O3, V1, V3, V4 | composition defect (not an input): report it with the snapshot | `compose` after a fix in `tools/compose.py` |

After each change: `tools/lint.py <slug>` (if tutorial.yaml changed), rerun to `compose`, `qa.py <slug> --pre` again. Only when PRE and snapshots pass: one render (`pipeline.py <slug> --only render --quality delivery`), then `qa.py <slug>`; a failing MP4 check re-renders only that video (`--video <id>`).

## Output Contract

Per video: `qa.py --pre` and MP4 `qa/<id>.json` failures by rule ID, each snapshot verdict (pass/fail + rule), fixes applied per PRE round (≤ 3), re-renders per video, and final status with any rule still failing.
