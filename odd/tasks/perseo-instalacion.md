# Ronda 7: Perseo XML v4 — instalación desde la Chrome Web Store + tutorial v3

## Specs

- S1 "simula la instalacion del plugin ... toca indicar como instalar tambien" (I1, I2).
- S2 "Que necesito que enseñes, a buscar la tienda de extensiones y como se instala despues el tutorial que ya tenemos" (I1; v3 content kept after the install part).
- S3 "no apliques restricciones de tiempo" (no max_seconds).
- S4 "solo manten el tono coherente el estilo de voz y habla de igual forma" (D5: one read for the whole video; same voice, style, tempo, pronunciation as v3).

## Tasks

- [x] T1 S1,S2 — Tools: recorder display-only `show_text` + `simulate_dialog` (in-page Chrome-like confirm dialog); `tools/merge_takes.py` (merge capture dirs with time offsets, unique frame names, surfaces) — worker
- [x] T2 S1,S2 — Install take (no SRI): store search → Perseo XML listing → press_visual "Agregar a Chrome" (label shown via show_text) → simulated confirm dialog → press_visual "Agregar extensión" → installed state — worker
- [x] T3 S2-S4 — Project perseo-xml-v4: merged capture (install take + perseo-xml-v3 capture), yaml with Parte 1 Instalar, Parte 2 Configurar carpeta, Parte 3 Emitidos, Parte 4 Recibidos; one TTS read; render; QA; frame review — worker
- [ ] T4 — Delivery — parent

## Log

- L1 (user, verbatim in reglas/reglas-video.md §Parte 9).
- L2 (decisions): no real install (the store listing ID is nggkmolkfkhfdjgbclinjcojpikldbhp; ego shows "Agregar a ego"; the native confirm dialog is not capturable) → simulate in-page (I2). No SRI recapture: reuse proyectos/perseo-xml-v3/capture (valid take, censor verified) merged after the install take (I3). Google search for the store is optional: use it if it does not trigger a "tráfico inusual" page, otherwise open chromewebstore.google.com and use its own search box.
- L3 (result): perseo-xml-v4 delivered, 77.4 s, install part from Google → store → listing → simulated "Agregar a Chrome"/dialog/"Quitar de Chrome"; no "Agregar a ego" frames (checked 16.5–17.1 s); qa FAIL C4 (sparse pages), A2 (gaps under music), C7 at 12.9 s (store loading); D5 pitch WARN −3.1..+3.9 st, loudness 0.0 LU.
