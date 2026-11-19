# Worklog — perseo-xml-v4 (odd/tasks/perseo-instalacion.md T1–T3, S1–S4; I1–I3, P1 revisada 2)

## 2026-11-19 — Lectura

- Leídos: skills tutorial, tutorial-guion, tutorial-ensayo-captura, tutorial-qa, ego-browser (+ `ego-browser skill` v2.2.1); `odd/tasks/perseo-instalacion.md` hasta `## Log` (L1–L2); `reglas/reglas-video.md` completo (§Parte 9: I1–I3; §Parte 6–8: N13–N27, P2–P4, D1–D5); `proyectos/perseo-xml-v3/{tutorial.yaml, worklog.md, edit/tutorial/timeline.json}` (video aprobado: 57,35 s, 15 pasos, 3 partes).
- Base: `.venv/Scripts/python.exe -m unittest discover -s tests` → 552 OK (dato del padre).

## 2026-11-19 — T1 herramientas (RED → GREEN)

- RED: `tests/test_ronda7.py` (23 pruebas) → 22 fallas/errores esperados (`merge_takes` sin implementar, acciones desconocidas `show_text`/`simulate_dialog`/`remove_dialog`, contexto `chrome`, `hide`, `take_config`, `keep_previous_take(out_dir=)`); la de PRESERVE (toma sin `hide`) pasó.
- GREEN:
  - common: acciones `show_text {sel, text}`, `simulate_dialog {title, body?, buttons, primary?, anchor?, icon?}`, `remove_dialog: true` (abrir/cerrar en orden), `hide: [CSS]` arriba, contexto `chrome` (N17); `load_tutorial(slug, file)`.
  - compose: insignia «En Chrome».
  - capture.py: `--config install.yaml --out takes/install` (`take_config`), el ícono del diálogo como data URL, `hide` al grabador; `keep_previous_take(out_dir=)`.
  - recorder: `show_text` (solo visual, evento `result` con `show_text: true`, sin `target_text` si coincide con la censura), `simulate_dialog` (tarjeta tipo Chrome arriba al centro, botones `#sim-btn-N`, evento `result` con `simulated: true`), `remove_dialog`, `take({hide})`.
  - `tools/merge_takes.py` (I3): cuadros con prefijo por toma, tiempos desplazados (fin de la toma anterior + 0,2 s), ids únicos, superficies y regiones de censura desplazadas, idempotente, las tomas fuente solo se leen.
  - `tests/test_schema.py`: el mensaje N17 ahora nombra `chrome` (cambio intencional).
- Suite: 575 OK. Diferencial de lint (HEAD vs. cambio) en `_demo`, `nexo-crm-contacto-v4`, `perseo-xml`, `perseo-xml-v2`, `perseo-xml-v3`: salida y exit idénticos.

## 2026-11-19 — Ensayo de la instalación (espacio 77)

- Google (`hl=es-419`) sin página de «tráfico inusual»: se usa Google → «Chrome Web Store» → la tienda → «Perseo XML» → ficha `nggkmolkfkhfdjgbclinjcojpikldbhp`.
- La tienda muestra «Agregar a ego» y el aviso «Cambia a ego para instalar extensiones y temas» (`.gSrP5d`, con un botón «Instalar Chrome»): oculto con `hide` (I2).
- Fricción 1: el framework de la tienda vuelve a poner su texto en la etiqueta del botón; reescribir el nodo de texto con un MutationObserver colgó la página (pelea infinita). Solución: `relabel` oculta la etiqueta original y agrega una hermana con su clase (`[data-tutorial-text]`); reaplicación acotada (≤ 10). Selector del botón ya rotulado: `button:has([data-tutorial-text])`.
- Fricción 2: Google aplica Trusted Types: `insertAdjacentHTML` falla. El diálogo se arma con `createElement` desde un árbol declarativo (`dialogTree`).
- Censura: avatar de la cuenta (`a[href*="accounts.google.com/SignOutOptions"]`) y el saludo de la tienda con el nombre del perfil (`h2.tCQDwe`: nombre y texto son dos nodos, un patrón de texto no lo alcanza).
- Toma de ensayo (fuera del repo): 6 pasos, 355 cuadros, todos los objetivos `target_ok: true`; «Agregar a Chrome» y el diálogo verificados en cuadros. El clic real en «Agregar a ego» nunca se hizo (solo `press_visual`).
- Pendiente visual: «Quitar de Chrome» queda con el estilo azul del botón original (en Chrome es un botón con borde); `show_text` cambia solo el texto.

## 2026-11-19 — T2 toma de instalación

- (1) `capture.py perseo-xml-v4 --config install.yaml --out takes/install` 08:42:11–08:42:40 exit 0 (323 cuadros): **descartada**. Al enfocar la caja de Google se ve el desplegable con el **historial de búsquedas del perfil** (dato personal). Quedó movida a `takes/install.prev-20261119-084338/` (no se borró: sin comandos destructivos; hay que eliminarla, contiene ese historial).
- Corrección: `hide` agrega `[jsname="UUbT9"]` (desplegable de Google); verificado en vivo (sin desplegable al escribir).
- (2) misma orden 08:43:38–08:44:08 **exit 0**: 304 cuadros (~10,8 fps), 6 pasos, todos los objetivos `target_ok: true`. Revisados 30 cuadros (uno por segundo): Google sin desplegable, avatar difuminado en Google y la tienda, saludo con el nombre difuminado, sugerencias de la tienda solo del catálogo («Custom Cursor…», «Perseo XML»), ficha sin el aviso de ego, «Agregar a Chrome», diálogo «¿Quieres agregar "Perseo XML"?» con «Agregar extensión»/«Cancelar», «Quitar de Chrome». Google usado (sin captcha).

## 2026-11-19 — T3 unión, guion y flujo rápido

- `tools/merge_takes.py proyectos/perseo-xml-v4 proyectos/perseo-xml-v4/takes/install proyectos/perseo-xml-v3/capture` 08:44:40–08:44:43 exit 0: 1601 cuadros, 21 pasos, 186,8 s de toma; `perseo-xml-v3/` sin cambios (`git status`).
- `tutorial.yaml`: v3 copiado (censura, superficie, pronunciación, voz por defecto, estilo, tempo 1,05, `pace: fast`, paleta, música); Parte 1 «Instalar la extensión» antepuesta, partes 2–4 renumeradas, sin `max_seconds` (S3). Conectores D1: «Primero, busca Chrome Web Store en Google.» → «Luego entra a la Chrome Web Store.» → «Después busca Perseo XML.» → «Elige Perseo XML en los resultados.» → «Haz clic en Agregar a Chrome.» → «Confirma con Agregar extensión. La extensión queda instalada.» → «Ahora ingresa a la plataforma del SRI.» (único cambio de texto de v3) → resto de v3 igual. Apertura «Aprendes a instalar y usar Perseo XML.» + «Necesitas Google Chrome y tu cuenta del SRI.». Lint exit 0 (avisos N4, P2 como v3).
- `pipeline.py perseo-xml-v4 --from tts --to compose` 08:44:47–08:47:23 exit 0 (154,9 s): «una tanda de 22 frases (D5)», 52,2 s de voz, **77,4 s** en total; música Lyria nueva (1 pista); mezcla −14,1 LUFS / −1,9 dBTP.
- `qa.py --pre` ronda 1 (08:47:28–08:48:20) exit 1: A2.voice_gaps FAIL (3 silencios heredados de v3 + 1,6 s tras «confirmar»), N12.form_fields FAIL (el empuje C8 del plano del formulario de Google, de 1728 px de ancho, lo sacaba del cuadro), N14.named FAIL (falso positivo: «Perseo» se toma como el popup; en la tienda es la búsqueda/la ficha), D5.pitch WARN. 44 capturas revisadas.
- Correcciones (RED → GREEN, `tests/test_ronda7.py` 27 pruebas): compose: el empuje de un formulario que entra a lo ancho lo mantiene entero (N12); qa: en un paso `context: chrome` «Perseo» pide revisión visual (WARN), fuera de él sigue exigiendo el popup. Suite 579 OK; diferencial en memoria (compose.plan + N14 de v2 y v3, HEAD vs. cambio): idéntico.
- `pipeline.py --from compose --to compose` exit 0 (33,6 s); `qa.py --pre` ronda 2 (→ 08:53:23) exit 1: solo A2.voice_gaps FAIL (aceptado como en v3, la música lo cubre), D5.pitch WARN (−3,1..+3,9 st, mediana 190 Hz; < ±4 st), N14.named WARN (verificado en capturas: «Pe…»/«Perseo XML» escrito en la caja y la tarjeta «Perseo XML» en pantalla). Única captura distinta: `at-6.229s` (Google, ya sin recorte del formulario).

## 2026-11-19 — Render único, QA del MP4 y defectos encontrados

- `pipeline.py perseo-xml-v4 --only render --quality delivery` 08:55:56–09:00:45 exit 0 (287,9 s): `out/perseo-xml-v4-tutorial.mp4`, 1920x1080, **77,44 s**.
- `qa.py perseo-xml-v4` 09:00:53–09:01:54 exit 1: 53 PASS; FAIL C4.empty_frames (64 muestras: 8 en la portada de Google 5,17–6,92 s, el resto las mismas pantallas de v3: configuración de Chrome y formularios del SRI, aceptadas en v3), FAIL A2.voice_gaps (los 3 de v3 + 1,6 s tras «confirmar»); WARN N26.mixed (28,53 s, 30,53 s), D5.pitch, N14.named. A1 −14,1 LUFS / −1,8 dBTP; D5.loudness 0,0 LU.
- Revisión visual del MP4 (28 cuadros): **defectos en la Parte 1** → el MP4 entregado NO es final:
  1. 16,6–16,9 s: la ficha muestra «Agregar a ego» antes del rótulo (I2).
  2. 8,2 s: tras Enter, el recuadro de la caja de Google queda sobre la página de resultados (zona vacía).
  3. 23,9 s: el recuadro del clic en «Agregar extensión» queda sobre la página al quitar el diálogo.
- Correcciones (RED → GREEN): `show_text {watch: true}` (observador del documento: rotula el botón al insertarse, antes de pintar; la tienda abre la ficha en el mismo documento, verificado); clic en «Buscar con Google» en vez de Enter; `pause: 900` antes de `remove_dialog`. Toma (3) 09:06:15–09:06:43 exit 0; unión; `pipeline --from tts --to compose` exit 0 (tts en caché, 91 s); `qa --pre` ronda 3 exit 1 (A2 FAIL conocido; D5, N14 WARN). Capturas de la ronda 3: nuevo defecto 4: a 7,35 s y 10,61 s el recuadro del clic queda sobre la pantalla nueva: ego devuelve el clic solo después de una navegación rápida (Google, la tienda) y edit no encontraba el cambio de pantalla (`screen_at` nulo).
- Corrección (RED → GREEN): el grabador registra `t_down` (antes de enviar) en click/goto/press; edit usa `t_down` solo si no hay cambio de pantalla después del tiempo registrado (capturas viejas sin `t_down`: sin cambios; diferencial sobre la toma de v3: idéntico); merge_takes desplaza `t_down`. Suite 583 OK.
- Toma (4) 09:15:35 exit 0 (336 cuadros, `t_down` en los clics); revisada: sin «ego» desde el primer cuadro pintado de la ficha, sin desplegable de Google, avatar y saludo difuminados. Unión 09:16:19 exit 0 (1633 cuadros).
- **Detenido aquí**: correr tts→compose + `qa --pre` sobre la toma (4) sería la 4.ª ronda PRE y exige un 2.º render; ambos fuera del límite autorizado (3 rondas, un render). Estado: `capture/` = toma (4) unida; `edit/`, `hf-tutorial/` = toma (3); `out/perseo-xml-v4-tutorial.mp4` = toma (2), con los defectos 1–4.
- Tomas previas: la (1) (con el historial de Google) la borró la poda de `capture.keep_previous_take` (KEEP_PREVIOUS=2); quedan `takes/install.prev-20261119-090615` y `-091536` (sin datos personales). `takes/` no está en `.gitignore`.
