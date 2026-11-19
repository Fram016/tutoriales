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
- Long commands (pipeline, music, anything that may exceed ~1 min): harness background runner (`bash_background`) or an explicit timeout ≥ 900 s, never a short shell timeout; then check the exit code and the log tail. Never assume a silent command is still running.
- Never hand-edit `timeline.json`; change tutorial.yaml (narration, steps, hold_ms, actions) and rerun.

## Timing rules owned by edit (per video)

| Rule | What edit does | If it still fails, change |
| --- | --- | --- |
| C4, N26 | cuts near-blank and mixed frames (loads, navigation transitions); speeds idle/waits ≤ 3× (faster for RED, RED3) | add `wait: SEL` for loaded content, recapture |
| C6 | typing at 13.5 chars/s; > 30 chars: ×3 after the first 15 | shorten the typed demo text |
| TUT4 | TUT: ≥ 1.5 s hold after each step's result/highlight | add `result:`/`highlight:` to that step |
| R2 | every `result` event visible ≥ 0.8 s | `result: SEL` right after its `wait:` |
| A2 | step = max(warped actions, voice + lead + tail); compresses action spans so voice gaps ≤ 1.0 s; closing ≤ 2.5 s | lengthen the step narration to cover the action, shorten the closing |
| E1 | opening ≤ 3 s (RED hook 1–2 s) | shorten `opening.narration` |
| N1, N14 | places each step's voice so the instruction sentence ends ≤ 0.3 s after its action and effect sentences play over their effect; inserts a pre-action hold when the narration is longer than the lead-in | shorten the instruction (one per step) |
| N6, R2 | the toast/result window is always kept, at 1.0× speed (never sped up) for ≥ R2 clean time + margin, and exempt from C4 cuts | `result: SEL` on the toast |
| RED3 | `videos[].omit`: typing/select events on those selectors are cut from that video; the step stays | list only optional selectors |

- `videos[].pace: fast` (P2) replaces TUT4: holds of 0.5 s after results (R2/N6 still keep a toast ≥ 0.8 s clean), idle up to 8× and any wait longer than ~1 s on screen cut to its first and last state (download: spinner, then the summary), lead 0.2 s / tail 0.1 s per step, opening ≤ 2 s, requirements ≤ 2.5 s, only the C3 lead before the first field of a new screen (the form shot is the establishing shot); the click inside an opened surface is the step's main action (N1) and its effect sentence waits for the step's result. tts speeds the voice by `tempo` (atempo, after trimming, cached per tempo). `max_seconds` (P1) is carried to the timeline; edit warns when the total exceeds it.
- P4 (every pace): edit owns the reading time. The first step of every part opens with 1.5 s of its first frame under the "Parte N" separator (timeline `parts[].start/duration`; voice, actions and captions come after it; that time is no A2 gap). A step never ends before its captions have been read from its voice start (compose.caption_span: each block max(its share of the voice, max(1.5, characters/15 + 0.4) s)) nor, in TUT, before 1.5 s (chip): the last frame is held or idle runs slower. compose schedules the captions with the same times, back to back, never under a separator; qa checks P4.captions/separators/chips. Fast voice tempo ≤ 1.05.
- Fast pace, one-sentence narration over several pointer actions: the main action (N1) is the last of them, so the voice covers the chain instead of ending at its first action (A2); qa's N1 uses the timeline `action_t` under fast. compose never snaps a click's screen mark to a pixel change at or before the click, and a highlight ends at the next screen change.
- Each video uses only its `steps` minus its `omit` events; step numbers keep the original index (E2); RED shows no numbers (N7).
- Timeline events carry `frame_box` (control + label, C9) and `screen_at` (C10) for compose.
- Rerun edit only when the take, `steps`, `omit` or voice durations changed; music/mix reuse their outputs when the length and prompt did not change.
- RED/PRO/NOV pacing comes from the type; do not add `hold_ms` to slow them down.

## Music by type

| Type | Music (Tabla de decisión) | `videos[].music` example |
| --- | --- | --- |
| TUT | Suave o ninguna | `{prompt: "Calm mood, soft warm pads, gentle piano, slow tempo"}` or `{none: true}` |
| RED | Rítmica | `{prompt: "Energetic bright mood, punchy drums, bright synth plucks, fast tempo"}` |
| PRO | Marcada (PRO5: cuts to the beat) | `{prompt: "Confident driving mood, strong steady beat, synth bass, medium-fast tempo"}` |
| NOV | Suave | `{prompt: "Friendly light mood, gentle plucks, soft pads, medium tempo"}` |

Prompt = mood + instruments + tempo/energy, matching the brand. Never genres tied to commercial music (pop, reggaeton, rock…) or artist names: Lyria blocks them as "recitation"; music.py then retries once with a neutral instrument-only prompt and logs it (rewrite the prompt if it keeps failing). The tool appends "Instrumental only, no vocals, no lyrics" and the duration. A video without `music:` uses the global `music:`. `MUSIC_MODEL`: `lyria-3.5` (full length) or `lyria-3-clip-preview` (30 s clip, loops).

## Execution Steps

1. edit → music → mix, or `.venv/Scripts/python.exe tools/pipeline.py <slug> --from edit --to compose` (continue to compose + `qa.py --pre`; never render here).
2. Per video, check the mix output line: integrated ≈ -14 LUFS and true peak < -1 dBTP (A1); "(sin música)" means no track (expected only with `none: true`).
3. Check each `timeline.json` total against the type duration (RED 15–35 s, PRO 20–60 s, NOV 15–30 s); if over, remove steps from that video or shorten its narration overrides, then rerun from `tts`.

## Output Contract

Per video: total duration vs target, speed-ups/freezes worth noting, music source (Lyria/offline/reused/none) and measured LUFS / true peak.
