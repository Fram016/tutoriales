# Perseo XML v5 tutorial

New tutorial of the "Perseo XML" Chrome extension built from the user's usage video (2026-11-25), recreated in ego-lite with sensitive data censored.
Project: `proyectos/perseo-xml-v5/`. Credentials only in `acceso.local.yaml` (names: PERSEO_XML_SRI_USER/PASSWORD, PERSEO_XML_EXT_USER/PASSWORD, PERSEO_XML_RUC).

## Specs

- S1: "Debes hacer tutorial en base a lo siguiente que te indico en el video \"C:\Users\Francisco Lopez\Videos\2026-11-25 16-57-31.mp4\" analiza el video mira el funcionamiento de la extensión \"Perseo XML\""
- S2: "luego recrea los pasos con ego lite"
- S3: "censura datos delicados"
- S4: "Si en caso necesitas hacer el video y al extensión no te deja volver a recrear el login busca como reinstalalrla o limpiar los datos"

## Tasks

- T1 (S1): transcribe + analyze usage video, write brief.md — worker (context backstop) — done: `proyectos/perseo-xml-v5/brief.md` from templates/brief.md (transcript read whole + keyframes, D-a..D-h, S1-S4 verbatim under Fuentes, sources `(video uso mm:ss)`). Resultado (F1) not imported: keyframes every ~5 s; the user's folders are in Descargas directly, not `Perseo XML\…` (D-d); Descargas rows are personal files; Emitidos shows the retracted ZIP selection (brief Preguntas abiertas).
- T2 (S1): tutorial.yaml + capture configs + lint — worker (context backstop) — done: `tutorial.yaml` (28 steps, 5 parts, Parte 1 = v4 install steps and narration; one TUT 16:9, pace fast, tempo 1.05) and `uso.yaml` (the 22 steps of Partes 2-5, actions identical to tutorial.yaml: checked with common.validate_tutorial on both + an action-by-action compare). `takes/install` = copy of v4's (diff -rq identical, 336 frames, gitignored). The merge is declared like v4 (header comment + `tools/merge_takes.py proyectos/perseo-xml-v5 …/takes/install …/takes/uso`); the schema has no `capture:` key. `.venv/Scripts/python.exe tools/lint.py perseo-xml-v5` exit 0, `OK (1 avisos)`: [P2] opening ~4.0 s, the same opening and warning as approved v4. TOOL GAP for T3: `type` has no `{in: SURFACE}` support (tools/capture/recorder.mjs `case "type"` types into ctx.page; common.SURFACE_ACTIONS has no type), so the panel login and client form (iniciar-sesion, guardar-cliente) cannot be recorded until the recorder supports it. `env:NAME` in type text is supported (capture.resolve_actions).
- T3 (S2, S3, S4): rehearse + capture in ego-lite (extension login, SRI, censor) — inline
- T4 (S1, S3): pipeline tts→compose, qa --pre, render, qa — inline

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
