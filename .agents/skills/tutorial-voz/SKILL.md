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
- Output per video id: `proyectos/<slug>/audio/voice/<id>/{opening, requirements?, <step>, closing?}.wav` (TUT closing optional, N27) + `durations.json`. Each step uses `videos[].narration[step]` when set, else the step's `narration`. D5 (one voice tone): the clips of a video are one batch; the cache key carries model + voice + style + tempo + `pronunciation` + the video's ordered narrations, so changing ONE narration re-synthesizes every clip of that video (never mixed with clips of earlier runs) and each video is its own batch. The batch is ONE request (one line per clip) cut at its pauses; when the cut is not trustworthy tts asks each clip alone and prints `aviso (D5)`. Every clip is trimmed of leading/trailing silence (~60 ms kept), sped up by the tempo and leveled to the same loudness (`tts.VOICE_LUFS`, one gain per clip) before measuring, so `durations.json` is the real spoken length (N1, A2). No per-clip voice or style.
- Do not delete the voice directory to "refresh": an unchanged video comes from the cache. Changing one narration, the tempo or the pronunciation map re-synthesizes that whole video (D5); changing `voice` or `style` regenerates every video (billed per character): confirm with the user first.
- D3: `pronunciation: {TERM: reading}` at the top of tutorial.yaml (e.g. `{RIDE: "ri de"}`): the voice reads the reading (whole word, case-sensitive); captions keep the term. Lint validates the map.
- D5 check: `qa.py` reports `D5.pitch` (each clip's mean F0 against the video median: WARN over ±2 semitones, listen to it; FAIL over ±4, another tone; intonation alone spans about ±3 inside one request) and `D5.loudness` (FAIL over ±3 LU). A failing clip: rerun tts for the video (a new batch) after a wording change, or report it.
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
3. Mispronounced word or acronym: add it to `pronunciation` (D3; the caption keeps the written form) and rerun.

## Output Contract

Per video: voice, style, tempo, opening/closing/step durations, whether the batch was re-synthesized or cached, and the D5 pitch/loudness spread from qa.
