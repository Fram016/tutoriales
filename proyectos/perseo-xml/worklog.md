# Worklog — perseo-xml (T4)

## 2026-11-18 — Intento detenido: sesión expirada

### tutorial (lectura)
- Leídos: skills `tutorial`, `tutorial-ensayo-captura`, `ego-browser` (+ `ego-browser skill` v2.2.1), spec `odd/tasks/perseo-xml.md` hasta `## Log` (L1–L9).
- El resto de skills de etapa (brief, guion, voz, edición, render, qa), `reglas/reglas-video.md` y los transcripts quedaron sin leer: el orden de trabajo priorizaba el ensayo con la sesión viva.

### tutorial-ensayo-captura (ensayo)
- `ego-browser nodejs` → `taskSpace(48)`: exit 0. Pestañas: p1 `https://srienlinea.sri.gob.ec/sri-en-linea/contribuyente/perfil?faces-redirect=true` (título "SRI en Línea"), p2 popup de la extensión (`chrome-extension://jakigokhcbfpebeiolidapdkeooiapeb/popup.html`).
- `page.goto(<enlace de consultas S4>)` en p1: exit 0, pero la página terminó en `https://srienlinea.sri.gob.ec/auth/realms/Internet/protocol/openid-connect/auth?...` con título **"SRI en Línea - Login"**.
- Se detuvo el trabajo según la instrucción: **sesión expirada**. No se escribió ninguna credencial, no hubo bucles de espera, no se llamó a `finish()` en el espacio 48 y no se cerró ninguna página.

### Fricción
- La pestaña p1 seguía mostrando el perfil, pero la sesión ya había caducado en el servidor. Eso solo se vio al navegar. Con la pestaña abierta no se sabe si la sesión sigue viva.
- ego-browser avisa de una actualización de Ego Lite (actual 0.6.3.14). No se actualizó porque hace falta la aprobación del usuario.

### Estado
- No se crearon `brief.md` ni `tutorial.yaml`. No hubo captura, TTS, música ni render, así que el costo fue 0.

### Propuestas (prioridad)
1. El usuario inicia sesión en el espacio 48 (handOff) justo antes de que el agente empiece. El agente ensaya y captura enseguida, sin escribir texto largo antes.
2. Preparar `brief.md` y un `tutorial.yaml` provisional sin sesión (selectores tomados del código de la extensión y de los transcripts). Así la sesión viva solo se usa para el ensayo corto y la toma.
3. Añadir a `capture.py` una comprobación previa que aborte si la URL inicial redirige a `/auth/realms/` (no se hizo: tools fuera de alcance).

## 2026-11-18 — Opción B: preparación sin sesión (no se tocó el espacio 48)

### tutorial / tutorial-brief
- Leídos completos: skills guion, voz, edición, render y qa; `reglas/reglas-video.md` (Partes 1–5); `referencias/uso-1/transcript.txt` y `uso-2/transcript.txt`. Fotogramas revisados: uso-1 2–8, 10, 11, 13, 15 y 30; uso-2 3, 5, 6, 8, 11 y 15.
- Código de la extensión (solo lectura): `popup.html`, `popup-script.js` y `content-script.js` (IDs `frmPrincipal:*` del SRI, botones y estados del popup, paleta).
- `proyectos/perseo-xml/brief.md` escrito: objetivo, audiencia (propuesta), TUT + RED, glosario, paleta del CSS del popup (#ca4100 / #09090b / Instrument Sans), historia "ninguna", CTA propuesto, flujo de 10 pasos y 5 preguntas abiertas.
- Fricción: en los fotogramas de referencia se ven datos reales (RUC, nombre, correo, teléfono del contribuyente y emisores de terceros). Solo se usaron para leer etiquetas; no se copió ningún valor.

### tutorial-guion
- `proyectos/perseo-xml/tutorial.yaml` provisional con 10 pasos, en el orden de S2: carpeta → consultas → emitidos → fecha-emitidos → consultar-emitidos → descargar-emitidos → recibidos → fecha-recibidos → consultar-recibidos → descargar-recibidos. Lleva `censor` (4 `env:` + 2 selectores de la tabla de recibidos), `surfaces.popup`, `follow: tab` / `back: main` para `chrome://settings/downloads` (sin clic en Cambiar), TUT 16:9 `steps: all` y RED 9:16 con [carpeta, consultar-emitidos, descargar-emitidos, descargar-recibidos].
- `.venv/Scripts/python.exe tools/lint.py perseo-xml` → 1.ª corrida: exit 1 (0,75 s): `[N2] videos.redes.opening.text` repite el título, y aviso `[A2]` cierre TUT ~2,6 s. Se corrigieron el texto del gancho RED y el cierre TUT ("Siguiente: importarlos.") → 2.ª corrida: `OK (0 avisos)`, exit 0.
- Nombres `env:` presentes en `acceso.local.yaml` (gitignored): PERSEO_XML_RUC, PERSEO_XML_NOMBRE, PERSEO_XML_EMAIL, PERSEO_XML_TELEFONO (solo se comprobaron los nombres).
- Fricción:
  - El recorder no entra en el shadow DOM, así que en `chrome://settings/downloads` no hay `focus` posible sobre Ubicación/Cambiar. Ese plano queda en 1,0× unos 2,5 s (`pause`).
  - El popup no tiene una señal visible de "descarga terminada" que distinga la descarga nueva de un historial anterior. Se usa `wait: "#boton4 b"` (el botón recupera su contenido) más `pause: 2100` (el resumen se refresca cada 2 s).
  - `pointAt` no reintenta, así que cada clic del menú necesita su `wait:` previo.

### Plan de grabación (parte en vivo, justo después de que el usuario inicie sesión)

Condición: el usuario inicia sesión en SRI en línea dentro del espacio 48 y avisa. Si en cualquier momento aparece "SRI en Línea - Login" o una URL `/auth/realms/`, se detiene todo y se informa "sesión expirada".

**1. Ensayo (≤ 3 min, un solo script `ego-browser nodejs`, espacio 48, p1).** No hace clic en los botones de descarga ni en "Cambiar", y solo imprime booleanos, tamaños e IDs, nunca texto de la página:
1. `const task = await taskSpace(48); const p = task.page("p1");` → `goto` del perfil (`app_url`). Si el título contiene "Login", se detiene.
2. Hamburguesa: comprobar que `xpath=(//header//*[self::button or self::a])[1]` es el icono del menú. Si no, listar `class`/`aria-label` de los botones del header y elegir uno. Clic.
3. `text=Facturación Electrónica` → clic → `text=Producción` → clic → `text=Consultas` → clic → `waitForSelector('text="Comprobantes electrónicos emitidos"')`. Anotar si algún `wait` de texto es ambiguo; si lo es, cambiarlo por un selector CSS o `xpath=`.
4. Clic en emitidos → existe `[id="frmPrincipal:calendarFechaDesde_input"]`. Escribir la fecha candidata, pulsar `Tab` (¿se cierra el calendario?), clic en `text="Consultar"` → esperar `[id="frmPrincipal:tablaCompEmitidos_data"] tr` y contar las filas. Elegir una fecha anterior a hoy con **1–5 comprobantes** (probar 2–3 fechas si hace falta).
5. Clic en `text="Anterior"` → `text="Comprobantes electrónicos recibidos"` → existe `[id="frmPrincipal:ano"]`. Seleccionar 2026 / Noviembre / 1 → Consultar → contar las filas de `[id="frmPrincipal:tablaCompRecibidos_data"] tr` (objetivo: pocas; ¿hubo reCAPTCHA?). Comprobar el orden de columnas: la 2 tiene que ser "RUC y Razón social emisor" y la 4 "Clave de acceso".
6. Censura: inyectar el censor igual que el recorder (`censorSource` de `tools/capture/recorder.mjs` con los 4 `env:` leídos dentro del script) y comprobar que hay 0 nodos visibles con los valores en el perfil, el encabezado, el campo RUC, las claves de emitidos y el popup p2. Guardar capturas en `proyectos/perseo-xml/build/censor-*.png` (fuera de git) y revisarlas.
7. Popup p2: `#configure-folder`, `#boton1`, `#boton4` y `#texto_correctos` visibles. **Sin clic.**
8. Si algo cambió, actualizar los selectores y fechas de `tutorial.yaml` y correr `tools/lint.py perseo-xml`.

**2. Toma (inmediatamente después, timeout ≥ 900 s):**
```
.venv/Scripts/python.exe tools/capture.py perseo-xml   # luego: echo exit=$?; revisar [take] paso … ok y capture/actions.json → failure
```
capture.py usa su propio espacio ("tutorial perseo-xml") con la sesión del perfil y lo cierra al terminar; el espacio 48 no se cierra.

**3. Después (no necesita sesión):** `pipeline.py perseo-xml --from tts --to compose` → `qa.py perseo-xml --pre` (≤ 3 rondas) → `pipeline.py perseo-xml --only render --quality delivery` → `qa.py perseo-xml`.

### Riesgos para la toma
- Selector de la hamburguesa y `wait:` de texto del menú sin confirmar.
- reCAPTCHA en recibidos.
- Captura de `chrome://settings` vía CDP sin probar.
- La sesión del SRI debería pasar al espacio nuevo de capture.py por cookies del perfil; si el portal usa sessionStorage, la toma empezaría en el login.
- Las descargas reales caen en la carpeta del usuario.

## 2026-11-18 — Parte en vivo (espacio 48, sesión activa) y flujo rápido

### tutorial-ensayo-captura (ensayo, 09:2x–09:33, ~10 min con búsqueda de fechas)
- Selectores confirmados en vivo: `#sri-menu` (hamburguesa), `xpath=//a[contains(@class,'ui-panelmenu-header-link')][normalize-space()='FACTURACIÓN ELECTRÓNICA']`, `xpath=//a[normalize-space()='Producción']`, `xpath=…Producción…//a[normalize-space()='Consultas']` (el menú tiene 3 "Consultas"), `[id="frmPrincipal:btnConsultar"]` (emitidos), `[id="frmPrincipal:btnBuscar"]` (recibidos), `[id="frmPrincipal:btnAnterior"]`, `frmPrincipal:ano/mes/dia`, `frmPrincipal:cmbEstablecimiento`, `frmPrincipal:txtPuntoEmision`.
- Columnas de la tabla de recibidos: 2 = "RUC y Razón social emisor", 4 = "Clave de acceso / Nro. Autorización", así que los selectores de censura de terceros son correctos.
- Censura en vivo (censorSource del recorder + los 4 env: leídos dentro del script, sin imprimir): 0 nodos de texto con valores visibles, 0 inputs, celdas 2 y 4 marcadas. Captura: `%TEMP%/perseo-censor-recibidos.png` (fuera del repo).
- reCAPTCHA en recibidos: solo el sello invisible; no apareció ningún desafío.
- Login: no hizo falta (la sesión siguió activa; no se usó el helper).
- Fechas: los días hábiles tienen 100+ facturas emitidas. Notas de Crédito tienen 5, pero "XML Desde el RIDE" no las admite ("Tipo de comprobante no soportado… codDoc 04"). Elegido: emitidos 13/11/2026, Factura, establecimiento 001, punto 901 → **12 facturas**. Recibidos: 01/11/2026, Factura → **6**.

### Toma (capture.py, 8 intentos, exit 1 ×7 y exit 0 en la 8.ª; ~2–3 min cada uno)
| # | Hora | Resultado | Causa / cambio |
|---|---|---|---|
| 1 | 09:33 | exit 1 | `text="Comprobantes electrónicos recibidos"` coincide con 2 elementos (span oculto del menú) |
| 2 | 09:37 | exit 1 | `wait` con xpath: el primer `<a>` del DOM es el oculto del menú lateral |
| 3 | 09:40 | exit 1 | el clic con xpath iba al enlace oculto → `//li[contains(@class,'sri-listaLinks')]/a[…]` |
| 4 | 09:43 | exit 1 | la extensión no descargó nada: el parche de tabs.query eligió la p1 del espacio 48 (también en SRI). p1 se llevó a about:blank antes de cada toma |
| 5 | 09:45 | exit 0 | pero (a) Notas de Crédito no admitidas (0 descargados, 5 con error) y (b) `chrome://settings/downloads` muestra la ruta con el usuario de Windows en claro (la censura no llega a chrome://; cuadro f000095 de esa toma) → se quitó `follow: tab` |
| 6 | 09:51 | exit 1 | tras la descarga, el clic en recibidos no navegó |
| 7 | 09:54 | exit 1 | igual que la 6 (con pausa de 1,5 s) |
| 8 | 09:57 | **exit 0** | "recibidos" vuelve a Consultas con `goto` al enlace S4. 603 cuadros (~3,7 fps), 10 pasos, popup con 3 aperturas, 2 m 44 s |

- Descargas reales en la toma final: emitidos 12 descargados / 0 con error (`surfaces/popup/frames/w1_f000023.jpg`); recibidos 6 / 0 (`w2_f000025.jpg`). Las tomas anteriores también descargaron archivos reales a la carpeta Descargas del usuario (5 o 6, 12 y 6 por toma completada).

### Verificación de censura en cuadros de la toma final (revisados con el visor de imágenes)
- Perfil (RUC, nombre, correo, teléfono) difuminados: `capture/frames/f000091.jpg`.
- Encabezado (RUC + nombre) difuminado en todas las pantallas del SRI; campo RUC de la consulta y RUC dentro de las claves de acceso de emitidos difuminados: `capture/frames/f000419.jpg` (de la toma 7; la toma 8 muestra lo mismo en `f000323.jpg`).
- Recibidos: columna RUC/Razón social del emisor y claves de acceso difuminadas: `capture/frames/f000514.jpg`.
- Popup: sin datos personales (`surfaces/popup/frames/w0_f000029.jpg`).
- Snapshot compuesto: `hf-tutorial/.hyperframes/artifacts/snapshots/qa-01/at-13.196s.png` (perfil difuminado detrás del popup).

### Flujo rápido
- Pipeline 1 (10:00–10:05, exit 1, 272 s): compose falló, `font_family_without_font_face: instrument sans` (hyperframes no tiene @font-face para la fuente del popup) → `brand.font: "Segoe UI"`. Música Lyria: 2 pistas generadas (≈ USD 0,16).
- Pipeline 2 (10:06–10:10, exit 0, 217 s) → **PRE ronda 1** (`qa.py --pre`, exit 1): tutorial A2, O1, O2, T1 («Abre Perseo XML y,»), C1, C8, C9, C10, N12; redes S3.duration, A2, C9, C10. Narraciones alargadas (A2), T1 corregido, RED sin `carpeta`.
- Pipeline 3 (10:12–10:15, exit 0, 211 s) → **PRE ronda 2** (exit 1): tutorial O1/O2 (resaltado de la tabla de recibidos bajo la banda), C1.context, C9/C10 (clics del popup), N12; redes S3.duration 36,3 s, A2 (1,8 / 4,0 / 4,0 s), C9/C10, C1.zoom WARN. Corregidos A2, T1 y C8 del tutorial.
- **PRE ronda 3** (pipeline `--from tts --to compose --video redes`, 59 s, exit 0; `qa.py --pre` exit 1): RED 32,3 s (S3 OK). Gancho "¿Muchos XML?", y la narración de consultar-emitidos se acortó a "Haz clic en Consultar. Aparece la lista." Quedan: redes A2 (2,3 s ×2), C9/C10, C1.zoom WARN; tutorial O1/O2, C1.context, C9/C10, N12. Se alcanzó el tope de 3 rondas: no hay más iteración.
- Snapshots revisados: tutorial `hf-tutorial/.hyperframes/artifacts/snapshots/qa-01/at-13.196s.png`, `at-51.478s.png`, `at-58.996s.png`, `at-77.056s.png`; redes `hf-redes/.hyperframes/artifacts/snapshots/qa-03/at-1s.png`, `at-17.971s.png`, `at-31.492s.png` (y `qa-01/at-14.159s.png`, `at-26.674s.png`). En el video los clics del popup caen sobre el botón correcto; el resultado (12 / 6 Descargados) se ve en detalle.
- Defecto visual sin resolver: `brand/logo.png` es negro y queda casi invisible sobre la tarjeta `#09090b` de apertura y cierre (redes `qa-03/at-1s.png`). Arreglo propuesto (una línea en tutorial.yaml + rerun desde compose + un render): `brand.background: "#ca4100"`, o un logo claro.

### Render final (una sola vez)
- `pipeline.py perseo-xml --only render --quality delivery`: 10:37:40–10:43:53, exit 0, 372 s (2 videos en paralelo). Re-renders: 0.
- `qa.py perseo-xml` (MP4): exit 1.

| Video | Ruta | Tipo | Formato | Duración | LUFS / pico |
|---|---|---|---|---|---|
| tutorial | `proyectos/perseo-xml/out/perseo-xml-tutorial.mp4` | TUT | 16:9 1920x1080 | 93,24 s | -14,0 / -2,1 dBTP |
| redes | `proyectos/perseo-xml/out/perseo-xml-redes.mp4` | RED | 9:16 1080x1920 | 32,32 s | -14,0 / -1,7 dBTP |

### QA final (fallos que quedan y capa que debe corregirlos)
| Video | Regla | Detalle | Capa |
|---|---|---|---|
| tutorial | C4 | 24,6–31 s: tras el clic en "Consultas" (menú), la cámara se queda con el recuadro sobre el menú ya cerrado, en la página nueva casi vacía (cuadro extraído a 25 s: recuadro naranja vacío) | compose (C10: cambio de pantalla tras un clic que navega) o recaptura con `focus:` en la página nueva |
| tutorial | O1/O2 | el resaltado de la tabla de recibidos llega bajo la banda/chip en 75,9 s | compose (O2: mover el encuadre) o recaptura con un `highlight:` más chico |
| tutorial | C1.context | planos de ubicación de 1,5 s (7,3 s y 60,8 s) | compose |
| tutorial + redes | C9/C10 | los clics del popup (`#configure-folder`, `#boton4`, `#boton1`) se evalúan en coordenadas de la página principal (x negativas); en el video caen bien | qa.py/compose (eventos con `surface`) |
| tutorial | N12 | `form_box` [492,80,1985,…] más ancho que el viewport (contenedor de la consulta + tabla) | recorder (formBox sin recorte de ancho) / compose |
| redes | A2.voice_gaps | 2,3 s sin voz mientras la extensión descarga (×2) | edit (span de la descarga a 3×) o narración más larga |
| redes | C1.zoom | WARN: formularios a 1,53× | compose (aviso) |

### Tiempos
| Etapa | Duración |
|---|---|
| Ensayo en vivo | ~10 min (incluye búsqueda de fechas) |
| Tomas (8) | ~19 min (la buena: 2 m 44 s) |
| Pipelines tts→compose (4) | 272 + 217 + 211 + 59 s |
| `qa.py --pre` (3) | ~50 s cada uno |
| Render | 372 s |
| `qa.py` MP4 | ~1 min |

Costo: Lyria 2 pistas (≈ USD 0,16); TTS de las narraciones nuevas o cambiadas (4 corridas, en caché las que no cambiaron).

### Fricción
1. `text=` y xpath encuentran primero enlaces ocultos del menú lateral del SRI (mismo texto) → hay que usar el xpath de la lista `sri-listaLinks`.
2. El parche de `tabs.query` elige la pestaña SRI más reciente de **todo** el navegador: una pestaña del SRI abierta en otro espacio (p1 del 48) se lleva los mensajes de la extensión.
3. `chrome://settings/downloads` no admite censura y muestra la ruta con el usuario de Windows: no se pudo mostrar Ubicación/Cambiar.
4. "XML Desde el RIDE" no admite Notas de Crédito; elegir pocos comprobantes exigió filtrar por establecimiento y punto de emisión.
5. Tras una descarga, "Anterior" + clic en recibidos no navegaba de forma fiable → `goto` al enlace S4.
6. Cada toma descarga XML reales (5 tomas completas o parciales con descargas).
7. hyperframes no tiene la fuente del popup (Instrument Sans) → Segoe UI.
8. qa.py no traduce coordenadas de superficies (popup) y marca falsos C9/C10.

### Propuestas (prioridad)
1. compose: después de un clic que navega, cortar al plano de ubicación de la página nueva (evita el C4 de 24–31 s).
2. qa.py/compose: mapear los eventos con `surface` a la posición compuesta del popup (C9/C10).
3. recorder: `target_tab` debería limitarse a las pestañas del espacio de la toma.
4. Logo claro (o tarjeta con `primary`) para la marca Perseo.
5. recorder: recortar `form_box` al viewport (N12).

Estado del espacio 48: no se llamó a finish. p1 está en about:blank (sesión del SRI viva en cookies) y p2 sigue en el popup.
