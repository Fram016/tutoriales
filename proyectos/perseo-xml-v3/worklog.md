# Worklog — perseo-xml-v3 (odd/tasks/perseo-ronda6.md T1–T2, S1–S5; D1–D5, P1 revisada)

## 2026-11-18 — Lectura

- Leídos: skills tutorial, tutorial-guion, tutorial-ensayo-captura, tutorial-qa, ego-browser (+ `ego-browser skill` v2.2.1); `odd/tasks/perseo-ronda6.md` hasta `## Log` (L1–L3); `reglas/reglas-video.md` completo (§Parte 8: D1–D5, P1 revisada; §Parte 6–7: N13–N27, P2–P4); `proyectos/perseo-xml-v2/tutorial.yaml` y su worklog (selectores, reCAPTCHA de recibidos, `manual_fallback`, parche de pestañas).
- Base: `.venv/Scripts/python.exe -m unittest discover -s tests` → 519 OK.

## 2026-11-18 — T1 herramientas (RED → GREEN)

- RED: `tests/test_ronda6.py` (28 pruebas) → 6 errores/22 fallos esperados (`spoken_text`, `measure_loudness`, `check_voice_tone`, `make_download_dirs` inexistentes; acción desconocida `press_visual`/`set_download_dir`; tts enviaba "RIDE"; caché compartido entre videos).
- GREEN:
  - D3 `pronunciation` (common.spoken_text: palabra completa, distingue mayúsculas; validado en common y lint `[D3]`); tts sintetiza el texto hablado, subtítulos con el original.
  - D4 recorder: `press_visual` (evento click `visual: true`, sin clic real), `set_download_dir` (chrome.settingsPrivate get/setPref, espera a que la página muestre la carpeta, evento `result` en `#defaultDownloadPath` sin `target_text`), `restoreDownloadDir` en un `finally` de `take()` (reusa la pestaña de configuración o abre chrome://settings/downloads en el espacio de la toma); `actions.json.download_dir = {changed, restored}` sin rutas. capture.py expande `%VAR%` en Python, crea las carpetas (`mkdir: true`) y solo imprime si se restauró. Dos `follow: tab`/`back: main` en una toma: probado.
  - D5 tts: firma de tanda por video (modelo, voz, estilo, tempo, pronunciación, narraciones en orden) en la clave del caché; cada clip nivelado a −20 LUFS (`level-v1/`). qa: `D5.pitch` (F0 medio por autocorrelación, ±2 st de la mediana) y `D5.loudness` (±3 LU).
  - Pruebas existentes actualizadas por D5 (antes un texto igual en dos videos se sintetizaba una vez; ahora cada video es su tanda): `test_tts` (7→8 llamadas), `test_pace` (tempo nuevo = tanda nueva).
- `.venv/Scripts/python.exe -m unittest discover -s tests` → 547 OK.
- Diferencial de lint (HEAD vs. cambio) en `_demo`, `nexo-crm-contacto-v4`, `perseo-xml`, `perseo-xml-v2`: salida idéntica.

### Fricción
- D5 cambia el caché de voz: correr tts en cualquier proyecto anterior re-sintetiza todos sus clips una vez (costo TTS).

## 2026-11-18 — D4 rediseñado (decisión del padre: opción B, solo visual)

- Ensayo (espacio 74): `chrome.settingsPrivate.setPref('download.default_directory', …)` devuelve `false` incluso con el mismo valor (getPref sí funciona; tipo STRING, no administrada; `download.prompt_for_download` sí se deja cambiar). Chromium solo cambia esa carpeta con el selector nativo, que no se graba.
- Decisión del padre: **solo visual**. `press_visual` en "Change" (cursor y onda, sin clic) y `show_download_dir: {path}` escribe la carpeta en la fila "Location" de chrome://settings/downloads (DOM). **La carpeta real del navegador no cambia**: las descargas de la toma van a la carpeta actual del usuario; el video muestra el resultado que dejaría el selector. No hay nada que restaurar (se quitó la lógica de restauración).
- Pruebas reescritas para `show_download_dir` (26 en `tests/test_ronda6.py`); suite completa verde.
- Ensayo en vivo con la censura: la fila muestra `\Downloads\Perseo XML\Emitidos` y el usuario de Windows difuminado (1 span de censura, `target_text` omitido); captura revisada fuera del repo.
- Fricción: el ensayo de `setPref` creó la carpeta `%USERPROFILE%\Downloads\Perseo XML\Emitidos` (vacía) en el equipo del usuario; no se borró (sin comandos destructivos).
- Fricción: los heredoc de bash reducen `\` a `\` (ya visto en v2): los scripts de ensayo con regex van en archivos escritos con la herramienta de archivos.

## 2026-11-18 — Guion y toma

- `tutorial.yaml`: 15 pasos en 3 partes, conectores D1 («Ingresa a la plataforma del SRI en línea.», «Luego abre Perseo XML.», «Después entra a Facturación Electrónica, Producción y Consultas.», «Ahora cambia la carpeta a Recibidos.», «Luego vuelve con Anterior.», «Por último, …»), D2 en las dos descargas, `pronunciation: {RIDE: "ri de"}`, `max_seconds: 58`, `pace: fast`, `tempo: 1.05`.
- `.venv/Scripts/python.exe tools/lint.py perseo-xml-v3` → exit 0, 2 avisos (N4 «sesión» del requisito literal; P2 apertura ~3,0 s estimada): los mismos que v2.
- Sesión: `sri_login.mjs` una vez en el ensayo → `{loggedIn: true, wasLogin: true}` (credenciales nunca impresas). Espacio 74 cerrado antes de la toma.
- `.venv/Scripts/python.exe tools/capture.py perseo-xml-v3` — 22:51:55–22:54:40, **exit 0, 1.er intento, sin captcha** (no hubo `manual_fallback`): 1297 cuadros (~8,2 fps), 15 pasos, popup 223 cuadros en 4 aperturas, censura por script en las 2 pestañas de configuración. Todos los objetivos `target_ok: true`; `press_visual` con `visual: true` (2); `result` de carpeta con `download_dir: true` sin `target_text` (2). Descargas: emitidos **12 / 0**, recibidos **6 / 0** (a la carpeta actual del usuario).
- Censura revisada en cuadros: `f000018` (perfil), `f000216` (configuración: «\Downloads\Perseo XML\Emitidos», usuario difuminado), `f000906` («…\Recibidos», usuario difuminado), `f000573` (emitidos: clave + 3 montos), `f001124` (recibidos: RUC/razón social + clave + 3 montos, campo RUC).

## 2026-11-18 — Flujo rápido (tts → compose), ajuste de P1 y D5

- `pipeline.py perseo-xml-v3 --from tts --to compose` (1) 22:55:17–22:57:44 exit 0: **62,7 s** (> 58, P1). (2) 22:59:03–23:01:01 exit 0: 62,9 s (probé fundir pasos con narración vacía: no ahorra, se revirtió). (3) 23:01:48–23:03:52 exit 0: 61,3 s (D2 como oración de efecto: «Haz clic en XML desde el RIDE. Transforma los RIDE en XML.», se dice sobre la descarga). (4) 23:04:11–23:06:14 exit 0: 62,6 s (estilo de voz «ágil»: más lento; se quitó). (5) 23:07:00 exit 1: `APIConnectionError` de Gemini (red); (6) 23:07:24–23:09:14 exit 0: **56,6 s** con frases más cortas (P4: «Ingresa a la plataforma del SRI.», «Abre los emitidos.», «Abre los recibidos.», «Llena fecha, establecimiento y punto.»).
- `qa.py --pre` (23:09:23–23:09:57) exit 1: A2.voice_gaps y **D5.pitch FAIL** (clips pedidos uno por uno: 189–259 Hz, −2,6..+2,9 st).
- D5 (herramienta): tts pide **todo el video en una sola solicitud** (una línea por clip) y la corta en sus pausas (`split_points`, programación dinámica por caracteres; si el corte no es confiable, pide cada frase aparte y avisa). Sonda real: 5 líneas → pausas de 0,46–0,69 s entre líneas y una de 0,54 s dentro de la frase de dos oraciones; el corte la salta. Pruebas: `SplitPointsTest` + tts con una solicitud por video (551 OK).
- (7) 23:16:35–23:18:03 exit 0: «una tanda de 16 frases (D5)», **57,3 s**. Tono por clip: mediana 206 Hz, −2,6..+3,3 st (la entonación de frases cortas sube aun dentro de una sola lectura) → qa D5.pitch avisa > ±2 st y falla > ±4 st; volumen −20,0 LUFS en los 16 clips (0,0 LU de dispersión).
- `qa.py --pre` (23:18:42–23:19:20) exit 1: solo **A2.voice_gaps FAIL** (1,6 s tras la carpeta Emitidos, 1,4 s antes de Consultar en emitidos, 2,8 s en la carpeta Recibidos: lo que muestra el clic, sin frase; la música lo cubre); D5.pitch WARN, D5.loudness PASS, P1 57,3 ≤ 58, P4 PASS, N13–N27 PASS.
- 35 capturas revisadas: apertura con logo claro y requisito; «Ingresa a la plataforma del SRI.» sobre el perfil (censurado); popup con «Carpeta de descargas»; configuración antes («\Downloads») y después («\Downloads\Perseo XML\Emitidos», usuario difuminado; `at-15.689s`) y lo mismo con «Recibidos» (`at-41.538s`); clic visual en «Change» (`at-14.547s`, `at-40.397s`); menú FACTURACIÓN ELECTRÓNICA → Producción → Consultas; formulario y tabla de emitidos censurados; «Transforma los RIDE en XML.» sobre el resumen 12/0 (`at-34.851s`); «Quedan listos para Perseo.» sobre 6/0 (`at-56.014s`). En `at-38.446s` el recuadro se desliza del ícono a «Carpeta de descargas» (movimiento N11 de 0,4 s, no es un error). Tras volver de la configuración se ve ~1 s la página del SRI con la insignia «En Perseo XML» (fin del paso).

## 2026-11-18 — Render, QA y entrega

- `pipeline.py perseo-xml-v3 --only render --quality delivery` 23:21:32–23:24:24 exit 0 (171,4 s): `out/perseo-xml-v3-tutorial.mp4`, 1920x1080, 25 fps, **57,36 s**.
- `qa.py perseo-xml-v3` 23:24:31–23:25:11 exit 1: 55 PASS; FAIL **C4.empty_frames** (62 muestras 72–74 % vacío: la configuración de Chrome oscura y casi vacía; mismo conflicto P3↔C4 aceptado en v2) y **A2.voice_gaps** (3 silencios de voz de 1,4–2,8 s, cubiertos por la música; el chequeo A2 del MP4 pasa); WARN N26.mixed (7,63 s: el popup aparece en la mitad superior) y D5.pitch (−2,6..+3,3 st). A1 −14,1 LUFS / −1,9 dBTP, duración 57,36 s (P1 ≤ 58), resolución ok.
- Cuadros del MP4 revisados: 3,4 s «Parte 1: Configurar la carpeta»; 13,3 s configuración antes («\Downloads», usuario difuminado) con «En Change, elige la carpeta Emitidos.»; 15,7 s después («\Downloads\Perseo XML\Emitidos»); 18,0 s «Parte 2: Comprobantes emitidos»; 35,2 s «Transforma los RIDE en XML.» sobre «12 Descargados / 0 Con error»; 36,6 s «Parte 3: Comprobantes recibidos»; 40,6 s onda del clic en «Change» (sin clic real); 42,0 s «…\Perseo XML\Recibidos»; 57,2 s «Quedan listos para Perseo.» sobre «6 Descargados / 0 Con error». Subtítulos de una oración, legibles, en la banda.
- Carpeta del navegador: nunca se cambió (solo visual). Comprobado al final en un espacio nuevo (cerrado): la preferencia no apunta a «Perseo XML» y termina en «\Downloads» (sin imprimir la ruta).
- Suite: `.venv/Scripts/python.exe -m unittest discover -s tests` → 552 OK.
- Costos: Gemini TTS ~7 tandas del video (cambios de texto + la versión de una sola solicitud) + 1 sonda de 5 frases; Lyria 1 pista (≈ USD 0,08).
