# Reglas ronda 3: menos zoom, plano de formulario y fallas pendientes

Apply the user's third-round request (reglas/reglas-video.md §Parte 5: C1 revised, N10-N12), fix the three QA failures of the v3 run, the time losses, and re-run a fresh agent.

## Specs

- S1 "si me agrada las mejoras aplicalas" — the improvements proposed after the v3 run: (a) C4 near-empty frames after a screen change before the toast cut (TUT ≈0:33); (b) RED toast clean only 0.60 s: edit must not speed up the R2 window and qa R2 must not count a caption in the band (outside the UI viewport) as covering; (c) V2 neighbor fields cut in 9:16; (d) long-running commands must never be killed silently (run in background / no 120 s shell timeout, check exit code); (e) Lyria "recitation" block: prompts without genre/artist names + one automatic retry with a neutral prompt; (f) measure render settings to cut the ~5 min render without visible loss.
- S2 "sumale que no haga tanto zoom un poco menos de zoom" — C1 revised: detail 1.4–1.8×.
- S3 "cuando sean cosas de formularios quizas pantalla completa sin zoom con recuadro remarcado o que me recomiendas?" — accepted recommendation N10-N12: form framing fitted to the form (1.1–1.5×, ≤1.8×), active-field brand outline + spotlight (≤25 % dim) moving 250–400 ms between fields, whole form across the width in 9:16.
- S4 Fresh agent from scratch re-makes TUT + RED (same as previous rounds).

## Tasks

- [ ] T1 S1,S3 — recorder form_box, edit keeps R2 window real-time, music retry — worker WB3
- [ ] T2 S1,S2,S3 — compose: zoom ranges, form framing + spotlight, screen-change cut to result, render benchmark/defaults — worker WA3
- [ ] T3 S1,S2,S3 — qa/lint: C1 new range, N10-N12 checks, V2 neighbors, R2 band fix — worker WC3
- [ ] T4 S1,S2,S3 — skills/README/_demo: zoom/form rules, long-command rule, Lyria prompt rules — worker WD3
- [ ] T5 — Integration: unit tests + smoke PASS — parent
- [ ] T6 S4 — Fresh agent v4 — worker

## Log

- L1 (user): "edta mucho mejor y si me agrada las mejoras aplicalas, sumale que no haga tantanto zoom un poco memenos de zoom y cusndo sean cosas de formularios quizas pantalla comoleta sin zoom con recuadro remarcado o que me recomiendas?"
- L2 (parent recommendation, applied): full screen without zoom is unreadable for forms (≈11-12 px text at 16:9 output, worse in 9:16); instead a form shot fitted to the form container + brand outline/spotlight on the active field; less zoom elsewhere (1.4–1.8×).
- L3 (contract additions on top of reglas-ronda2.md L3):
  - actions.json/timeline events: type/select/click/focus events may carry `form_box` = bounding box of the closest form container (form, fieldset, [role=dialog], dialog, .modal/.card-like element containing ≥2 fields), viewport-clamped.
  - layout.json: camera segment kind `form` (scale, form_box); items kind `spotlight` {t0, t1, rect (active field frame_box in output px), color, dim}.
  - edit: result/toast windows (`result` events) run at 1.0× speed for ≥ compose.R2_CLEAN + margin; never sped up.
  - music: on a Lyria error containing "recitation", retry once with a neutral instrument-only prompt; log it.
- L4 (v3 run evidence): wall 30.6 min, 9.5 lost to a 120 s shell timeout that killed the pipeline silently; render 296 s for 40.7 s + 18.6 s in parallel; TUT C4 at 33.3–33.6 s; RED R2/N6 0.60 s; RED V2 "Ape", "Carg", "Telé", "Orig".
