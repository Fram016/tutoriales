# Reglas de video v2 (tipos de video, cámara, overlays, texto, idioma, audio, vertical real)

Apply the user's rulebook to the pipeline, then re-run a fresh agent from scratch to produce the Nexo CRM video under the new rules.
Normative source (verbatim): reglas/reglas-video.md — rule IDs E1-E3, C1-C6, O1-O3, R1-R3, T1-T3, L1-L4, A1-A2, V1-V5, TUT1-7, RED1-5, PRO1-6, NOV1-5.

## Specs

- S1 "Parte 1: Errores detectados" — the 26 errors in reglas/reglas-video.md §Parte 1 must not reappear.
- S2 "Parte 2: Reglas" — rules E, C, O, R, T, L, A, V verbatim in reglas/reglas-video.md §Parte 2, including "Validación automática sugerida".
- S3 "Parte 3: Reglas por tipo de video" — "Antes de generar, la IA debe recibir o decidir el tipo de video, porque ese dato define la estructura, la duración, el ritmo y el formato." TUT/RED/PRO/NOV rules and the decision table verbatim in reglas/reglas-video.md §Parte 3. "El horizontal debe generarse como TUT." "El vertical debe generarse como RED, no como TUT recortado."
- S4 "primero manda a corregir las reglas que tenemos actualmente y luego reenvia otro subagente desde cero a hacer para ver como quedaria con la actualizacion de reglas."

## Tasks

- [x] T1 S2,S3 — Timing & schema — worker WB — commit 8d26c48
- [x] T2 S1,S2,S3 — Composition — worker WA — commit 196431b
- [x] T3 S1,S2,S3 — Validation: lint.py + qa.py + smoke — worker WC — commit fd426a7
- [x] T4 S1,S2,S3 — Skills, README, brief, _demo v2, demo apps in tú — worker WD — commit 7f858f9
- [x] T5 S1-S3 — Integration: 152 unit tests OK + offline smoke PASS (fix worker: blank detector, click lag, screen_at cuts, place_voices) — commits 8d26c48/196431b
- [ ] T6 S4 — Fresh subagent from scratch produces Nexo CRM TUT 16:9 + RED 9:16 — worker

## Log

- L1 (user, verbatim, full text in reglas/reglas-video.md): "Ok vamos a hacer algo porque, te mando correcciones y reglas nuevas, primero manda a corregir las reglas que tenemos actualmente y luego reenvia otro subagente desde cero  a hacer para ver como quedaria con la actualizacion de reglas. Parte 1: Errores detectados ... Parte 2: Reglas ... Parte 3: Reglas por tipo de video ..."
- L2 (contract: tutorial.yaml v2). Breaking change; `intro`, `outro`, `summary` are removed.
  ```yaml
  title: "Cómo crear un contacto en Nexo CRM"
  product: "Nexo CRM"            # T3: never split across lines (render with non-breaking spaces)
  app_url: http://127.0.0.1:8766/
  viewport: [1920, 1080]
  language: es-EC
  device: desktop                # L2: desktop -> "hacer clic"; mobile -> "tocar"
  brand: {dir, primary, accent, background, text, font}
  glossary:                      # L3: preferred term -> forbidden synonyms
    contacto: [cliente, prospecto, registro]
  music: {prompt}                # optional global default; per-video override below
  steps:                         # E2: ONE list; one step = one action with a visible result
    - id: nuevo
      title: "Abre el formulario"  # optional, shown next to "Paso N"
      chapter: 1                   # optional (E3/TUT3), only for videos > ~5 min
      narration: "..."             # default narration (TUT)
      hold_ms: 600                 # optional
      actions:                     # one-key maps
        - goto: URL | click: SEL | hover: SEL | press: KEY | scroll: PX | wait: SEL | pause: MS
        - type: {into: SEL, text: "literal or env:NAME", clear?: bool}
        - select: {in: SEL, option: VALUE}
        - focus: SEL               # NEW: camera target without cursor (read something, C1 detail)
        - result: SEL              # NEW: confirmation/outcome element (toast, saved row) -> R1 detail zoom, R2 >=800 ms clean
        - highlight: SEL           # NEW: new element -> R3 accent outline/pulse + detail zoom
  videos:                        # S3: every video declares its type
    - id: tutorial               # outputs proyectos/<slug>/out/<slug>-<id>.mp4
      type: TUT                  # TUT | RED | PRO | NOV
      format: "16:9"             # "16:9" | "9:16"
      steps: all                 # "all" or ordered subset of step ids (order preserved; E2 numbering = original index+1)
      opening: {narration: "En este video aprendes a crear un contacto en Nexo CRM.", text: "Aprende a crear un contacto"}
      requirements: {narration: "...", text: "..."}   # optional, TUT only, <= 5 s
      closing: {narration: "En el siguiente video aprendes a registrar una oportunidad.", text: "Siguiente: registrar una oportunidad"}
      narration: {}              # optional per-step override {step_id: text} (RED/PRO/NOV wording)
      music: {prompt: "...", none: false}
    - id: redes
      type: RED
      format: "9:16"
      steps: [nuevo, datos, guardar]
      opening: {narration: "¿Conociste un posible contacto en una feria?", text: "¿Conociste a alguien en una feria?"}
      closing: {narration: "Mira el tutorial completo.", text: "Mira el tutorial completo"}
      narration: {nuevo: "...", datos: "...", guardar: "..."}
  ```
  Validation (common.load_tutorial): required title, steps, videos; unique ids; videos[].steps ⊆ steps; type/format enums; opening and closing required for every video (E1).
- L3 (contract: per-video artifacts). For each video id V:
  - audio/voice/V/{opening,requirements?,<step>,closing}.wav + audio/voice/V/durations.json {name: seconds}; tts cache by text hash.
  - edit/V/screen.mp4 (source-resolution 1920x1080, 30 fps; plays from timeline.screen_start to screen_end) + edit/V/timeline.json (L4).
  - audio/V/music.mp3 (or none) and audio/V/mix.wav covering 0..total (A1 −14 LUFS, true peak < −1 dBTP).
  - hf-V/ HyperFrames project + hf-V/layout.json (L5); out/<slug>-V.mp4.
  - Stage functions keep the same names: capture(slug), tts(slug, offline), edit(slug), music(slug, offline, force), mix(slug), compose(slug), render(slug, quality, video=None), render.snapshots(slug, video, times); lint.lint(slug) -> list[str] warnings, raises PipelineError on errors. pipeline stages: lint, capture, tts, edit, music, mix, compose, render.
- L4 (contract: edit/V/timeline.json v2; all times absolute seconds in the final video).
  ```json
  {"video":"tutorial","type":"TUT","format":"16:9","source":[1920,1080],"output":[1920,1080],"total":0,
   "product":"Nexo CRM","title":"...",
   "opening":{"start":0,"duration":3.0,"text":"...","narration":"...","voice_start":0.2,"voice_duration":2.6},
   "requirements":null,
   "closing":{"start":0,"duration":2.5,"text":"...","narration":"...","voice_start":0,"voice_duration":2.2},
   "screen_start":3.0,"screen_end":0,
   "steps":[{"id":"nuevo","number":2,"chapter":null,"title":"...","narration":"...","start":0,"duration":0,
             "voice_start":0,"voice_duration":0,
             "events":[{"type":"click|hover|type|select|focus|result|highlight|goto|press|scroll","t":0,"t_end":0,
                        "selector":"...","box":{"x":0,"y":0,"w":0,"h":0},"point":{"x":0,"y":0},"chars":0,"secret":false}]}]}
  ```
  Timing rules owned by edit: piecewise time-warp per step; typing retimed to 13.5 chars/s, and when chars > 30 the chars after the first 15 run ×3 (C6); near-blank capture frames (loads) are cut (C4); waits/idle spans sped up (≤3× outside typing; RED3 pace for RED); TUT: ≥1.5 s hold after each step's result/highlight event (TUT4); result events visible ≥0.8 s (R2); a step lasts max(warped actions, voice + lead + tail) and action spans are compressed so voice gaps stay ≤1.0 s when possible (A2); closing card ≤2.5 s (A2); opening ≤3 s (E1; RED hook 1–2 s).
- L5 (contract: hf-V/layout.json written by compose, read by qa).
  ```json
  {"output":[1920,1080],"viewport":[x,y,w,h],"cursor_px":48,"font_px":44,
   "camera":[{"t0":0,"t1":0,"scale":1.0,"kind":"context|detail|move"}],
   "items":[{"kind":"caption|chip|title|card|cursor|active|result|highlight","t0":0,"t1":0,"rect":[x,y,w,h],
             "text":"...","lines":["..."],"step":"id"}]}
  ```
  Rects in output pixels; `active` = the element of the current event mapped through the camera; `cursor` sampled at each event.
- L6 (design decisions for compose): cursor drawn at constant ~48 px in OUTPUT pixels regardless of zoom, soft halo on click (C5). Camera: detail 1.8–2.5× for every type/click/select/focus/result/highlight event, context 1.0× ≤1.0 s, 400–600 ms ease-in-out pans/zooms, never cross-fades; render with `--page-motion-blur off` (suspected cause of C2 ghosting); target fully in frame ≥500 ms before the click (C3). Step chip and captions share ONE style in every video (O3), chip opacity 100 % and text contrast ≥4.5:1 (O1); chip never over logo/menu/header (O1): place it attached to the caption block or in a reserved zone, never at a fixed corner over UI. Captions avoid active/result/mentioned fields by moving the framing (O2). 9:16 = full-bleed real crop of the 1920x1080 source following the active element (base scale ≈1.78, detail up to 2.5), UI ≥70 % of the height, nothing important in the top 15 % / bottom 20 % (V1-V4); title only in the opening ≤3 s (V3). Captions: ≤2 lines × 42 chars, ≥1.2 s, no line ending in article/preposition/conjunction, never across steps (T1), font ≥44 px at 1080 output (T2), product name unbreakable (T3). PRO/NOV: no step chip (PRO4). TUT long videos: "Parte N · Paso M" (E3/TUT3).
- L7 (finding, rule conflict for the user): R2 (zoom to the confirmation toast ≥800 ms) vs C4 (no frame > 70 % empty) when the toast sits alone in an empty corner. _demo resolved it by using the highlighted new row as the result (R1/R3) instead of the toast. Pending user decision.
- L8 (T6 instructions to the fresh agent, as a user would type them): "Nexo CRM es un CRM de ventas. Se ingresa con correo y contraseña. En el menú lateral está Contactos; ahí se ve la lista y el botón '+ Nuevo contacto'. El formulario pide Nombre, Apellido y Correo como obligatorios; también Empresa, Cargo, Teléfono, Etapa (Prospecto, Negociación, Cliente), Origen y Notas. Al guardar vuelve a la lista, el contacto aparece primero y resaltado, y sale un aviso verde. Hay un buscador arriba de la lista. Quiero el tutorial completo en horizontal y un video corto para redes en vertical sobre cómo crear un contacto. Está dirigido a vendedores nuevos que registran su primer posible cliente."
