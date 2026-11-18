---
name: tutorial-qa
description: "Trigger: revisar video, control de calidad, verificar tutorial, revisar zoom, revisar subtítulos, revisar reglas, está bien el video, QA, quality check, review video, snapshots. Runs tools/qa.py automatic rule checks per video (qa/<video>.json), then the mandatory visual review against the 26 known errors; fixes via tutorial.yaml + pipeline.py --from, max 3 rounds."
license: Apache-2.0
metadata:
  author: tutoriales
  version: "2.0"
---

## Activation Contract

Use after every render and always before delivering. Never report a video as done without both the automatic checks and the visual review passing. Rules by ID: `reglas/reglas-video.md` (Parte 1 errors, Parte 2–3 rules).

## Hard Rules

- Automatic: `.venv/Scripts/python.exe tools/qa.py <slug> [--video <id>]`. Per video it checks ffprobe (resolution, duration, audio), the automatic rules (C4 blank frames, O1/O2/R2 overlap from `hf-<id>/layout.json`, A1/A2 loudness and silences, T1 line length and final word, L1–L4 forbidden terms, type durations), writes `proyectos/<slug>/qa/<id>.json` and prints snapshot PNG paths.
- Read every `qa/<id>.json` failure: each names the rule ID; fix it before the visual review.
- Visual: open EVERY printed PNG with the image-reading tool. Never pass QA on text output alone.
- Any visible personal data, real credentials, notifications or personal tabs = fail; fix and re-record.
- Bound: at most 3 fix rounds per slug; after the 3rd, stop and report the rules still failing.

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
| 8, 9 | O1 | step chip off the logo/menu/header, fully opaque, readable |
| 10 | O2, R2 | toast in detail, without caption or cursor on top |
| 11 | O2 | caption not covering the active or mentioned fields |
| 12 | T1 | no caption line ending in "el/la/de/con/y/…"; no caption across steps |
| 13 | O3 | same caption/chip style in every video |
| 14 | R3 | new row/element clearly outlined in the accent color |
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

Also per snapshot: cursor on the used element; screen shows the step's expected state; brand (logo, colors, font) correct in opening/closing.

## Fix → rerun from the right stage

| Failing rule | Change | Rerun (`tools/pipeline.py <slug> --from …`) |
| --- | --- | --- |
| E1 | `videos[].opening` / `closing` | `tts` |
| E2, V5, RED2, RED3 | `steps` (merge split actions), `videos[].steps` subset | `capture` if steps changed, else `tts` |
| C3, C4, wrong screen, private data | actions, `wait:`, selectors | `capture` |
| C6 | shorter typed text | `capture` |
| C1, R1, R2, R3, O2, V2 | missing `result:` / `highlight:` / `focus:` selector | `capture` |
| A2, TUT4, silences | step narration covering the action, shorter closing | `tts` |
| A1 | music level/prompt (`music.py --force` if the track is the problem) | `mix` |
| L1–L4, T1 | narration / `text` wording, glossary; app voseo → report to the user | `tts` (wording) or `compose` (`text` only) |
| T3 | `product`, shorter `title`/`text` | `compose` |
| C2, C5, O1, O3, V1, V3, V4 | composition defect (not an input): report it with the frame | `compose` after a fix in `tools/compose.py` |
| Brand, logo | `brand:` / `brand/` | `compose` |

Run `.venv/Scripts/python.exe tools/pipeline.py <slug> --from <stage> --quality draft [--video <id>]` (it runs `lint` first when starting from the beginning; run `tools/lint.py <slug>` after every tutorial.yaml edit), then qa.py again.

## Output Contract

Per video: qa.py result and `qa/<id>.json` failures by rule ID, each snapshot verdict (pass/fail + rule), fixes applied per round (≤ 3), and final status with any rule still failing.
