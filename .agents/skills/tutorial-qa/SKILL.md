---
name: tutorial-qa
description: "Trigger: revisar video, control de calidad, verificar tutorial, revisar zoom, revisar subtítulos, revisar reglas, está bien el video, QA, quality check, review video, snapshots, qa --pre. Runs tools/qa.py --pre before any render (timeline + layout checks + snapshots, fix loop max 3 rounds), then the MP4 checks after the single final render; visual review against Parte 1 errors and Parte 4–6 observations."
license: Apache-2.0
metadata:
  author: tutoriales
  version: "2.3"
---

## Activation Contract

Use after compose (before any render) and after the final render; always before delivering. Never report a video as done without the automatic checks and the visual review passing. Rules by ID: `reglas/reglas-video.md` (Parte 1 errors, Parte 2–3 rules, Parte 4–6: C1 revised, C7–C10, N1–N27).

## Hard Rules

- PRE (no MP4): `.venv/Scripts/python.exe tools/qa.py <slug> --pre [--video <id>]` runs every check needing only `edit/<id>/timeline.json` + `hf-<id>/layout.json` (C1, O1/O2/R2, T1, L1–L4, durations, C7–C10, N1–N3, N5–N7, N9–N27 where checkable from data, V2) and prints snapshot PNG paths. The fix loop lives here.
- MP4: `.venv/Scripts/python.exe tools/qa.py <slug> [--video <id>]` after the single render: resolution/duration/audio, A1 loudness, C4 blank-frame pixels. Writes `proyectos/<slug>/qa/<id>.json`.
- Each failure names its rule ID; fix it before the visual review.
- Visual: open EVERY printed PNG with the image-reading tool. Never pass QA on text output alone.
- Visible personal data, real credentials, notifications or personal tabs = fail; fix and re-record.
- Bound: ≤ 3 PRE fix rounds per slug, no render inside the loop; after the 3rd, stop and report what still fails. After the render, re-render only the failing video (`--video <id>`).

## Visual checklist (rule → look for)

| Rule | Look for |
| --- | --- |
| E1, N27 | first 3 s say the goal (TUT) / pose the problem (RED); RED/PRO end with the CTA; TUT ends on the final result (closing card only if asked); not only title or "¡Listo!" |
| E2, N15 | same step names and numbering in every video; one form = one step; every step is a user action with one task (no "Se abre…", "ya viene elegido" steps) |
| N13 | every highlight/click box sits on a visible element whose text matches the caption (no empty boxes, no "Certificados" for "Comprobantes emitidos") |
| N14, N1 | what the caption names is on screen at that moment (extension open, settings, "Cambiar", the summary); "Aparece la lista" never over an already visible list |
| N16 | 2+ flows: "Parte N: título" separators and chip "Parte N · Paso M" |
| N17 | context badge says where you work (SRI / extension); brand color only for the product and highlights |
| N18 | the extension summary (downloaded / errors) in detail after EVERY download |
| N19 | one sentence per caption block, none split ("…Para una consulta corta, / elige…"), never two instructions in one block |
| N20 | no black borders around the page; UI text readable everywhere (no tiny full tables) |
| N21 | caption band ≤ 1/8 of the height |
| N22 | the extension popup never cut by the frame edge (also on the result) |
| N23 | no promos in the popup (Club, Facturito, "Únete gratis") |
| N24 | logo readable on the opening card |
| N25 | the same sensitive categories blurred in every table and screen, incl. chrome:// pages |
| N26 | no blank screen during navigation, no two pages mixed ("Cr / usu") |
| C1 | detail ≈ 1.4–1.8× (not tighter); no wide shot with unreadable text > 1 s |
| N10, N11, N12 | form shot: no per-field camera moves, whole form visible (whole width in 9:16), spotlight on the active field in the brand primary, rest dimmed ≤ 25 % |
| C2 | no duplicated fields or loose text fragments between zooms |
| C3 | clicked element fully in frame before the click |
| C4 | no near-empty screen (loads, spinners), also right after a screen change before the toast |
| C5 | cursor the same size at every zoom |
| C7 | each new screen opens with a 1.0× shot (≤ 1.0 s), then zooms to the first element |
| C8 | no identical framing > 4 s TUT / 3 s RED (in a form shot the spotlight move counts) |
| C9, V2 | every active field shows its label and whole control; no neighbor field or label cut ("Ape", "Telé", "Carg", "Orig") |
| C10 | a screen change cuts to the new framing or the result; no pan over empty areas, no click on nothing |
| O1, N2, N7 | TUT chip "Paso N" only, opaque, off logo/menu/header; no chip in RED/PRO/NOV |
| O2, R2, N6 | toast in detail ≥ 0.8 s clean at real speed: no caption or cursor over it (a caption in the band outside the UI does not cover it) |
| O2, N3 | caption in its fixed band, never over active or mentioned fields |
| O3 | same caption/chip style in every video |
| N1 | instruction caption on screen before its action, never over its result |
| N4 | the hook's story appears in typed data and narration |
| N5, R3 | chip, lines, highlight, spotlight and band in the app palette; new row outlined in the brand color; no black boxes |
| N8 | RED/PRO closing names the destination |
| N9, V1 | one stable 9:16 composition; real crop, UI ≥ 70 % of the height |
| V3, V4 | title only in the opening; nothing important in top 15 % / bottom 20 % |
| V5, RED3 | RED: no login or obvious navigation, 15–35 s; `omit` fields do not appear |
| C6 | long text not typed slowly in full |
| A2 | no still closing card; no silence > 1 s |
| T1, T3 | no caption line ending in "el/la/de/con/y/…", none across steps; product name on one line |
| L1–L3 | tú everywhere (also the app's texts); "haz clic" desktop / "toca" mobile; glossary terms only |

Regressions = fail: new-row highlight visible (R3), RED hook works, RED ≈ 20 s, TUT requirements card, -14 LUFS, consistent readable step chips, tú everywhere. Per snapshot also: cursor on the used element, expected screen state, brand (logo, colors, font) in opening/closing.

## Fix → rerun from the right stage

| Failing rule | Change | Rerun (`tools/pipeline.py <slug> --from … --to compose`) |
| --- | --- | --- |
| E1, N2 (opening), N8 | `videos[].opening` / `closing` | `tts` |
| E2, V5, RED2, RED3 | `steps`, `videos[].steps`, `videos[].omit` | `capture` if actions changed, else `edit` (omit) / `tts` |
| C3, C4, C9, N10 (no `frame_box`/`form_box`), N13, N14 (screen not shown), N18, N23, N25, N26, wrong screen, private data | actions, `wait:`, visible-scoped selectors, `follow: tab`, `result:` summary, `surfaces.hide`, `censor`, form container | `capture` |
| N15, N16, N17, N27 | split/merge steps, `parts`/`part`, `context`, drop TUT `closing` | `capture` if actions changed, else `tts` |
| N19 | one short sentence per instruction | `tts` |
| C6, N4 (data) | typed text (short, carries the story) | `capture` |
| C1, R1, R2, R3, N6, O2, V2 | missing `result:` / `highlight:` / `focus:` selector | `capture` |
| N1, A2, TUT4, silences | step narration: one short instruction before its action | `tts` |
| A1 | music level/prompt (`music.py --force` if the track is the problem) | `mix` |
| L1–L4, T1, N4 (narration) | wording, glossary; app voseo → report to the user | `tts` (wording) or `compose` (`text` only) |
| T3 | `product`, shorter `title`/`text` | `compose` |
| N5, N24, brand, logo | `brand:` / `brand/` (light logo) | `compose` |
| C2, C5, C7, C8, C10, N3, N7, N9, N11, N12, N20, N21, N22, O1, O3, V1, V3, V4 | composition defect: report it with the snapshot | `compose` after a fix in `tools/compose.py` |

After each change: `tools/lint.py <slug>` (if tutorial.yaml changed), rerun to `compose`, `qa.py <slug> --pre` again. Only when PRE and snapshots pass: one render (`pipeline.py <slug> --only render --quality delivery`, background runner or timeout ≥ 900 s, then check exit code + log tail), then `qa.py <slug>`.

## Output Contract

Per video: `qa.py --pre` and MP4 `qa/<id>.json` failures by rule ID, each snapshot verdict (pass/fail + rule), fixes per PRE round (≤ 3), re-renders per video, and final status with any rule still failing.
