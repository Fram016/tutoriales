---
name: tutorial-replicar
description: "Trigger: replicar video, replicar tutorial, rehacer video, mejorar video, mejor calidad, transcribir video, a partir de este video, replicate video, remake video, improve video, transcribe. Mode B: transcribes an existing video, reconstructs one step list and the videos to produce into tutorial.yaml v2, then re-records it clean as mode A."
license: Apache-2.0
metadata:
  author: tutoriales
  version: "2.0"
---

## Activation Contract

Use when the user provides an existing tutorial video to replicate with better quality (clean 1080p take, TTS voice, music, captions; default TUT 16:9 + RED 9:16). Rules by ID: `reglas/reglas-video.md`.

## Hard Rules

- Command: `.venv/Scripts/python.exe tools/transcribe.py <video> --slug <slug>` → `proyectos/<slug>/replica/{audio.wav, transcript.json, transcript.txt, frames/*.jpg, frames.json}`. Whisper runs on CPU (`WHISPER_MODEL`, default small); long videos take minutes.
- The original video is a reference only: never reuse its audio or frames.
- You still need the live app URL and demo credentials (`proyectos/<slug>/acceso.local.yaml`, see `tutorial-brief`); the flow is re-recorded, not copied.
- If the video only teaches how the app works, use `tutorial-brief` with `transcribe.py <video> --slug <slug> --ref <name>` instead.
- When `proyectos/<slug>/brief.md` exists, its Objetivo, Audiencia, Enfoque and Tipo de video win over the original video.
- The original's defects do not carry over: rebuild to the rules (Parte 1 errors), e.g. add the missing opening/closing (E1), merge actions split into several steps (E2), and generate the vertical as RED, not as the horizontal cropped.

## Execution Steps

1. Run transcribe.py. Read `replica/transcript.txt` (timestamps) whole.
2. Look at the frames in `replica/frames/` (times in `frames.json`): screens, buttons clicked, fields typed, step order, brand.
3. Reconstruct ONE step list: one action with a visible result per step (E2), aligned to transcript segments; note selectors to discover (visible labels → `text=`), and the toast/new element of each result (`result:`/`highlight:`).
4. Improve the narration: remove fillers, repetitions and errors; apply `tutorial-guion` language (tú, glossary, device verbs); keep meaning and order. Data that looks real → series demo data.
5. Decide the video types (orchestrator `tutorial`), write `proyectos/<slug>/tutorial.yaml` v2 via `tutorial-guion` and run `tools/lint.py <slug>`; ask for the app URL, demo credentials and brand if not in the video.
6. Continue as mode A from `tutorial-ensayo-captura`.

## Output Contract

Report: original duration and step count vs the new step list and videos (id, type, format), rule defects of the original fixed, narration improvements, anything not reproducible (missing access, removed private data); then hand off to the orchestrator.
