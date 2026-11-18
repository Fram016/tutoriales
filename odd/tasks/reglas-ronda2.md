# Reglas ronda 2: observaciones del usuario + pipeline en 10-12 min

Apply the user's second-round observations (reglas/reglas-video.md §Parte 4, rules C7-C10, N1-N9) and cut a full run from ~46 min to ~10-12 min; then a fresh agent re-makes the TUT and RED videos.

## Specs

- S1 Observations verbatim in reglas/reglas-video.md §Parte 4 ("Tutorial (horizontal, 39 s)", "Redes (vertical, 21 s)", "Lo que sí funciona" must keep working) and the derived rules C7-C10, N1-N9 in the same section.
- S2 "corrige las skills en base a estas observaciones mas las como bajar el tiempo unos 10 a 12 minutos" — the time plan accepted by the user: (1) check before rendering (layout.json + timeline + short snapshots), (2) one final render, (3) re-render only the failing video (--video), (4) real voice durations (trim TTS silence; lint estimate realistic), (5) render both videos in parallel.
- S3 "lanza un subagente desde cero que haga nuevamente los videos de redes y de tutorial".

## Tasks

- [ ] T1 S1,S2 — Timing: recorder label boxes, narration-before-action sync, videos[].omit, TTS silence trim, pipeline fast path — worker WB2
- [ ] T2 S1,S2 — Composition: establishing shot, per-field framing, hard cuts, caption band, palette from brand, chips, R2 toast, parallel render — worker WA2
- [ ] T3 S1,S2 — Validation: qa.py --pre (no MP4), new checks C7-C10/N1-N9, lint updates — worker WC2
- [ ] T4 S1,S2 — Skills + README: new rules, fast workflow, story, palette, CTA destination — worker WD2
- [ ] T5 — Integration: unit tests + offline smoke PASS — parent
- [ ] T6 S3 — Fresh agent from scratch: Nexo CRM TUT + RED with the fast workflow — worker

## Log

- L1 (user, verbatim; full observations in reglas/reglas-video.md §Parte 4): "tengo esas observaciones, corrige las skills en base a estas observaciones mas las como bajar el tiempo unos 10 a 12 minutos y lanza un subagente desde cero que haya nuevamente los videos de redes y de tutorial"
- L2 (decisions taken by the parent from the observations): R2 wins over C4 (N6: toast always shown, its window exempt from C4). E2 vs RED3 resolved with one take + `videos[].omit` (RED cuts the typing of fields that do not carry the story). Glossary: UI values in quotes are allowed (already in lint). Chip shows only "Paso N" in TUT and nothing in RED/PRO/NOV (N2, N7). CTA destination comes from the brief (`cta_destination`).
- L3 (contract changes on top of odd/tasks/reglas-video.md L2-L6):
  - tutorial.yaml: `videos[].omit: [SELECTOR, ...]` (typing/select events on those selectors are cut from that video; the step stays). `videos[].opening.text` is optional and must not paraphrase `title` (N2). Step `title` stays in the yaml (brief/worklog) but is not rendered. `brand` defaults: accent = primary (never an invented color); `brand.surface` (caption band background, default = dark brand color) and `brand.on_surface` (text, default #ffffff).
  - actions.json/timeline events: type/select/click events may carry `frame_box` = union of the control box and its visible label (label[for=id], or the closest field wrapper), used for framing (C9). `screen_at` stays (C10).
  - timeline: each step event carrying an instruction gets the voice placed so the instruction sentence ends ≤0.3 s after the action time (N1): edit inserts a pre-action hold when the narration is longer than the lead-in. Cards use measured voice durations after silence trimming.
  - tts: trim leading/trailing silence of every clip (ffmpeg silenceremove, keep ~60 ms) before measuring.
  - layout.json: items get `color`; new item kinds `band` (caption band rect) and `establishing` camera segments (kind "context" with reason "establishing").
  - qa.py: `--pre` runs every check that needs only timeline.json + layout.json (+ snapshots), no MP4; the MP4 checks (A1, C4 pixels, duration, resolution) run without --pre.
  - render.py: renders all requested videos in parallel (one process per video, workers split across cores) and supports `--video ID`.
- L4 (fast workflow, to be written in the skills): lint → capture → tts → edit → music → mix → compose → `qa.py --pre` + snapshots (fix loop here, up to 3 rounds, no render) → ONE render at final quality → `qa.py` (MP4 checks) → re-render only a failing video. Target ≤12 min for a ~1 min TUT + ~20 s RED.
