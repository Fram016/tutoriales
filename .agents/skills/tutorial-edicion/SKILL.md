---
name: tutorial-edicion
description: "Trigger: edición, editar video, cortes, acelerar, música, música de fondo, mezcla, volumen, ducking, edit, cuts, speed up, background music, Lyria, mix, loudness, LUFS. Cuts the take to the narration (edit.py), generates Lyria music (music.py) and mixes voice + ducked music at -14 LUFS (mix.py)."
license: Apache-2.0
metadata:
  author: tutoriales
  version: "1.0"
---

## Activation Contract

Use after capture and tts. Order is fixed: `edit` → `music` → `mix` (music needs the final length; mix needs the timelines).

## Hard Rules

- Commands (repo root):
  - `.venv/Scripts/python.exe tools/edit.py <slug>` → `proyectos/<slug>/edit/{full,short}/{screen.mp4, timeline.json}`.
  - `.venv/Scripts/python.exe tools/music.py <slug> [--offline] [--force]` → `audio/music.mp3` (Lyria) or `audio/music.wav` (offline pad).
  - `.venv/Scripts/python.exe tools/mix.py <slug>` → `audio/{full,short}/mix.wav`, 48 kHz stereo, -14 LUFS (`LOUDNESS_TARGET`), -1.5 dBTP ceiling.
- Lyria is billed (≈ USD 0.08/track, no free tier). music.py reuses any existing track; pass `--force` only when the user wants new music or when only the offline `music.wav` pad exists (it is reused too, and mix.py picks `music.mp3` first).
- Do not hand-edit `timeline.json`; change tutorial.yaml and rerun.

## How edit.py sizes cuts

- Each step keeps its real action span. If the action is much longer than voice + 0.8 s, it is sped up (max 3x: slow typing, waits).
- If the voice is longer than the action, the last frame is frozen until the voice ends.
- Events (click/type/hover) are remapped to output time for cursor, zoom and captions. full = all steps; short = `summary: true` steps (all steps if none).
- To fix pacing: shorten/lengthen `narration`, add `hold_ms` to show a result longer, or remove `pause:` actions.

## Music prompt guidance

Set `music: {prompt: ...}` in tutorial.yaml: genre + instruments + mood + energy, matching the brand ("Corporate ambient, soft synth pads, light percussion, positive and calm"). The tool already appends "Instrumental only, no vocals, no lyrics" and the duration. `MUSIC_MODEL`: `lyria-3.5` (full length) or `lyria-3-clip-preview` (30 s clip, loops).

## Execution Steps

1. edit → music → mix, or `.venv/Scripts/python.exe tools/pipeline.py <slug> --from edit --to mix`.
2. Check the mix output line: integrated LUFS ≈ -14 and peak ≤ -1.5 dBTP; "(sin música)" means no track was found.

## Output Contract

Report per-variant total duration, speed-ups/freezes worth noting, music source (Lyria/offline/reused) and measured LUFS.
