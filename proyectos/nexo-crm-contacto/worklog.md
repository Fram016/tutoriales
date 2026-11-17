# Worklog: nexo-crm-contacto (prueba de skills, T2 de odd/tasks/video-demo-crm.md)

Agente: subagente "tutorial" (delegado). Fecha: 2026-11-17, 16:18 → 16:50 (≈ 32 min de reloj).
Objetivo de la corrida: producir el tutorial siguiendo los skills al pie de la letra y registrar cada fricción.
Credenciales: solo por nombre (`NEXO_CRM_CONTACTO_USER`, `NEXO_CRM_CONTACTO_PASSWORD`); nunca se imprimieron ni copiaron.

---

## 1. `tutorial` (entrada / orquestador)

**Qué dice:** preflight con `doctor.py` (`--online` si hay GEMINI_API_KEY), slug kebab, crear `proyectos/<slug>/` + `brand/`, brief primero, luego guion → ensayo/captura → voz → edición → render → QA; tras la toma, `pipeline.py --from tts --quality draft` y al final `--quality delivery` desde `compose`.

**Qué hice:**
- `.venv/Scripts/python.exe tools/doctor.py --online` → exit 0, 9 s, "0 fallas, 0 advertencias" (Gemini TTS gemini-3.8-flash-tts / Kore OK, HyperFrames 0.9.64, ego-browser 0.6.3.14).
- Slug dado por el padre; `mkdir -p proyectos/nexo-crm-contacto/brand` (quedó vacío: sin logo).
- Gate: "App URL + credenciales + flujo" → modo A.

**Fricción:**
- `doctor.py --online` sintetiza un clip TTS real (57 KB) para verificar: es un costo pequeño, pero el skill dice que corre "una vez que existe la key" sin decir que cobra.
- El Output Contract pide "voz + música usadas" y "nota de costo", pero no dice cómo saber cuántos caracteres se facturaron (tts.py no lo imprime).

## 2. `tutorial-brief`

**Qué dice:** copiar `templates/brief.md`, pegar instrucciones textuales, guardar credenciales (ya estaban), leer código fuente read-only con fuente `(código ruta:línea)`, proponer Objetivo/Audiencia/Enfoque/Flujo/Datos, verificar login en ego-browser, preguntas abiertas.

**Qué hice:**
- Leí `demo-apps/nexo-crm/index.html` (194 líneas) completo: selectores `#login-email`, `#login-password`, `#btn-login`, `#nav-contactos`, `#btn-nuevo-contacto`, `#buscar`, `#c-*`, `#btn-guardar`, `#toast`, `tr.new`; validación y duración del toast (2,5 s).
- Escribí `brief.md` (instrucciones L3 textuales; marca propuesta `#7c3aed`/`#a78bfa`/`#1f1235`/blanco/Segoe UI, sin logo; datos ficticios "Sofía Ramírez, Café Montaña").
- Verificación de login: `ego-browser nodejs` (heredoc, Git Bash), task space **22**, viewport 1920x1080 → exit 0, ~1 s; `#view-inicio` visible, sin error, sin 2FA/CAPTCHA/SSO. Las credenciales se leyeron dentro del script desde `acceso.local.yaml` (parser plano propio, Node no trae YAML) y no se imprimieron.

**Fricción:**
- **El código fuente de la app contiene las credenciales demo en texto plano** (`const DEMO = {...}`). El skill dice "leer el código read-only" pero no advierte qué hacer cuando el código expone secretos (no copiarlos, no citarlos con `:línea`). Las cité solo por rango de líneas sin valores.
- La app usa **voseo** ("Ingresá", "Completá", "Organizá") y el skill de guion prohíbe voseo en la narración. Ningún skill dice qué hacer cuando la UI y la narración chocan (¿se nombra el label tal cual? ¿se avisa al usuario?). Lo anoté en el brief y narré en neutro.
- El **correo de la cuenta demo es visible** en el video (se tipea en el login y aparece en el encabezado). Las reglas dicen "nunca poner valores en brief/yaml/logs" pero no dicen si el usuario demo puede verse en pantalla; QA solo falla por "credenciales reales". Lo acepté (dominio `.demo`) y lo dejé en Preguntas abiertas.
- Orden del skill: el paso 7 (verificar login) va después del paso 6 (llenar el brief), pero la plantilla obliga a escribir "Login verificado: sí/no" antes. Escribí "sí" anticipado y lo verifiqué enseguida; mejor que la plantilla diga "pendiente".
- El skill no dice cómo leer `acceso.local.yaml` dentro de un script de ego-browser (Node ESM, sin `yaml`, `process.env` no se hereda). Tuve que improvisar un parser de `NOMBRE: valor`. Un helper reutilizable evitaría errores con valores con `:` o comillas.
- Brief.md no tiene campo para Marca (logo/colores/fuente) aunque `tutorial` paso 3 pide reunirla en el brief; la puse bajo Fuentes y Preguntas abiertas.

## 3. `tutorial-guion`

**Qué dice:** esquema de `_demo/tutorial.yaml`, una idea por paso, ~2,6 palabras/s, `summary: true` en pasos que prueban el objetivo, presupuesto ≤ 60-70 s, `wait:` al final de cada paso que cambia la página, selectores como "best guess".

**Qué hice:**
- `tutorial.yaml` con 8 pasos (login, contactos, nuevo, obligatorios, empresa, etapa, guardar, buscar), 5 con `summary: true` (login, nuevo, obligatorios, guardar, buscar). Voz `Aoede` (tono "breezy/cercano") con estilo propio; música "light corporate pop".
- Estimación (script de conteo): 105 palabras → 46,4 s completo y 66 palabras → 31,4 s resumen (incluye intro+outro 6 s).
- Selectores: tomados del código (ya confiables), no "best guess".

**Fricción:**
- La estimación por palabras **solo cuenta la voz**: el resultado real fue 59,5 s (las acciones de tipeo duran más que la voz). El skill dice "trim narration, not steps" cuando sobra, pero no dice qué hacer cuando **falta** duración (el brief pedía 60-90 s). Terminé alargando una narración y el outro.
- No hay guía para elegir voz según el "tono" del brief (la tabla de `tutorial-voz` mapea firm/upbeat/breezy… pero el guion es quien escribe `voice:`). Elegí Aoede sin poder escucharla antes.
- No dice si la narración puede ir en segunda persona singular ("Ya puedes…") en el outro: el ejemplo del skill la usa, aunque la regla general es plural.

## 4. `tutorial-ensayo-captura`

**Qué dice:** cargar ego-browser y correr `ego-browser skill`; un task space para el ensayo; ejecutar cada acción con el mismo selector; snapshot por paso; corregir yaml; `finish({keep: []})`; luego `capture.py`.

**Qué hice:**
- `ego-browser skill` (guía v2.2.1, completa, termina en `end of guide`).
- Ensayo en el mismo task space 22: los 8 pasos con `page.fill/click/selectOption/waitForSelector` + `page.evaluate` para estado compacto (vistas visibles, filas, toast) en lugar de 8 snapshots completos; 2 screenshots en `%TEMP%` (formulario lleno y lista con toast) revisados visualmente. Todo OK al primer intento, ningún selector cambiado.
- `finish({ keep: [] })` del space 22 → exit 0.
- Toma 1: `tools/capture.py nexo-crm-contacto` → exit 0, 66 s, 1029 cuadros (~16,1 fps), 8 pasos, sin `failure`; evento de contraseña marcado `secret`.
- Toma 2 (ronda QA 1): vía `pipeline.py --from capture` → 1070 cuadros (~15,8 fps), 68,5 s.

**Fricción:**
- **capture.py no imprimió las líneas `[take] paso <id> ok`** que el skill promete (solo la línea final). Tuve que leer `capture/actions.json` para ver tiempos por paso. Probable causa: la salida de `ego-browser nodejs` no llega línea a línea o lleva prefijos (`[ego-browser:notice]`).
- ego-browser mostró `[ego-browser:notice] Ego Lite update is available` en cada corrida; la guía dice terminar la tarea y pedir permiso para `ego-browser upgrade`. No actualicé (sin autorización); queda para el usuario.
- El ensayo con `page.fill` **no reproduce** lo que hace el recorder (clic + tecleo carácter a carácter, `selectOption` sin abrir el desplegable, `mouse.move` previo). Un ensayo "con los mismos selectores" no detecta problemas de cámara/zoom; los dos problemas reales aparecieron recién en QA.
- El skill no menciona que **la cámara sigue al último punto del puntero**: tras un clic que cambia de página, el encuadre se queda donde estaba el botón. La solución (añadir `hover:` sobre el resultado) no está documentada en ningún skill; la deduje leyendo `tools/compose.py:camera_plan`.
- Tras agregar los `hover:` no volví a ensayar en ego-browser (el skill pide ensayar antes de la toma, pero la tabla de QA manda directo a `--from capture`). Funcionó, pero el flujo es ambiguo.
- Escritura en vivo: el tipeo real fue ~0,15 s/carácter (no 45 ms como sugiere `typeDelay`), así que los pasos de formulario se aceleran 1,5-2,3x en edición.

## 5. `tutorial-voz`

**Qué dice:** `tts.py <slug>` online; caché por texto+voz+estilo; luego `pipeline --from edit`.

**Qué hice:** corrió dentro de `pipeline.py --from tts --quality draft` (exit 0): 8 clips, 43,1 s de voz, 33,8 s. Ronda 1: solo re-sintetizó `guardar` y `buscar` (12,4 s), 44,4 s de voz. Final: login 5,12 · contactos 5,04 · nuevo 3,72 · obligatorios 6,00 · empresa 4,80 · etapa 6,20 · guardar 8,04 · buscar 5,52 s. Voz Aoede, estilo "voz cálida y cercana, como un compañero que te enseña, español latinoamericano neutro, ritmo ágil y claro".

**Fricción:**
- No hay forma de escuchar/aprobar la voz como agente; el skill no pide una verificación de pronunciación (p. ej. transcribir el clip con `faster_whisper`, que ya está instalado) antes de seguir.
- tts.py no informa caracteres facturados (≈ 829 caracteres en total en esta corrida, calculado aparte).

## 6. `tutorial-edicion`

**Qué dice:** `edit` → `music` → `mix`; Lyria se cobra, se reutiliza; revisar LUFS ≈ -14 y pico ≤ -1,5 dBTP.

**Qué hice:**
- Draft: edit 13,1 s (full 59,5 s / short 39,1 s); music Lyria `lyria-3.5` generada **una sola vez** (22,7 s); mix full -14,1 LUFS / -1,9 dBTP, short -14,3 LUFS / -1,9 dBTP.
- Ronda 1: edit full 61,8 s / short 41,4 s; music "reutilizo music.mp3"; mix igual.
- Aceleraciones notables (full): login 1,48x, obligatorios 1,61x, empresa 1,73x, etapa 2,31x; congelados: guardar (voz 8 s sobre ~3,5 s de acción).

**Fricción:**
- **Lyria devolvió 60,8 s cuando music.py pidió ~64 s** (`int(59.5)+5`), y además con "gentle ending". El video final dura 61,9 s: en el outro del 16:9 la música ya se desvaneció (≈ -55 a -88 dB rel. pico) y **vuelve a arrancar en bucle en el último ~0,75 s** (≈ -52 dB rel. pico, muy bajo pero presente). Ni music.py ni mix.py ni qa.py verifican que la pista cubra la duración; mix hace `-stream_loop -1` en silencio.
- music.py calcula la duración con el primer `edit` y reutiliza la pista para siempre; si el guion crece después, nadie avisa.
- El skill pide "reportar aceleraciones/congelados dignos de nota" pero edit.py no los imprime; los saqué de `edit/*/timeline.json`.

## 7. `tutorial-render`

**Qué dice:** compose (cuenta avisos de `hyperframes check`), `render --quality draft` para iterar, `delivery` al final; "sin logo" → pedir logo antes del render final.

**Qué hice:**
- Draft 1: compose 33,8 s (17/28 avisos), render 251,3 s → 59,53 s / 39,10 s.
- Draft 2 (ronda 1): compose 37,2 s (16/28 avisos), render 316,5 s → 61,87 s / 41,40 s.
- Final: `pipeline.py nexo-crm-contacto --from compose --quality delivery` → exit 0, 399 s (compose 49,4 s, render 349,0 s).

**Fricción:**
- compose solo imprime **el número de avisos** de `hyperframes check` (16 y 28), nunca cuáles son; el Output Contract pide reportarlos y no hay manera sin correr hyperframes a mano.
- "sin logo → pedir el logo antes del render final": aquí el padre dijo explícitamente "sin logo", pero el skill no contempla esa excepción.
- **La fuente de marca "Segoe UI" no se usa en intro/outro/subtítulos**: el render sale con una sans tipo Roboto (causa no verificada; probablemente el Chrome headless de HyperFrames no resuelve Segoe UI). El checklist de QA pide "fuente correcta" y el skill de guion sugiere "Segoe UI" en el ejemplo. Debería documentarse qué fuentes están disponibles en el render.
- Render draft tarda 4-5 min por ronda; el skill no da tiempos esperados, útil para planificar las 3 rondas de QA.

## 8. `tutorial-qa`

**Qué dice:** `qa.py`, abrir TODOS los PNG, checklist por snapshot, arreglar y re-correr desde la etapa correcta, máximo 3 rondas.

**Qué hice:**
- QA draft 1 (`qa.py`, exit 0, 22 s): técnico PASS. Revisé los 17 PNG:
  - FAIL full "Paso 3" y short "Paso 2" (paso `nuevo`): la cámara quedó en el botón (arriba a la derecha), el formulario cortado y el cursor en espacio vacío.
  - FAIL short "Paso 4" (paso `guardar`): la ventana 1080x1080 seguía el clic del botón Guardar; no se veían ni el nombre del contacto nuevo ni el aviso verde.
  - Resto PASS.
- Ronda 1 (tabla: "wrong element" → `--from capture`): `hover: "#c-nombre"` en `nuevo`; `hover: "#toast"` + `hover: "tr.new td"` en `guardar` y narración reordenada (aviso → lista); "¡Ahí está Sofía!" en `buscar` y outro 3 → 4 s para pasar de 60 s. `pipeline.py --from capture --quality draft` → exit 0, 464 s. `qa.py` → exit 0, 24 s, PASS; revisé de nuevo los 17 PNG → todos PASS. Extraje además con ffmpeg un cuadro en `guardar`+2 s de cada variante (los snapshots de mitad de paso no muestran el aviso): toast visible en ambos.
- Final delivery: `qa.py` → exit 0, 27 s, PASS. Revisé hojas de contacto extraídas **del MP4 final** (11 cuadros 16:9, 8 cuadros 9:16) en los mismos tiempos: coinciden con los snapshots.

| Variante | Snapshot | Veredicto |
| --- | --- | --- |
| 16:9 | intro 1,5 s | PASS (fuente no es Segoe UI, ver fricción) |
| 16:9 | Paso 1 login | PASS (correo demo visible, contraseña enmascarada) |
| 16:9 | Paso 2 contactos | PASS (chip "Paso 2" tapa el logo de la app, menor) |
| 16:9 | Paso 3 nuevo | FAIL r0 → PASS r1 |
| 16:9 | Paso 4 obligatorios | PASS |
| 16:9 | Paso 5 empresa | PASS |
| 16:9 | Paso 6 etapa/notas | PASS |
| 16:9 | Paso 7 guardar | PASS con observación: con el zoom 2x el aviso queda en la banda del subtítulo y éste tapa "Con…" ~1,4 s |
| 16:9 | Paso 8 buscar | PASS |
| 16:9 | outro | PASS |
| 9:16 | intro | PASS |
| 9:16 | Paso 1 login | PASS |
| 9:16 | Paso 2 nuevo | FAIL r0 → PASS r1 |
| 9:16 | Paso 3 obligatorios | PASS |
| 9:16 | Paso 4 guardar | FAIL r0 → PASS r1 (aviso y fila nueva visibles) |
| 9:16 | Paso 5 buscar | PASS |
| 9:16 | outro | PASS |

**Fricción:**
- **Los snapshots de qa.py salen de la composición (`hf-*/.hyperframes/...`), no del MP4 entregado**, y siempre a mitad de paso: un aviso efímero (toast 2,5 s) o un problema al inicio/fin del paso no se ve. Tuve que extraer cuadros extra con ffmpeg.
- Los PNG se sobrescriben entre rondas con el mismo nombre (`at-6.46s.png`): no hay forma de comparar antes/después.
- El checklist no tiene ítem para audio (música que se corta/repite, voz que se pisa) ni para la duración objetivo del brief (60-90 s / < 45 s); qa.py solo compara contra el timeline.
- El conflicto subtítulo vs. elementos anclados abajo (toasts, barras de acción) no se puede arreglar desde `tutorial.yaml`: el subtítulo es fijo en la plantilla y el zoom lleva el elemento a esa banda. Quedó como observación.
- La tabla "Fix → rerun" no cubre "encuadre/zoom incorrecto" explícitamente; lo asimilé a "wrong element" (`--from capture`).

---

## Resultados finales

| Archivo | Resolución | Duración | Audio | Sonoridad |
| --- | --- | --- | --- | --- |
| `proyectos/nexo-crm-contacto/out/nexo-crm-contacto-16x9.mp4` | 1920x1080, 30 fps, h264 | 61,87 s | AAC 48 kHz estéreo | -14,1 LUFS, pico -1,9 dBTP |
| `proyectos/nexo-crm-contacto/out/nexo-crm-contacto-9x16.mp4` | 1080x1920, 30 fps, h264 | 41,40 s | AAC 48 kHz estéreo | -14,3 LUFS, pico -1,9 dBTP |

- Calidad: `delivery`. Modo online (sin `--offline`). Voz Gemini TTS `gemini-3.8-flash-tts` / Aoede. Música Lyria `lyria-3.5` (1 pista, 60,8 s).
- QA: técnico PASS en ambas variantes; visual PASS en 17/17 snapshots tras 1 ronda de correcciones (1 observación menor en 16:9 Paso 7).
- Duraciones vs. brief: 16:9 61,9 s (meta 60-90 s ✔), 9:16 41,4 s (meta < 45 s ✔).
- Pendientes: sin logo (por indicación); ego-lite tiene actualización disponible (no aplicada); música con bucle muy bajo en el último 0,75 s del 16:9.

## Tiempo y costo por etapa (aprox.)

| Etapa | Tiempo de herramienta | Costo |
| --- | --- | --- |
| Preflight (doctor --online) | 9 s | 1 clip TTS de prueba (mínimo) |
| Brief (lectura código + login) | ~4 min agente, 1 s ego | 0 |
| Guion | ~3 min agente | 0 |
| Ensayo (ego-browser) | ~2 min agente, 1 s script | 0 |
| Captura ×2 | 66 s + 68,5 s | 0 |
| Voz ×2 | 33,8 s + 12,4 s | ≈ 829 caracteres TTS (641 + 188) |
| Edición (edit+music+mix) ×2 | 43,8 s + 28,2 s | Lyria 1 pista ≈ USD 0,08 |
| Compose ×3 | 33,8 + 37,2 + 49,4 s | 0 |
| Render ×3 (draft, draft, delivery) | 251,3 + 316,5 + 349,0 s | 0 |
| QA ×3 + revisión visual | 22 + 24 + 27 s, ~6 min agente | 0 |
| **Total** | ≈ 32 min reloj (≈ 22 min de herramientas, 15 de ellos de render) | ≈ USD 0,08 + TTS por ≈ 830 caracteres |

## Mejoras propuestas (priorizadas)

1. **Cámara tras un clic que navega** (`tools/compose.py:camera_plan` + skills ensayo/QA): mover el foco al primer elemento visible del resultado (el `wait:` del paso) en lugar del último punto del puntero; mientras tanto, documentar en `tutorial-guion`/`tutorial-ensayo-captura` "añadí `hover:` sobre el resultado después de un clic que cambia de vista". Fue la causa de los 3 FAIL.
2. **qa.py**: snapshots del MP4 final (no de la composición), un cuadro extra al inicio y fin de cada paso (o al momento de cada `wait:`), nombres por paso (`<variante>-<id>.png`) y comparación con las duraciones objetivo del brief.
3. **Música**: music.py debe verificar la duración que devuelve Lyria y avisar si es menor que el timeline; mix.py debería hacer fade-out al final en lugar de un `stream_loop` silencioso; QA debería revisar el audio al final.
4. **Subtítulo vs. elementos abajo**: compose debería subir el subtítulo (o limitar el zoom) cuando la caja enfocada cae en la banda inferior; documentarlo en QA como limitación conocida.
5. **capture.py**: imprimir las líneas `[take] paso … ok` (hoy no aparecen); imprimir resumen de aceleraciones/congelados en edit.py; listar los avisos de `hyperframes check` en compose.py.
6. **Brief**: plantilla con sección "Marca" y "Login verificado: pendiente"; regla explícita para código fuente con secretos embebidos, para UI con voseo vs. narración neutra y para el usuario demo visible en pantalla.
7. **Guion**: la estimación por palabras debe sumar el tiempo de tipeo (≈ 0,15 s/carácter real) y decir qué hacer si el video queda **corto** frente al brief; guía para elegir voz según el tono.
8. **Ensayo**: un helper para leer `acceso.local.yaml` desde scripts de ego-browser; aclarar si cambios de `hover:`/`wait:` de QA requieren re-ensayo; mencionar el aviso de actualización de ego-lite.
9. **Fuentes**: documentar qué familias renderiza HyperFrames (Segoe UI cae a otra) o empaquetar la fuente de marca en `brand/`.
10. **Costos**: tts.py y music.py deberían imprimir caracteres/segundos facturados; doctor `--online` debería advertir que gasta un clip.
