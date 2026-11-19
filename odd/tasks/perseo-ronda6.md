# Ronda 6: Perseo XML v3 — diálogos en secuencia, carpeta configurada de verdad, RIDE pronunciado "ri de"

## Specs

- S1 "Haz mas coherente los dialogos y por ejemplo debes mencionar explicitamente, Ingresa a la plataforma del SRI, luego ingresa a... y sigue con frases coherentes" (D1).
- S2 "no mostraste tambien como configurar correctamente la carpeta de descargas" (D4).
- S3 "no importa que consumas un poco mas de tiuempo siempre que sea claro solo no llegues al minuto" (P1 revisada: < 60 s).
- S4 "explica que por ejemplo en emitidos transforma los RIDE a XML" (D2).
- S5 "RIDE se pronuncia RI DE no raid" (D3).

## Tasks

- [ ] T1 S2,S5 — Tools: tts `pronunciation` map; recorder `set_download_dir` (chrome://settings via chrome.settingsPrivate) + restore at take end; second follow/back allowed — worker
- [ ] T2 S1-S5 — New project perseo-xml-v3: script, recapture (SRI login helper, captcha manual fallback), pipeline, QA, render — worker
- [ ] T3 — Frame review and delivery — parent

## Log

- L1 (user, verbatim in reglas/reglas-video.md §Parte 8).
- L2 (decision): the native Windows folder picker cannot be captured; the video shows the click on "Change" and the settings page with the new folder (real pref change via chrome.settingsPrivate.setPref('download.default_directory', ...) on the followed chrome://settings tab), one folder per type: %USERPROFILE%\Downloads\Perseo XML\Emitidos and ...\Recibidos (created by the take). The original download folder is read before and restored after the take (also on failure). Path censor keeps blurring "C:\Users\<user>" while the folder names stay visible.
- L3 (user): "Algo adicional mantene un solo tono de voz hubieron cambios de tono de voz, eso añade como orden" → rule D5 (one voice tone), added to T1/T2.
- L4 (blocker + decision): Chromium rejects settingsPrivate.setPref for download.default_directory (only the native picker can change it). Parent chose option B: display-only `show_download_dir` (press_visual on Change + new folder text shown in the settings row, censor on the user name); downloads stay in the user's current folder; no restore needed. Rationale: no UI automation of native dialogs on the user desktop, no raw CDP download dir; the video shows the real result the user gets after picking a folder.
