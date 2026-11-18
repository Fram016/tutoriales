---
name: tutorial-voz
description: "Trigger: voz, locución, narrador, voz en off, generar voz, cambiar voz, TTS, voice, voiceover, narration audio, Gemini TTS. Synthesizes the opening, requirements, step and closing clips of every video with tools/tts.py (Gemini TTS, español neutro de Ecuador, tú)."
license: Apache-2.0
metadata:
  author: tutoriales
  version: "2.1"
---

## Activation Contract

Use after the take, or whenever any narration, voice or style changes. Rules by ID: `reglas/reglas-video.md`.

## Hard Rules

- Command: `.venv/Scripts/python.exe tools/tts.py <slug>` (online, needs GEMINI_API_KEY) or `--offline` (silent clips of estimated length, no cost; smoke tests and timing drafts only).
- Output per video id: `proyectos/<slug>/audio/voice/<id>/{opening, requirements?, <step>, closing}.wav` + `durations.json`. Each step uses `videos[].narration[step]` when set, else the step's `narration`. The cache keys clips by text hash + voice + style, so identical text in two videos is synthesized once. Every clip is trimmed of leading/trailing silence (~60 ms kept) before measuring, so `durations.json` is the real spoken length (N1, A2).
- Do not delete the voice directory to "refresh": changing one narration re-synthesizes only that clip. Changing `voice` or `style` regenerates every clip of every video (billed per character): confirm with the user first.
- Style must keep español neutro de Ecuador and trato de tú (L1, L4); never a voseo or regional style.
- Never ship offline (silent) clips: rerun online before the final render.

## Decision Gates

| Need | Set |
| --- | --- |
| Default for all tutorials | `.env`: `TTS_MODEL`, `TTS_VOICE`, `TTS_STYLE` (user edits it) |
| Per tutorial | `voice: {voice: Kore, style: "..."}` in tutorial.yaml |
| Firm / informative / upbeat / breezy / bright | `Kore` / `Charon` / `Puck` / `Aoede` / `Zephyr` |

Style example: `voz comercial cálida y clara, español neutro de Ecuador, trato de tú`. RED/PRO can ask for a faster, more energetic delivery in the per-tutorial style; TUT stays calm (TUT4).

## Execution Steps

1. Run tts.py, then everything after it up to compose (timings depend on `durations.json`): `.venv/Scripts/python.exe tools/pipeline.py <slug> --from edit --to compose` (`--video <id>` for one video), then `tutorial-qa` PRE.
2. Check durations: opening ≤ 3 s (RED hook 1–2 s), closing ≤ 2.5 s (E1, A2). If longer, shorten the text in tutorial.yaml (budget in `tutorial-guion`: words ≤ (s − 0.5) × 1.9) and rerun; only the changed clips are re-synthesized.
3. Mispronounced word: rewrite it phonetically or as words (numbers, acronyms) in that narration and rerun.

## Output Contract

Per video: voice, style, opening/closing/step durations, and which clips were re-synthesized vs cached.
