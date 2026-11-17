# Pipeline de tutoriales con IA

Universal pipeline that turns an app + flow (or an existing video) into an edited tutorial (16:9 full + 9:16 summary).
Windows 11, no NVIDIA GPU, starting from zero. Brand assets arrive per tutorial.

## Specs

- S1 Skills: "necesito que hagas las skills" — one skill per pipeline stage plus an orchestrator, based on the agreed scheme (guion, replicar, voz, captura, edicion, musica, render, qa, orquestador `tutorial`).
- S2 Install: "instales lo necesario" — FFmpeg, Python env, HyperFrames, Whisper (CPU), Gemini SDK, starting from "solo python y node".
- S3 Env: "crea el env para poder colocar las variables que necesites" — `.env.example` + `.env` (ignored by git) with every variable the pipeline needs.
- S4 Verify: "lo verifiques y de ahi iniciamos" — a doctor/smoke check proving each tool works; API-dependent checks reported as pending until the key exists.
- S5 Brand: "logos colores y demas te paso segun el tutorial" — brand is per-tutorial input, not global.
- S6 Universal: "la idea es que sea universal" — any web flow (CRM login + create record, browser extension usage, ...), mode A (app + flow) and mode B ("pasarte el video y que lo repliques con mejor calidad").
- S7 Outputs (from ContaFácil reference): Horizontal 16:9 full video, Vertical 9:16 summary for Reels/TikTok/Stories; "La música baja sola cuando habla la voz y el audio quedó en volumen estándar de redes."

## Tasks

- [x] T1 S2 — Install FFmpeg + Python 3.12 venv + deps — inline
- [x] T2 S2 — HyperFrames local install + doctor — inline (Chrome headless ensured)
- [x] T3 S3 — `env.template`, `.gitignore`, config loader — inline (.env written by user: harness blocks .env* writes)
- [x] T4 S6 — Capture: ego-lite screenshot loop + action log — inline
- [x] T5a S6,S7 — Tools: capture, tts, edit, music, mix (verified offline on _demo) — inline
- [x] T5b S1,S7 — Tools: compose.py + render.py (HyperFrames 16:9 + 9:16) — worker — commit "feat: compose and render tutorials with HyperFrames"
- [x] T5c S4,S6 — Tools: pipeline.py, transcribe.py (mode B), qa.py, doctor.py, smoke.py — worker W1 — commit "feat: add orchestrator, replication, QA, doctor and smoke tools plus agent skills"
- [x] T6 S1,S5,S6 — Skills in .agents/skills/ (orchestrator + per stage) + README.md — worker W2 — same commit
- [x] T7 S4 — doctor exit 0 (2 warnings: .env, GEMINI_API_KEY); smoke PASS offline (238 s) — parent
- [ ] T8 S4 — Online verification (doctor --online, real TTS + Lyria on _demo) — blocked: user creates .env with GEMINI_API_KEY
- [ ] T9 S6 — Pilot tutorial on a real app chosen by the user — blocked: user provides app/flow/brand

## Log

- L1 (user, original scheme request): "Necesito crear aqui un proyecto, la idea es crear tutoriales con IA ... Transcripción: Whisper (mlx-whisper) ... Cortes y zooms: FFmpeg, con scripts de Python ... Subtítulos y armado final: HyperFrames ... Música: Gemini Lyria ... Voz: Gemini TTS, voz comercial en español latino ... La música baja sola cuando habla la voz y el audio quedó en volumen estándar de redes. Salieron 2 versiones: Horizontal 16:9, video completo (3:23) Vertical 9:16, resumen para Reels/TikTok/Stories (1:05) ... Mi idea es pasarte la app el flujo y con ego lite hagas el video lo grabes edites y me des el resultado final, otra opcion seria pasarte el video y que lo repliques con mejor calidad. ... la idea es que sea universal."
- L2 (user): "Windows sin gpu de nvidia, no tengo instalado nada, solo python y node y crea el env para poder colocar las variables que necesites no tengo nad aprevio asi qeu inicemos de cero, logos colores y demas te paso segun el tutorial, necesito que hagas las skills instales lo necesario lo verifiques y de ahi iniciamos"
- L3 (decision): Python 3.15 is too new for faster-whisper/ctranslate2 wheels → project venv on Python 3.12 via uv. Current models (Nov 2026): `gemini-3.8-flash-tts`, `lyria-3.5` / `lyria-3-clip-preview` (no free tier), HyperFrames CLI 0.9.x (needs FFmpeg + Chrome).
- L4 (evidence): ego-lite rejects `sessionId` in Page.screencastFrameAck → screencast stalls after 1 frame. Agent window is off-screen (screenX -32384) and the user's ego shows personal tabs, so FFmpeg window capture is unusable and unsafe. Decision: 3 in-flight Page.captureScreenshot loop at 1920x1080 emulated viewport → ~14 fps measured on _demo. Screenshots have no cursor → synthetic cursor drawn in composition from logged click points.
- L5 (contract): edit/<variant>/timeline.json = {variant, source:[w,h], intro, outro, screen_duration, total, steps:[{id,title,narration,start,duration,voice_start,voice_duration,events:[{type: click|hover|type|goto|press|scroll, t, t_end?, selector, box:{x,y,w,h}, point:{x,y}, secret?}]}]}. All times absolute in final video seconds (intro included). screen.mp4 starts at t=intro. audio/<variant>/mix.wav covers 0..total.
- L6 (contract, CLIs; every stage is `python tools/<stage>.py <slug>` run with .venv/Scripts/python.exe from the repo root): capture.py (needs app reachable; ego-lite), tts.py [--offline], edit.py, music.py [--offline] [--force], mix.py, compose.py, render.py [--quality draft|looks|delivery] [--variant full|short] (outputs proyectos/<slug>/out/<slug>-16x9.mp4 and -9x16.mp4; `render.snapshots(slug, variant, times)` returns PNG paths). Stage order: capture → tts → edit → music → mix → compose → render. New: pipeline.py <slug> [--from S] [--to S] [--only S] [--offline] [--quality Q]; transcribe.py <video> --slug <slug> → proyectos/<slug>/replica/{audio.wav, transcript.json, transcript.txt, frames/*.jpg, frames.json}; qa.py <slug> [--variant V] → ffprobe + loudness checks + one snapshot per step mid-point, prints PNG paths for visual review; doctor.py [--online]; smoke.py (serves demo-app on 127.0.0.1:8765 and runs pipeline _demo --offline --quality draft, then qa).
- L7 (tutorial.yaml schema): title, subtitle, app_url, viewport [w,h], language, brand {dir, primary, accent, background, text, font} (logo.png|logo.svg inside proyectos/<slug>/<brand.dir>), intro {seconds}, outro {text, seconds}, voice {model, voice, style} (optional overrides of .env), music {prompt, model}, steps[] {id, title?, narration, summary?: bool (goes into 9:16), hold_ms?, actions[] one-key maps: goto URL | click SEL | hover SEL | type {into SEL, text (literal or env:NAME), clear?} | select {in SEL, option} | press KEY | scroll PX | wait SEL | pause MS}. Selectors: raw CSS, text=Visible text (quoted = exact), xpath=... Secrets only via env:NAME in .env.
- L8 (evidence): faster-whisper 1.2.1 PyAV decode breaks on this PyAV (`metadata_errors` TypeError) → transcribe.py decodes audio.wav with wave+numpy. Recorder selectors: raw CSS (top document only), text=, xpath= (no @refs/loc=). Music: music.wav is only the offline placeholder; online runs always fetch music.mp3 and delete the placeholder. Narration in neutral Latin American Spanish (user in Ecuador).
