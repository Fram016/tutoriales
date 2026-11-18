---
name: tutorial-edicion
description: "Trigger: edición, editar video, cortes, acelerar, ritmo, pausas, silencios, música, música de fondo, mezcla, volumen, ducking, edit, cuts, speed up, pacing, background music, Lyria, mix, loudness, LUFS. Retimes the single take per video (edit.py), generates per-video Lyria music by type (music.py) and mixes voice + ducked music at -14 LUFS, peaks < -1 dBTP (mix.py)."
license: Apache-2.0
metadata:
  author: tutoriales
  version: "2.1"
---

## Activation Contract

Use after capture and tts (tts trims each clip's leading/trailing silence, keeping ~60 ms, before measuring `durations.json`, so timings are real). Order is fixed: `edit` → `music` → `mix` (music needs each video's final length; mix needs the timelines). Every stage runs for every entry in `videos:`. Rules by ID: `reglas/reglas-video.md`.

## Hard Rules

- Commands (repo root):
  - `.venv/Scripts/python.exe tools/edit.py <slug>` → `proyectos/<slug>/edit/<video>/{screen.mp4, timeline.json}` (timeline v2, absolute seconds).
  - `.venv/Scripts/python.exe tools/music.py <slug> [--offline] [--force]` → `audio/<video>/music.mp3` (Lyria), offline pad, or none.
  - `.venv/Scripts/python.exe tools/mix.py <slug>` → `audio/<video>/mix.wav`, 48 kHz stereo, -14 LUFS (`LOUDNESS_TARGET`), true peak < -1 dBTP (A1).
  - One video only: `.venv/Scripts/python.exe tools/pipeline.py <slug> --from edit --to mix --video <id>`.
- Lyria is billed (≈ USD 0.08/track, no free tier). music.py reuses existing tracks; `--force` only when the user wants new music or only the offline pad exists.
- Never hand-edit `timeline.json`; change tutorial.yaml (narration, steps, hold_ms, actions) and rerun.

## Timing rules owned by edit (per video)

| Rule | What edit does | If it still fails, change |
| --- | --- | --- |
| C4 | cuts near-blank frames (loads); speeds idle/waits ≤ 3× (faster for RED, RED3) | add `wait: SEL` for loaded content, recapture |
| C6 | typing at 13.5 chars/s; > 30 chars: ×3 after the first 15 | shorten the typed demo text |
| TUT4 | TUT: ≥ 1.5 s hold after each step's result/highlight | add `result:`/`highlight:` to that step |
| R2 | every `result` event visible ≥ 0.8 s | `result: SEL` right after its `wait:` |
| A2 | step = max(warped actions, voice + lead + tail); compresses action spans so voice gaps ≤ 1.0 s; closing ≤ 2.5 s | lengthen the step narration to cover the action, shorten the closing |
| E1 | opening ≤ 3 s (RED hook 1–2 s) | shorten `opening.narration` |
| N1 | places each step's voice so the instruction sentence ends ≤ 0.3 s after its action; inserts a pre-action hold when the narration is longer than the lead-in | shorten the instruction (one per step) |
| N6, R2 | the toast window is always kept (≥ 0.8 s) and exempt from C4 cuts | `result: SEL` on the toast |
| RED3 | `videos[].omit`: typing/select events on those selectors are cut from that video; the step stays | list only optional selectors |

- Each video uses only its `steps` minus its `omit` events; step numbers keep the original index (E2); RED shows no numbers (N7).
- Timeline events carry `frame_box` (control + label, C9) and `screen_at` (C10) for compose.
- Rerun edit only when the take, `steps`, `omit` or voice durations changed; music/mix reuse their outputs when the length and prompt did not change.
- RED/PRO/NOV pacing comes from the type; do not add `hold_ms` to slow them down.

## Music by type

| Type | Music (Tabla de decisión) | `videos[].music` example |
| --- | --- | --- |
| TUT | Suave o ninguna | `{prompt: "Soft corporate ambient, warm pads, calm"}` or `{none: true}` |
| RED | Rítmica | `{prompt: "Upbeat rhythmic pop, punchy drums, bright synths"}` |
| PRO | Marcada (PRO5: cuts to the beat) | `{prompt: "Driving electronic, strong beat, confident"}` |
| NOV | Suave | `{prompt: "Light ambient, gentle plucks, friendly"}` |

Prompt = genre + instruments + mood + energy, matching the brand; the tool appends "Instrumental only, no vocals, no lyrics" and the duration. A video without `music:` uses the global `music:`. `MUSIC_MODEL`: `lyria-3.5` (full length) or `lyria-3-clip-preview` (30 s clip, loops).

## Execution Steps

1. edit → music → mix, or `.venv/Scripts/python.exe tools/pipeline.py <slug> --from edit --to compose` (continue to compose + `qa.py --pre`; never render here).
2. Per video, check the mix output line: integrated ≈ -14 LUFS and true peak < -1 dBTP (A1); "(sin música)" means no track (expected only with `none: true`).
3. Check each `timeline.json` total against the type duration (RED 15–35 s, PRO 20–60 s, NOV 15–30 s); if over, remove steps from that video or shorten its narration overrides, then rerun from `tts`.

## Output Contract

Per video: total duration vs target, speed-ups/freezes worth noting, music source (Lyria/offline/reused/none) and measured LUFS / true peak.
