# Ronda 5: tutorial Perseo XML v2 en 45 s, ritmo ágil y menos zoom

Re-edit the existing take of proyectos/perseo-xml-v2 (no recapture) into a ≤45 s, fast-paced TUT with lighter zoom.

## Specs

- S1 "dura un minuto para funciones que se pueden mostrar en maximo 45 segundos" — total ≤ 45 s (P1).
- S2 "siento qeu va a un ritmo lento" — fast pace (P2).
- S3 "diria usar menos zoom para que se vean mejor los formularios" — less zoom, whole forms visible (P3).

## Tasks

- [x] T1 S1-S3 — Tools: `pace: fast` + `max_seconds` (schema, edit speeds/holds/cards, tts tempo, compose zoom ranges/separators/establishing, lint+qa thresholds) — worker
- [x] T2 S1-S3 — Perseo XML v2: short narration (budget), pace fast, max_seconds 45; re-run tts→render on the existing capture; QA + frame review — parent/worker
- [ ] T3 — Deliver

## Log

- L1 (user): "Esta mucho mejor pero hay un proboema, dura un minuto para funciones que se pueden mostrar en maximo 45 segundos, ademas no se ve tan bien realmente siento qeu va a un ritmo lento y diria usar menos zoom para que se vean mejor los formularios"
- L2 (decision): reuse proyectos/perseo-xml-v2/capture (valid take, censor verified); no SRI access needed. Rules P1-P3 in reglas/reglas-video.md §Parte 7 override TUT4 and the C1 detail range for `pace: fast`.
- L3 (current state): 105 s total (opening + requirements 6.8 s + 3 separators + 13 steps); downloads ~10 s each on screen; detail zoom 1.4–1.6×, popup 1.32×.
- L4 (result): 43.4 s, QA PASS except C4.empty_frames on sparse real pages (settings, whole forms) — accepted: P3 "menos zoom" is the latest user request and prevails over C4 for whole-page/whole-form shots.
- L5 (user): "No, cuando muestras los pasos no deja leer es muy rapdio" → rule P4 (reading time). T4: apply P4 in tools + re-edit perseo-xml-v2 (≤45 s still), no recapture.
- [ ] T4 P4 — reading time for separators/captions/chips, tempo ≤1.05, re-edit perseo-xml-v2 ≤45 s — worker
