---
name: tutorial-replicar
description: "Trigger: replicar video, replicar tutorial, rehacer video, mejorar video, mejor calidad, transcribir video, a partir de este video, replicate video, remake video, improve video, transcribe. Mode B: transcribes an existing video, reconstructs flow and narration into tutorial.yaml, then re-records it clean as mode A."
license: Apache-2.0
metadata:
  author: tutoriales
  version: "1.0"
---

## Activation Contract

Use when the user provides an existing tutorial video to replicate with better quality (clean 1080p take, TTS voice, music, captions, 16:9 + 9:16).

## Hard Rules

- Command: `.venv/Scripts/python.exe tools/transcribe.py <video> --slug <slug>` → `proyectos/<slug>/replica/{audio.wav, transcript.json, transcript.txt, frames/*.jpg, frames.json}`. Whisper runs on CPU (`WHISPER_MODEL`, default small); long videos take minutes.
- The original video is a reference only: never reuse its audio or frames in the output.
- You still need the live app URL and demo credentials; the flow is re-recorded, not copied.

## Execution Steps

1. Run transcribe.py. Read `replica/transcript.txt` (timestamps) whole.
2. Look at the frames in `replica/frames/` (use `frames.json` for their times) with the image-reading tool: identify screens, buttons clicked, fields typed, order of steps, and any brand (logo, colors).
3. Reconstruct the flow: one step per visible outcome, aligned to transcript segments. Note selectors to discover (visible labels → `text=`).
4. Improve the narration: remove fillers, repetitions and errors; apply the `tutorial-guion` style; keep the original meaning and order. Data seen on screen that looks real → replace with demo data.
5. Write `proyectos/<slug>/tutorial.yaml` via `tutorial-guion`; ask the user for the app URL, credentials (`.env`) and brand if not in the video.
6. Continue as mode A from `tutorial-ensayo-captura`.

## Output Contract

Report: original duration and step count vs new plan, narration improvements made, anything not reproducible (missing access, removed private data), then hand off to the orchestrator.
