# Worklog: nexo-crm-contacto-v4 (T6 / S4, agente nuevo desde cero)

Inicio: 01:59:41 · Fin: 02:18 (hora local, 2026-11-18). No se leyó ni reutilizó nada de `nexo-crm-contacto`, `-v2` ni `-v3`.
Instrucciones del usuario: odd/tasks/reglas-video.md L8 (copiadas textualmente en brief.md › Fuentes).

## 1. `tutorial` (entrada)

- Qué dice: preflight con doctor; slug; brief antes que el guion; por defecto TUT 16:9 + RED 9:16 desde una sola lista de pasos; FAST WORKFLOW (≤ 12 min); comandos largos nunca bajo un timeout corto de shell.
- Qué hice: leí los 8 skills, reglas-ronda3.md hasta `## Log` y reglas-video.md completo (Partes 1–5). `ego-browser skill` → guía v2.2.1 (367 líneas, completa).
- `.venv/Scripts/python.exe tools/doctor.py --online` → exit 0, 8 s, 0 fallas (TTS gemini-3.8-flash-tts/Kore OK). App en http://127.0.0.1:8766/ → HTTP 200.
- Tipo: lo dio el usuario (“tutorial completo en horizontal” + “video corto para redes en vertical”) → `tutorial` TUT 16:9 `steps: all` + `redes` RED 9:16.
- Fricción: ninguna.

## 2. `tutorial-brief`

- Qué dice: completar Objetivo, Audiencia, Tipo, Dispositivo, Glosario, Paleta extraída de la app (N5), Historia (N4), Destino del CTA (N8), Flujo, Datos de la serie; verificar el login en ensayo; credenciales solo por nombre.
- Qué hice: leí `demo-apps/nexo-crm/index.html` (solo lectura). Paleta: `--brand #7c3aed` (botón primario), menú lateral `#1f1235` (oscuro → background/surface), `--brand-d #5b21b6`, fuente Segoe UI. Glosario: contacto (no: cliente, registro); Prospecto/Negociación/Cliente solo como opciones de Etapa. Historia: Sofía Vera, conocida en una feria → Origen “Feria”, nota “Conocida en la feria de Quito” (29 car.). CTA: “en el enlace de nuestro perfil” (propuesto; pregunta abierta). Sin logo (pregunta abierta).
- Ensayo de login + flujo completo en ego-browser (espacio 42, `round-01.mjs`, 7,4 s, exit 0): credenciales leídas dentro del script desde `acceso.local.yaml` (nombres `NEXO_CRM_CONTACTO_V4_USER` / `NEXO_CRM_CONTACTO_V4_PASSWORD`; valores nunca impresos). Resultado: login OK sin 2FA; los 9 campos tienen el mismo contenedor `form#contact-form`; aviso `#toast` visible a 1,2 s; primera fila con clase `new` “Sofía Vera”; paleta confirmada con getComputedStyle.
- Fricción: el código fuente de la app contiene las credenciales demo en claro; no se copiaron a ningún archivo.

## 3. `tutorial-guion`

- Qué dice: esquema v2, un paso = una acción con resultado (formulario = un paso, N10–N12 sin `focus:` por campo), `result:`/`highlight:` tras `wait:`, presupuestos de palabras, `omit` para RED, lint sin errores ni avisos.
- Qué hice: 5 pasos (login, contactos, nuevo, datos, guardar). RED = [nuevo, datos, guardar] con `omit: [#c-empresa, #c-telefono, #c-etapa]`. Música por tipo sin géneros ni artistas.
- `tools/lint.py` 1.ª vez → exit 1: `[TUT1] opening tiene que decir el objetivo`, avisos RED1 (gancho 0,8 s) y RED2 (~14 s). Corregí: apertura “Aprendes a registrar contactos.”, título “Tu primer contacto en Nexo CRM” (otra idea, N2), gancho “¿Conociste a alguien?”, narraciones RED más largas. 2.ª vez → `OK (0 avisos)`.
- Fricción: mi primer intento de reemplazo con un heredoc doble no se aplicó (lo ejecutó un `python` vacío del sistema); lo rehice con la herramienta de edición. Sin costo.

## 4. `tutorial-ensayo-captura`

- Qué dice: una toma para todos los videos; selectores CSS crudos; `form_box` por campo; capture con timeout ≥ 900 s.
- `.venv/Scripts/python.exe tools/capture.py nexo-crm-contacto-v4` (timeout 900 s) → exit 0, 53 s, 690 cuadros (~13,3 fps), 5 pasos, `failure: None`, viewport 1920x1080. `form_box` {x 272, y 150, w 880, h 592} en los 8 eventos del formulario.
- Fricción (herramienta): el recorder también asigna `form_box` a clics fuera de formularios: `#nav-contactos` → todo el viewport (1920x1080) y `#btn-nuevo-contacto` → {240,68,1680,387}. Probablemente `formBox()` cuenta campos ocultos (`fields >= 2`) del `#app`. Compose los convierte en “planos de formulario” a 1,0× → C1.context FAIL en TUT (ver QA).

## 5. `tutorial-voz` + `tutorial-edicion` + `tutorial-render` (FAST WORKFLOW)

### Pasada 1 — `tools/pipeline.py nexo-crm-contacto-v4 --from tts --to compose` (timeout 1200 s) → exit 0, 148 s

| etapa | s |
| --- | --- |
| tts | 47,0 (13 clips; TUT 34,5 s de voz, RED 11,9 s) |
| edit | 16,5 (TUT 39,5 s, RED 19,2 s; avisos A2 en ambos) |
| music | 43,5 (Lyria lyria-3.5, 1 pista por video, sin bloqueo “recitation”) |
| mix | 4,2 (TUT −14,0 LUFS / −1,6 dBTP; RED −14,1 / −1,4) |
| compose | 35,9 (check OK, 21 y 13 avisos de hyperframes) |

`tools/qa.py --pre` (21 s) → exit 1: TUT A2 (2 silencios de 1,1 s), TUT C1.context (10,98–12,48 s a 1×), RED A2 (1,7/2,3/2,3 s), RED N1 (datos: instrucción 1,0 s después de la acción), RED N12 (formulario 1112 px > 1080). Revisé las 33 capturas una por una.

### Ronda de corrección 1 (texto → `--from tts`)
- TUT: login + “Se abre el inicio.”; contactos “Haz clic en Contactos. Está en el menú lateral, y aquí ves tu lista.”; requisitos “Necesitas tu correo y contraseña de Nexo CRM.”
- RED: nuevo, datos y guardar con una frase de resultado más.
- lint OK (0 avisos). Pipeline → exit 0, 72 s (tts 20,6, edit 16,8, music 0,2 “reutilizo”, mix 4,9, compose 28,3). qa --pre (21 s): resuelve TUT A2 y RED N1; quedan RED A2 (1,4 s ×2), TUT C1.context (1,4 s), RED N12.

### Ronda de corrección 2 (solo RED)
- RED datos: “Completa nombre, apellido y correo. Elige origen Feria y anota en Notas dónde la conociste.”
- `pipeline.py … --from tts --to compose --video redes` → exit 0, 32 s. qa --pre (22 s): RED A2 resuelto. Quedan TUT C1.context y RED N12 (no se corrigen desde tutorial.yaml; ver Fricción). Revisé las 33 capturas de qa-03 (hojas de contacto).
- Rondas usadas: 2 de 3. No se usó la 3.ª: lo que falla está en tools/compose/recorder (fuera del alcance).

### Render único — `tools/pipeline.py nexo-crm-contacto-v4 --only render --quality delivery` (timeout 1800 s)
- exit 0, 152 s (02:12:00–02:14:32), ambos en paralelo, 25 fps, 2 workers cada uno. RED 117 s, TUT 152 s. Renders usados: 1 (sin re-renders).
- `tools/qa.py nexo-crm-contacto-v4` (25 s) → exit 1 (ver tablas).

### Fricción
- C10/C4 tras “Guardar contacto” (defecto de compose, S1a no resuelto): la app cambia de pantalla en el mismo instante del clic; compose mantiene el encuadre del formulario y el recuadro del botón sobre la lista nueva (TUT 33,9 s; RED 15,9–16,3 s, además con un paneo de 0,5 s), y en TUT hay un plano a 1× de la lista con 72 % vacío a 34,32 s antes del aviso.
- N12 estructural: en 9:16 sin franjas (N9, V1 ≥ 70 %) la escala mínima es 1365/1080 ≈ 1,26×; el formulario de la app mide 880 px → 1112 px > 1080. Solo se recorta el padding del formulario (−8/−16 px); ningún campo ni etiqueta queda cortado.
- La fila resaltada (≈ 1600 px de ancho) no cabe a 1,4× (mínimo de detalle de C1): queda cortada a la derecha en ambos videos (TUT pierde Etapa; RED pierde Teléfono/Etapa y parte del correo).
- Los valores omitidos en RED (Empresa “Café Montaña”, Teléfono) se ven igual en el formulario y en la lista, porque la toma es una sola (E2); `omit` solo corta el tecleo.
- ego-browser avisó que hay una actualización de Ego Lite (actual 0.6.3.14); no se actualizó (requiere permiso del usuario).

## 6. `tutorial-qa`

Espacio de ego-browser 42 cerrado con `finish({ keep: [] })` (02:15:37).

### qa.py --pre final (ronda 2) + qa.py MP4

| video | regla | chequeo | estado | detalle |
| --- | --- | --- | --- | --- |
| tutorial | S3/A1 | resolución, duración, audio | PASS | 1920x1080, 40,88 s (timeline 40,87), aac |
| tutorial | A1 | loudness / true peak | PASS | −14,0 LUFS / −1,3 dBTP |
| tutorial | C4 | empty_frames (MP4) | **FAIL** | 34,32 s 72 % vacío (entre el clic en Guardar y el aviso) |
| tutorial | C1 | context | **FAIL** | 11,59–12,95 s (1,4 s) a 1× en Inicio (form_box del recorder en el clic del menú) |
| tutorial | C1 | zoom | WARN | plano de formulario 17,67–19,57 s a 1,09× |
| tutorial | resto (A2, O1, O2, R1, R2, T1, T2, C5, C7–C10, N1–N3, N5, N6, N10–N12, L1–L4) | — | PASS | |
| redes | S3/A1 | resolución, duración, audio | PASS | 1080x1920, 20,12 s, aac |
| redes | A1 | loudness / true peak | PASS | −14,0 LUFS / −2,8 dBTP |
| redes | C4 | empty_frames (MP4) | PASS | 63 fotogramas ≤ 70 % vacío |
| redes | N12/V2 | form_fields | **FAIL** | formulario [−8/−16, 190, 1112, 748] más ancho que 1080 (campos completos) |
| redes | resto (RED2, A2, N8, O1, O2, R1, R2, T1, T2, C1, C5, V1 71 %, V3, V4, C7–C10, N1–N3, N5–N7, N9–N11, L1–L4) | — | PASS | |

### Revisión visual (todas las capturas de qa-01 y qa-03, más fotogramas del MP4 a 33,9/34,32/34,6 s TUT y 15,9/16,2/16,5 s RED)

| regla | TUT | RED |
| --- | --- | --- |
| E1 | pasa: título + “Aprendes a registrar contactos.”; cierre “Siguiente video: buscar un contacto” | pasa: “¿Lo conociste en una feria? Regístralo así”; CTA con destino |
| C1/C7 | establecimiento a 1× en login e Inicio; detalle 1,4×; Inicio a 1× 1,4 s (falla) | detalle 1,4×, formulario 1,26× |
| N10/N11 | pasa: plano fijo del formulario completo, recuadro morado que se mueve campo a campo, resto oscurecido | pasa |
| N12/V2 | etiquetas visibles; título de página “Nuevo contacto” cortado arriba (no es campo) | todas las etiquetas visibles (Apellido, Cargo, Teléfono, Origen completos); padding cortado |
| C10 | **falla** 33,9 s: recuadro de Guardar sobre la lista nueva | **falla** 15,9–16,3 s: recuadro vacío + paneo sobre la lista |
| R2/N6 | aviso verde ≥ 0,8 s sin subtítulo encima (34,9 s) | aviso 16,55–17,45 s limpio |
| R3/N5 | fila nueva con contorno morado; chip, línea, banda en la paleta | igual; sin chip |
| N3 | banda inferior fija | banda dedicada inferior |
| L1–L3 | tú; “haz clic”; contacto | igual |

## Tiempos (wall clock) vs presupuesto de 10–12 min

| etapa | inicio–fin | duración |
| --- | --- | --- |
| lectura de skills/spec + doctor | 01:59:41–02:00:30 | ~0,8 min (doctor 8 s) |
| ensayo ego-browser | 02:00:58 | 7 s |
| brief + guion + 2 lint | 02:01:05–02:02:40 | ~1,6 min |
| capture | 02:02:45–02:03:38 | 53 s |
| pipeline 1 (tts→compose) | 02:03:52–02:06:20 | 148 s |
| qa --pre 1 + revisión de 33 capturas | 02:06:25–02:08:45 | ~2,3 min |
| ronda 1 (pipeline 72 s + qa 21 s) | 02:08:52–02:10:25 | ~1,5 min |
| ronda 2 (pipeline RED 32 s + qa 22 s + revisión) | 02:10:43–02:11:55 | ~1,2 min |
| render delivery (1 vez, paralelo) | 02:12:00–02:14:32 | 152 s |
| qa MP4 + verificación C4 + finish | 02:14:35–02:15:40 | ~1,1 min |
| worklog | 02:15:40–02:18 | ~2,3 min |
| **total** | 01:59:41–02:18 | **~18,3 min** |

- Trabajo de pipeline (capture → qa MP4): 02:02:45–02:15:00 ≈ **12,3 min**, levemente por encima del límite de 12 min. Las etapas más lentas: render (152 s), pipeline 1 (148 s, con tts 47 s y Lyria 43,5 s) y la revisión visual (~2 min por ronda).
- Ningún comando largo murió en silencio (todos con timeout ≥ 900 s; exit code y cola del log revisados).

## Salidas finales

| video | ruta | tipo | formato | duración | audio | pasos |
| --- | --- | --- | --- | --- | --- | --- |
| tutorial | proyectos/nexo-crm-contacto-v4/out/nexo-crm-contacto-v4-tutorial.mp4 | TUT | 16:9, 1920x1080, h264 + aac, 25 fps, 8,5 MB | 40,88 s | −14,0 LUFS / −1,3 dBTP | 1–5 |
| redes | proyectos/nexo-crm-contacto-v4/out/nexo-crm-contacto-v4-redes.mp4 | RED | 9:16, 1080x1920, h264 + aac, 25 fps, 3,1 MB | 20,12 s | −14,0 LUFS / −2,8 dBTP | nuevo, datos, guardar |

Voz: Gemini TTS (Kore, estilo por defecto de `.env`), en línea. Música: Lyria, 1 pista por video generada una vez y reutilizada. Costo: 2 pistas Lyria ≈ USD 0,16 + TTS de ~1100 caracteres (las rondas solo resintetizaron los clips cambiados).

## Lista de Parte 4 y Parte 5

### Parte 4 · Tutorial
- [x] Todo en zoom → corregido: planos a 1× en login (6,6 s) e Inicio (12,0 s) (qa-03).
- [x] Texto desfasado → corregido: N1 PASS; “Haz clic en Contactos” antes del clic (13,2 s), “Haz clic en Guardar contacto” sobre el formulario (33,6 s).
- [x] Texto repetido etiqueta/subtítulo → corregido: chip solo “Paso N”.
- [x] Apertura redundante → corregido: título “Tu primer contacto en Nexo CRM” + “Aprendes a registrar contactos.” (N2.opening PASS).
- [x] Subtítulos flotando → corregido: banda inferior (N3 PASS).
- [x] Formulario fijo y monótono → según N10/N11: plano fijo con recuadro que se mueve campo a campo (C8 PASS).
- [x] Etiqueta “Nombre” cortada → corregido (21,2 s); solo el título de la página queda cortado arriba.
- [x] No se ve el aviso → corregido (34,9 s).
- [x] Historia perdida → corregido: Origen Feria + nota “Conocida en la feria de Quito” + narración.
- [x] Colores / naranja / cajas negras / otra marca → corregido: #7c3aed y #1f1235 (N5 PASS).
- [ ] **Aún presente (nuevo):** recuadro de Guardar sobre la lista y un plano casi vacío antes del aviso (33,9–34,6 s; C4 72 %, C10).

### Parte 4 · Redes
- [x] Abre en “Paso 3” → corregido (sin chip, N7 PASS).
- [x] “Ape”, “Carg”, “Telé” cortados → corregido (5,99 s, 9,83 s); queda el FAIL formal de N12 por el padding.
- [x] “Vera” en un campo que no se ve → corregido (6,88 s).
- [x] Salto entre pantalla llena y franjas → corregido (N9 PASS, una sola composición).
- [ ] **Aún presente:** clic sobre la nada tras guardar: recuadro vacío y paneo sobre la lista (15,9–16,3 s). C4 en píxeles PASS.
- [x] Gancho sin cumplir → corregido (feria en tarjeta, datos y narración).
- [x] Cierre sin destino → corregido (“Tutorial completo en el enlace de nuestro perfil”).
- [x] Texto repetido → corregido.
- [x] Colores → corregido.

### Lo que sí funciona (sin regresiones)
- [x] Fila nueva resaltada, ahora en morado (TUT 36,4 s, RED 17,8 s); aunque queda cortada a la derecha.
- [x] El gancho funciona. [x] RED dura 20,1 s. [x] TUT cierra con el siguiente video. [x] Trato de tú.

### Parte 5
- [~] C1 revisada (1,4–1,8×): detalles a 1,4× en ambos; TUT C1.context FAIL (Inicio a 1× 1,4 s, causado por el recorder).
- [x] N10 plano de formulario: PASS en ambos (TUT 1,09–1,1×, RED 1,26×).
- [x] N11 recuadro + spotlight: PASS (10 y 5 campos).
- [~] N12: campos y etiquetas completos a lo ancho; FAIL formal por 16 px de padding (estructural).

### Specs de reglas-ronda3
- S1: (a) **falla** (C4 TUT 34,32 s); (b) PASS (R2 RED); (c) PASS visual (sin vecinos cortados), N12 formal FAIL; (d) PASS; (e) PASS (sin bloqueo; 1 pista por video); (f) render 152 s para 40,9 s + 20,1 s (v3: 296 s).
- S2: PASS en RED; TUT con C1.context FAIL por el recorder.
- S3: PASS (N10, N11); N12 formal FAIL.
- S4: hecho desde cero; TUT + RED entregados con 3 fallas automáticas documentadas.

## Parte 1 (26 errores)
- Corregidos: 23 (#1–3, 5, 7–22, 24–26).
- Parcial o aún presentes: 3. #4 C4: RED pasa, pero TUT tiene un fotograma vacío al 72 % a 34,32 s. #6 C1: Inicio a 1× durante 1,4 s. #23 V2: la fila resaltada queda cortada a la derecha y el padding del formulario se recorta en 9:16.

## Propuestas (por prioridad)
1. compose: en un `click` seguido de `screen_at`/`wait` con cambio de pantalla, cortar en seco al encuadre del `result` y quitar el recuadro del botón en cuanto cambie la pantalla. Resuelve S1a, C4 34,32 s y el “clic sobre la nada” en ambos videos.
2. recorder `formBox()`: contar solo campos visibles (`offsetParent`/box > 0) y no asignar `form_box` cuando el contenedor es casi todo el viewport. Así el clic del menú pasa a ser un detalle (C1.context).
3. N12 vs N9/V1: cuando el formulario no cabe a lo ancho a la escala mínima sin franjas, aceptar que se recorte el padding si `FIELD_EDGE` se cumple (que qa mida campos y no el contenedor), o permitir un encuadre 2× de arriba hacia abajo.
4. highlight de filas anchas: encuadrar desde el inicio de la fila hasta la columna mencionada (nombre…correo), o permitir < 1,4× para `highlight` (R1 sigue en detalle).
5. edit/RED: si hay `omit`, avisar que el valor se ve igual en el formulario y la lista (o sugerir no teclear campos opcionales en la toma compartida).
6. Presupuesto de tiempo: la revisión visual de ~33 PNG por ronda cuesta ~2 min; que qa.py arme una hoja de contacto por video (lo hice a mano con PIL fuera del repo).
7. lint: avisar de un posible gancho corto (RED1) con la duración real de TTS en vez de estimarla, para evitar rondas de tts.

## Preguntas abiertas
- Destino del CTA (se usó el propuesto “en el enlace de nuestro perfil”).
- Logo de Nexo CRM (render sin logo).
- Actualizar Ego Lite (aviso de ego-browser): requiere tu aprobación.
