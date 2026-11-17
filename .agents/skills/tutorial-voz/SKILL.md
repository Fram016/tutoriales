---
name: tutorial-voz
description: "Trigger: voz, locución, narrador, voz en off, generar voz, cambiar voz, TTS, voice, voiceover, narration audio, Gemini TTS. Synthesizes one Gemini TTS clip per step with tools/tts.py (Latin American Spanish commercial voice)."
license: Apache-2.0
metadata:
  author: tutoriales
  version: "1.0"
---

## Activation Contract

Use after the take, or whenever narration, voice or style changes.

## Hard Rules

- Command: `.venv/Scripts/python.exe tools/tts.py <slug>` (online, needs GEMINI_API_KEY) or `--offline` (silent clips of estimated length, no cost; for smoke tests and timing drafts only).
- Output: `proyectos/<slug>/audio/voice/<step>.wav` + `durations.json`; `cache.json` keys each clip by text+voice+style.
- Do not delete the voice directory to "refresh": changing one narration re-synthesizes only that step. Changing `voice` or `style` regenerates all steps (billed per character), so confirm with the user first.
- Never ship offline (silent) clips: rerun online before the final render.

## Decision Gates

| Need | Set |
| --- | --- |
| Default for all tutorials | `.env`: `TTS_MODEL`, `TTS_VOICE`, `TTS_STYLE` (user edits it) |
| Per tutorial | `voice: {voice: Kore, style: "..."}` in tutorial.yaml |
| Firm / informative / upbeat / breezy / bright | `Kore` / `Charon` / `Puck` / `Aoede` / `Zephyr` |

Style string example: `voz comercial cálida y clara, español latinoamericano neutro, ritmo ágil y profesional`.

## Execution Steps

1. Run tts.py. Then run edit and everything after it again (timings depend on `durations.json`): `.venv/Scripts/python.exe tools/pipeline.py <slug> --from edit`.
2. If a word is mispronounced, rewrite it phonetically or as words in `narration` (e.g. numbers, acronyms) and run again.

## Output Contract

Report voice, style, per-step durations and which steps were re-synthesized vs cached.
