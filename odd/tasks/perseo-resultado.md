# Ronda 8: Perseo XML v4 — resultado final con el video del usuario

## Specs

- S1 "ahi te dejo un video de algo que debes añadir al final como resultado final" (F1).
- S2 "yo estoy mostrando como voy a descargas la carpeta Perse Xml, voy a mostrar los emitidos, regreso y muestro los recibidos" (F1 flow).
- S3 "censura la información delicada de la carpeta de descargas" (F3).
- S4 "simplemente muestra cómo se ve el resultado final" (short part, same voice D5).

## Tasks

- [ ] T1 S1-S3 — tools/import_video_take.py: user video → censored take (frames + frames.json + actions.json from a step spec) — worker
- [ ] T2 S1-S4 — perseo-xml-v4: new final part "Resultado final" merged after the current takes; one TTS read; render; QA; frame review (censor!) — worker
- [ ] T3 — Delivery — parent

## Log

- L1 (user, verbatim in reglas/reglas-video.md §Parte 10). Source: C:\Users\Francisco Lopez\Videos\2026-11-19 09-39-50.mp4 (1920x1080, 23.9 s, Windows File Explorer dark mode; transcript in proyectos/perseo-xml-v4/referencias/resultado/).
- L2 (decisions): no new recording; the user video is imported as a take (F2); its audio is dropped; the whole narration (install + v3 + final) is regenerated in one read (D5, cost: one Gemini TTS request).
