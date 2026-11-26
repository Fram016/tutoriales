# Perseo XML v5 tutorial

New tutorial of the "Perseo XML" Chrome extension built from the user's usage video (2026-11-25), recreated in ego-lite with sensitive data censored.
Project: `proyectos/perseo-xml-v5/`. Credentials only in `acceso.local.yaml` (names: PERSEO_XML_SRI_USER/PASSWORD, PERSEO_XML_EXT_USER/PASSWORD, PERSEO_XML_RUC).

## Specs

- S1: "Debes hacer tutorial en base a lo siguiente que te indico en el video \"C:\Users\Francisco Lopez\Videos\2026-11-25 16-57-31.mp4\" analiza el video mira el funcionamiento de la extensión \"Perseo XML\""
- S2: "luego recrea los pasos con ego lite"
- S3: "censura datos delicados"
- S5: "cuando temrinemos este peoceso del video debes auditar por aue demoro en que demoro y optimizar, no podemos demorar 3 horas o mas en un video de 2 minutos con pasos simples no es viable"
- S6: "por si acaso debes xortar el video cuand dezcatga lo extenso y mostrar cuando finaliza"
- S7: user selected "O3 Una toma por parte" — "Si falla una parte, se regraba solo esa (merge_takes ya existe). Evita perder tomas de 8 min."
- S8: user selected "O4+O5 Menos delegación + preflight" — "Comandos deterministas los corro yo directo; antes del guion comparo versión/UI de la app con el video anterior de la serie."
- S9: user selected "O6 Caché de voz por frase" — "Corregir una frase no regenera toda la narración."
- S10: demo data: "No, como el usuario indique" — "Mantengo las fechas que pidas aunque haya muchos documentos (el corte en edición sigue)."
- S4: "Si en caso necesitas hacer el video y al extensión no te deja volver a recrear el login busca como reinstalalrla o limpiar los datos"

## Tasks

- T1 (S1): transcribe + analyze usage video, write brief.md — worker (context backstop) — done: `proyectos/perseo-xml-v5/brief.md` from templates/brief.md (transcript read whole + keyframes, D-a..D-h, S1-S4 verbatim under Fuentes, sources `(video uso mm:ss)`). Resultado (F1) not imported: keyframes every ~5 s; the user's folders are in Descargas directly, not `Perseo XML\…` (D-d); Descargas rows are personal files; Emitidos shows the retracted ZIP selection (brief Preguntas abiertas).
- T2 (S1): tutorial.yaml + capture configs + lint — worker (context backstop) — done: `tutorial.yaml` (28 steps, 5 parts, Parte 1 = v4 install steps and narration; one TUT 16:9, pace fast, tempo 1.05) and `uso.yaml` (the 22 steps of Partes 2-5, actions identical to tutorial.yaml: checked with common.validate_tutorial on both + an action-by-action compare). `takes/install` = copy of v4's (diff -rq identical, 336 frames, gitignored). The merge is declared like v4 (header comment + `tools/merge_takes.py proyectos/perseo-xml-v5 …/takes/install …/takes/uso`); the schema has no `capture:` key. `.venv/Scripts/python.exe tools/lint.py perseo-xml-v5` exit 0, `OK (1 avisos)`: [P2] opening ~4.0 s, the same opening and warning as approved v4. TOOL GAP for T3: `type` has no `{in: SURFACE}` support (tools/capture/recorder.mjs `case "type"` types into ctx.page; common.SURFACE_ACTIONS has no type), so the panel login and client form (iniciar-sesion, guardar-cliente) cannot be recorded until the recorder supports it. `env:NAME` in type text is supported (capture.resolve_actions).
- T3 (S2, S3, S4): rehearse + capture in ego-lite (extension login, SRI, censor) — worker — done: rehearsal fixed the selectors (2578198: Guardar cliente `#acceso-form-cuenta button[type="submit"]`; «+ Agregar» is hidden while the vault is empty, so agregar-cliente is merged into guardar-cliente; the 1.2.1 download ends when `#boton4 b`/`#boton1 b` comes back, waited in stages of 15 of `#texto`) and showed the panel flipping tabs on every tab activation (fixed in the recorder, 74c1f51). 2 takes of `uso.yaml`: take 1 cut at descargar-emitidos (1.3 records/s vs 3/s in rehearsal; stages of 50 → 15), take 2 exit 0: 21 steps, 448.9 s, 1631 main frames + 571 panel frames in 5 openings, every target_ok true, 152 emitidos and 18 recibidos downloaded, no captcha (no manual_fallback). Censor checked on start/middle/end frames of every step (main + panel) and on zoomed frames: panel account name/avatar, login and client identification, passwords; SRI login RUC/clave; perfil name/RUC/email/phone and header name; RUC field of the emitidos/recibidos forms; emitidos clave + amounts; recibidos RUC/razón social + clave + amounts; chrome://settings/downloads user part of `\Downloads\Perseo XML\Emitidos|Recibidos` (script). Nothing uncensored. `capture/` = `merge_takes.py` of takes/install + takes/uso: 1967 frames, 27 steps (same order as tutorial.yaml), 484.8 s; `tools/lint.py perseo-xml-v5` OK (1 aviso, P2 opening). Clean state restored (client removed, panel «Sin sesión», SRI cookies cleared for srienlinea only). Downloads went to the user's current folder (D4).
- T4 (S1, S3): pipeline tts→compose, qa --pre, render, qa — worker — done (pending items listed): `out/perseo-xml-v5-tutorial.mp4`, TUT 16:9, 1920x1080, 130.1 s, 27 steps in 5 parts. Fix rounds: 2 of 3, only narration wording in tutorial.yaml with no action changes. iniciar-sesion, guardar-cliente, cambiar-emitidos, revisar-emitidos and carpeta-recibidos were rewritten so each has one instruction sentence plus an effect sentence (N1/N19/A2). Round 1's pipeline ran with lint errors (N19, TUT1); they were fixed in round 2. Final lint: OK, 1 warning (P2 opening, same as v4). Download cut (user: "cortar el video cuando descarga lo extenso y mostrar cuando finaliza"): descargar-emitidos shows 7.4 s on screen (click, SRI spinner, then the summary 152 processed / 152 downloaded / 0 errors); descargar-recibidos shows 6.3 s (18/18/0). Snapshots reviewed: qa-01 (70) and qa-02 (68 PNG). Final video: 8 frames (3/20/37/46/72/93/112/128 s); censor holds on the panel account, the login and client IDs, passwords, the SRI login RUC/clave, the header name, table claves and amounts, and the chrome://settings user path. Final MP4 qa: resolution, aac, -14.2 LUFS and -1.5 dBTP pass. Still failing, accepted by the parent: A2 (10 voice gaps of 1.1-2.0 s), R1/C1 (panel framed at 1.0254x; compose fits the whole 420x860 panel, N22 vs P3 needs a tools/ change), N18 (false positive: the `#tab-descargas` click in carpeta-emitidos is read as a download, tools/qa.py), C4 (Google start page 81% empty, same as v4), D5.pitch WARN -2.0..+3.3 st. Timings: pipeline 347.8 s + 277.9 s + 340.6 s, render 493.1 s (1 render). Lyria: 1 track generated, then reused. TTS: 3 batches.

- T5 (S5): audit where the ~3 h went (per stage and per agent) and optimize the workflow — audit 1f853bd, lint-first fix 26f630c
- T6 (S7): one take per part: capture.py records each `part` of tutorial.yaml into takes/part-<n> (or only `--part N`), and merges them into capture/ with merge_takes; a failed part is re-recorded alone — worker
- T7 (S9): TTS per-line cache: changing one narration line re-synthesizes only the changed lines (one batch of the changed lines), unchanged clips are reused — worker
- T8 (S8, S10): skills: parent runs deterministic commands directly (pipeline/render/qa/lint); preflight compares app/extension version and UI with the previous video of the series before the script; demo data as the user indicates — inline

## Decisions (parent, from video analysis + rehearsal 2026-11-25)

- D-a Reference: `proyectos/perseo-xml-v5/referencias/uso/transcript.txt` (+ frames/). The user narrates what the tutorial must show; the flow below follows it.
- D-b Extension installed in ego-lite: store build 1.2.1, id `nggkmolkfkhfdjgbclinjcojpikldbhp`. UI is a SIDE PANEL (`popup.html`), recorded as surface `panel` (url `chrome-extension://nggkmolkfkhfdjgbclinjcojpikldbhp/popup.html`, anchor `top-left` because Chrome docks the side panel on the left in the user's video, target_tab `https://srienlinea.sri.gob.ec/*`, hide `#publicidad-perseo` (N23 ads carousel "Conoce Perseo")). Size: tall narrow panel, e.g. [420, 900], dpr 2 (check compose limits).
- D-c Takes (I3): `takes/install` = copy/reuse of `proyectos/perseo-xml-v4/takes/install` (same store listing + id; I1, I2 simulated install). `takes/uso` = new live take (`uso.yaml`). `takes/resultado` = user's reference video segments imported with `tools/import_video_take.py` (F1-F3), only if the folder segment is usable; else end on the recibidos summary.
- D-d Live take flow (`uso.yaml`, starts on `https://srienlinea.sri.gob.ec/sri-en-linea/inicio/NAT`, SRI logged out, extension logged out, client "Prueba" removed beforehand):
  1. open panel → `#tab-claves`; mention "Crear cuenta" (`#acceso-seg-registro`) only by narration/hover (no account is created).
  2. Iniciar sesión: `#acceso-login-identificacion` (env:PERSEO_XML_EXT_USER), `#acceso-login-clave` (env:PERSEO_XML_EXT_PASSWORD), submit `#acceso-login-accion`; result `#acceso-abierta`.
  3. Agregar cliente: `+ Agregar` button, fields `#acceso-identificacion` (env:PERSEO_XML_SRI_USER), `#acceso-alias` = "Prueba", `#acceso-clave` (env:PERSEO_XML_SRI_PASSWORD), submit = button text "Guardar cliente" inside `#acceso-form-cuenta` (no id). Explain: vault (bóveda) of SRI credentials to reuse.
  4. Carpeta Emitidos: `#tab-descargas` → `#configure-folder` → follow tab chrome://settings/downloads → press_visual `#changeDownloadsPath` + show_download_dir `%USERPROFILE%\Downloads\Perseo XML\Emitidos` (D4 display-only, like v4) → back main.
  5. `#tab-claves` → `#acceso-ir-sri` "Acceder al SRI" (updates the main SRI tab → Keycloak login). The panel auto-switches to Descargas on SRI tabs: click `#tab-claves` again, click `label.acceso-opcion` (the radio input itself is hidden), click `#acceso-llenar` "Llenar en el SRI" → message "Datos llenados. Revisa y pulsa Ingresar en el SRI."; close panel; click `#kc-login` on main → perfil. Verified in rehearsal (no captcha).
  6. Emitidos: menu as v4 (FACTURACIÓN ELECTRÓNICA → Producción → Consultas → Comprobantes electrónicos emitidos), fecha `21/11/2026` (user: "Para el ejemplo vas a colocar la fecha 21"), Consultar; panel → `#boton4` "XML Desde el RIDE"; D2 explain RIDE→XML transformation; show stats `#texto` (procesados), `#texto_correctos`, `#texto_error`, and expand `Detalle de registros` (`<details>`).
  7. Carpeta Recibidos (same as 4 with `...\Recibidos`).
  8. Recibidos: Anterior → Comprobantes electrónicos recibidos, año 2026, mes Noviembre, día 24 (user: "voy a consultar desde 24"), Consultar (reCAPTCHA risk: manual_fallback as v4), panel `#boton1` "XML Para importar", stats.
- D-e Censor (N25, one criterion: blur everywhere): env:PERSEO_XML_RUC, PERSEO_XML_NOMBRE, PERSEO_XML_EMAIL, PERSEO_XML_TELEFONO, PERSEO_XML_EXT_USER, the Contafacil account name shown in `#acceso-usuario` and `#acceso-avatar` (selectors), `#acceso-login-identificacion`, `#acceso-identificacion`, client detail `.acceso-opcion-detalle`, SRI header taxpayer name, emitidos/recibidos table columns as v4, panel `#registros-container` entries if they show claves de acceso, Windows user path regex. Password fields show dots (still blur them).
- D-f Brand/voice/music/pronunciation/glossary: same as v4 (primary #ca4100, voice es-419-commercial-11 energetic seller style, RIDE→"ri-de", one TTS batch). Video: one TUT 16:9 `steps: all`, pace fast, tempo 1.05, no max_seconds (P1 revisada 2). Parts: 1 Instalar, 2 Iniciar sesión y cliente, 3 Carpeta y SRI, 4 Emitidos, 5 Recibidos, (6 Resultado if imported).
- D-g Labels must match live UI: "Claves SRI", "Descargas", "Iniciar sesión", "Crear cuenta", "+ Agregar", "Guardar cliente", "Acceder al SRI", "Llenar en el SRI", "Carpeta de descargas", "XML Desde el RIDE", "XML Para importar", "Detalle de registros", SRI "Ingresar".
- D-h recorder fix: surfaces neutralize `window.close()` (extension closes its panel after filling) — commit 78945ae.

## Log

- L1: Debes hacer tutorial en base a lo siguiente que te indico en el video "C:\Users\Francisco Lopez\Videos\2026-11-25 16-57-31.mp4" analiza el video mira el funcionamiento de la extensión "Perseo XML" luego recrea los pasos con ego lite censura datos delicados. Tus datos para esta prueba son SRI: <url login SRI> RUC <redacted> Contraseña: <redacted>. Credenciales para extensión Usuario: <redacted> Contraseña: <redacted>. Si en caso necesitas hacer el video y al extensión no te deja volver a recrear el login busca como reinstalalrla o limpiar los datos

## Audit T5: where the time went (measured: file mtimes, commits, subagent stats)

Total: ~17:03 (request) → 19:55 (MP4) = ~2 h 52 min for a 2:10 video.

| Phase | Clock | Minutes | Machine time inside | Cause of the rest |
|---|---|---|---|---|
| Transcribe usage video (6:15) | 17:03–17:13 | 10 | Whisper CPU 4.8 min | none (ran in background) |
| Analysis + live rehearsal + window.close fix | 17:13–17:34 | 21 | ~1 | extension changed (1.2.1: side panel, login, vault) → new tool gap |
| brief + tutorial.yaml + uso.yaml (worker) | 17:34–17:44 | 10 | 0 | ok |
| type-in-surface fix + rehearsal + onActivated fix | 17:44–18:08 | 24 | ~2 | two more recorder gaps found one at a time by rehearsal |
| Takes (2) + censor check + merge | 18:08–18:27 | 19 | take 7.5 min ×2 (≈4 min of each is waiting on 152 downloads) | take 1 lost to a download-speed wait |
| Pipeline + pre-QA + render (worker) | 18:27–19:55 | 88 | 3 pipeline runs ≈ 16 min, qa --pre 3 min, render ≈ 9 min | ~60 min of agent review: 1126 tool calls, 68 snapshots opened per round, 1 wasted run (lint skipped by --from tts) |

Findings:
- F1 The QA loop is the biggest sink (~60 of 172 min): the agent opens every snapshot one by one and iterates on rules that cannot pass without tool changes (A2, R1/C1 panel, N18 false positive).
- F2 One-time tooling gaps of the new extension UI (side panel) cost ~45 min; reusable now (78945ae, d995e5b, 74c1f51).
- F3 Real waiting inside takes: 152 emitidos download ≈ 2 min per take; demo data volume drives take time.
- F4 Bug: `pipeline --from tts` skipped lint and ran 5 min on a broken yaml → fixed (26f630c).
- F5 Chained delegation (explore → worker → worker → worker) adds startup + re-reading of skills/rules per worker.

Optimizations (proposed, ordered by impact):
- O1 qa --pre writes ONE contact sheet per part (not 68 PNGs); the agent reviews sheets; hard cap 2 rounds and 20 min; known tool-limited rules (list in the skill) are reported, never iterated.
- O2 Small demo data: choose dates/filters giving ~10–20 documents so downloads take seconds.
- O3 Takes per part (one take per Parte) so a failure re-records only that part; merge_takes already exists.
- O4 Parent runs pipeline/render commands directly (no worker for deterministic commands); workers only for writing yaml.
- O5 Pre-flight: compare extension version/UI with the previous video of the series before writing the script (catches F2 early).
- O6 Narration fixes re-synthesize only changed lines (cache per line) instead of the whole one-batch read.
Target: a 2-minute tutorial of an already-known app in ≤ 30–40 min.
- L2 (user, ronda 9): ok ahors tenemos otro tema aue tesolver el ultimo video mo esta claro. 1. debes indicar como se ve el formulario de tegistrarse cuando muestras como hacer login, debes decir, "si eres usuario del sistema contafacil ingresa con tu contraseña y clave en caso de no tener credenciales llena el formulario de registro para hacer uso de la extemsion" cuando explicas como cambiar la carpeta de descargas debes explicar por que por ejemplo "vamos a cambiar la carpeta de descargas oara qur todos los xml que descarguemos del sri vayan a una carpeta especifica" o algo similar, en vez de decir clic en change deberias hablar en español y un poco descriptivo "se debe dar clic en cambiar o change para seleccionar la carpeta de adecuada", cuando seleccionas laa fechas del sri, no debes decir la fecha que deben escoger si no "seleccionan fecha" o algo similar, lo que te indique es para tu ejercicio no parte del tutorial, adicional para tutoriales la voz esta bien pero debe ser mas energica un poco mas animada. aprnas termines lo que estas haciendo corrige el video con las nuevas directrices de ia y comprobemos la demora
- L3 T9 (S11 = L2): rules G1-G4 + D6 revisada (ca8bce1); tutorial.yaml/uso.yaml: new step `registro` (sign-up form shown), narration per G1-G4, more energetic style. Needs a new uso take + pipeline + render; measure the total time (target ≤ 30-40 min).
