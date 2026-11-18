# Worklog: nexo-crm-contacto-v2 (T6, corrida desde cero con las reglas v2)

Agente tutorial nuevo, sin leer `proyectos/nexo-crm-contacto/`. Fecha 2026-11-17, 20:14–21:00 (≈ 46 min de reloj).
Normas: `reglas/reglas-video.md`. Instrucciones del usuario: L8 de `odd/tasks/reglas-video.md`.
Salidas: TUT 16:9 + RED 9:16 desde una sola lista de pasos.

## 0. Skill `tutorial` (entrada)

**Qué dice:** preflight con `doctor.py` (+ `--online`), elegir el tipo antes del guion, brief primero, una toma, lint sin errores ni avisos, pipeline draft, QA con 3 rondas como máximo y render final `delivery`.

**Qué hice:**
- `.venv/Scripts/python.exe tools/doctor.py` → exit 0, 5,2 s, 0 fallas. `doctor.py --online` → exit 0, 8,3 s, Gemini TTS OK (gemini-3.8-flash-tts / Kore).
- Tipo de video: el usuario pidió "tutorial completo en horizontal y un video corto para redes en vertical" → `tutorial` TUT 16:9 `steps: all` + `redes` RED 9:16 (dado, no propuesto).
- Slug `nexo-crm-contacto-v2`; `brand/` creado sin logo.

**Fricción:**
- `doctor.py` imprime "corré con --online" (voseo, L1) en su propia salida.
- ego-browser avisó en cada script de que hay una actualización de Ego Lite (0.6.3.14). No actualicé (hace falta el permiso del usuario).

## 1. Skill `tutorial-brief`

**Qué dice:** copiar `templates/brief.md`, pegar las instrucciones textuales, credenciales solo por nombre, leer el código en modo solo lectura con fuente `(código ruta:línea)`, llenar Tipo de video, Dispositivo, Glosario, Datos de la serie y Flujo (marcar login y campos opcionales para que RED los omita), y verificar el login en ego-browser.

**Qué hice:**
- `brief.md` desde la plantilla, con las instrucciones de L8 tal cual.
- Leí `demo-apps/nexo-crm/index.html` (194 líneas) en modo solo lectura: selectores `#login-email`, `#login-password`, `#btn-login`, `#nav-contactos`, `#btn-nuevo-contacto`, `#c-*`, `#btn-guardar`, `#rows`, `#toast` (el aviso se oculta a los 2,5 s, abajo a la derecha).
- Credenciales: `env:NEXO_CRM_CONTACTO_V2_USER` / `env:NEXO_CRM_CONTACTO_V2_PASSWORD` (ya estaban en `acceso.local.yaml`, que está en gitignore; verifiqué solo los nombres).
- Marca: sin marca entregada → primary `#7c3aed` y background `#1f1235` (los de la app), accent `#ea580c` (naranja: contraste ≥ 3:1 sobre blanco para R3 y legible sobre la etiqueta oscura), fuente Segoe UI, sin logo.
- Glosario: contacto (no: cliente, prospecto, registro), etapa, origen, aviso.
- Datos de la serie: Sofía Vera, Café Montaña, sofia@cafemontana.ec, Origen Feria (cortos, C6).
- Login verificado en ego-browser (TaskSpace 30, script `r01.mjs` en %TEMP%, que lee `acceso.local.yaml` dentro del script y no imprime valores): `{app: true, err: false}`, 1,7 s. Sin 2FA, CAPTCHA ni SSO.

**Fricción:**
- **E2 contra RED3 (campos opcionales).** El brief pide "marcar campos opcionales para que RED pueda omitirlos", y el guion dice que RED los omite "dejando esos pasos fuera de `videos[].steps`", lo que supone un paso separado para los opcionales. Pero el mismo guion dice "llenar un formulario es UN paso", y `lint.py` avisa (E2) si dos pasos seguidos llenan el mismo formulario. Con una sola toma no se pueden cumplir las dos cosas. **Decisión:** un solo paso de formulario (E2 manda, y el error #2 de la Parte 1 lo reclamó el usuario). Para acercarme a RED3, dejé fuera Cargo, Teléfono y Notas en los dos videos: solo se llenan los obligatorios + Empresa + Origen (Origen alimenta el gancho de "feria"). Consecuencia: RED muestra dos campos opcionales.
- **L3 contra los datos de la interfaz.** "Prospecto" y "Cliente" son valores reales del campo Etapa y a la vez sinónimos prohibidos de "contacto". Los dejé fuera de la narración. En pantalla aparecen como valores de la app.
- El brief pide marcar "Login verificado" antes del ensayo completo; lo hice con un ensayo de login aparte en el mismo TaskSpace.
- La cuenta demo muestra su correo en el encabezado y al teclearlo en el login. Es una cuenta demo, pero el skill de QA no dice si eso cuenta como "credenciales reales visibles".

## 2. Skill `tutorial-guion`

**Qué dice:** schema v2, una lista de pasos, `result:` para cada aviso de confirmación, `highlight:` para la fila nueva, apertura ≤ 7 palabras, cierre ≤ 6 palabras, gancho RED ≤ 5 palabras, 2,6 palabras/s, lint sin errores ni avisos.

**Qué hice:** `tutorial.yaml` con 5 pasos (login, contactos, nuevo, datos, guardar). TUT `steps: all`, RED `[nuevo, datos, guardar]` (numeración 3–5), con textos propios para RED. Música: TUT suave, RED rítmica. Voz Kore con estilo "español neutro de Ecuador, trato de tú".
- `tools/lint.py nexo-crm-contacto-v2` → exit 0, "OK (0 avisos)", 0,35 s.

**Fricción:**
- **R2 contra C4 (L7) desde el guion.** El skill y `assets/ejemplo-tut-red.yaml` mandan `result: "#toast"`, pero `proyectos/_demo/tutorial.yaml` hace lo contrario (solo `highlight`) por C4. Seguí el skill (`result: "#toast"`); el conflicto apareció en QA (ver §7).
- El lint estima 2,6 palabras/s y aprobó la apertura y el cierre, pero el TTS real fue mucho más lento en frases cortas (ver §4). El lint no anticipa los avisos que luego da edit.

## 3. Skill `tutorial-ensayo-captura`

**Qué dice:** ensayar cada paso con los mismos selectores, comprobar que focus, result y highlight sean visibles, comprobar que el aviso siga en pantalla, un TaskSpace y `finish({keep: []})`, y luego una toma con `capture.py`.

**Qué hice:**
- Ensayo `r02.mjs` (TaskSpace 30): los 5 pasos con los selectores exactos del yaml. Confirmé `#view-contactos table` (focus), `#toast` (visible 1,2 s después del clic, con la caja 294×50) y `#rows tr:first-child` (clase `new`, texto "Sofía Vera · Café Montaña · …"). Revisé las capturas s4 (formulario) y s5 (lista + aviso).
- `finish({keep: []})` en `r03.mjs` → "finished 30".
- Toma: `tools/capture.py nexo-crm-contacto-v2` → exit 0, 43,6 s, 484 cuadros (~11,3 fps), 5 pasos. Verifiqué que `actions.json` no contenga los valores de credenciales (búsqueda hecha con un script que lee el yaml): ninguno. La contraseña tiene `secret: true`.
- Ningún selector cambió en el ensayo.

**Fricción:**
- El skill dice que capture imprime `[take] paso <id> ok` por paso; en realidad solo imprime el resumen.
- El ensayo corre con el viewport de la ventana de ego (1536×706), no a 1920×1080; el skill no dice que se emule 1080p al ensayar. Las cajas medidas no son las de la toma.
- No hay forma de ensayar el encuadre (dónde caerá la cámara 9:16): los cortes V2 solo se ven después del render.

## 4. Skill `tutorial-voz`

**Qué dice:** `tts.py` online, apertura ≤ 3 s (gancho RED 1–2 s) y cierre ≤ 2,5 s; si no, acortar el texto.

**Qué hice:** TTS online dentro de `pipeline.py --from tts` (47,5 s; TUT 7 clips / 37,5 s de voz, RED 5 clips / 21,7 s). Rondas posteriores: solo se resintetizaron los clips cambiados (la caché funciona: r1 32 s, r2 14 s, r3 5 s).
- Duraciones finales: TUT apertura 2,60 s, cierre 2,44 s; RED gancho 1,84 s, cierre 1,68 s.

**Fricción:**
- **El TTS es lento en frases cortas.** "Siguiente: buscar contactos." (3 palabras) duró 3,08 s; "Siguiente, buscar contactos." 2,48 s; "Siguiente: el buscador." 2,44 s. A esto edit suma lead + tail (≈ 0,3 s), así que el cierre TUT nunca bajó de 2,5 s. Con la regla del lint (el cierre TUT debe decir "siguiente") y este TTS, A2 (≤ 2,5 s) es casi inalcanzable.
- El gancho RED de 3 palabras ("¿Contacto de feria?") da 1,84 s de voz → tarjeta de 2,24 s (> 2 s, RED1).
- Hay un solo `voice.style` por tutorial: no puedo tener TUT calmado y RED enérgico, aunque el skill lo sugiere.

## 5. Skill `tutorial-edicion`

**Qué dice:** edit → music → mix; Lyria ≈ USD 0.08 por pista, se reutiliza; -14 LUFS, pico < -1 dBTP.

**Qué hice:**
- Ronda 0: edit 19 s, TUT 41,7 s y RED 24,5 s. Avisos de edit: apertura TUT 3,4 s, cierre TUT 3,5 s, gancho RED 2,5 s, cierre RED 2,6 s.
- Música Lyria `lyria-3.5`, **una sola vez por video** (2 pistas, 49 s). En las rondas siguientes: "reutilizo music.mp3".
- Mezcla: TUT -14,0 LUFS / -1,8 dBTP; RED -14,0 LUFS / -2,2 dBTP.

**Fricción:** la duración del cierre depende del TTS y no del texto (ver §4). Edit avisa, pero no recorta el silencio inicial ni final del clip.

## 6. Skill `tutorial-render`

**Qué dice:** compose + render draft para iterar; delivery al final; sin logo → pedirlo antes del render final.

**Qué hice:** compose en todas las rondas (`check OK`, 17 avisos en TUT y 23–25 en RED). Render draft 207–339 s por ronda. Final: `pipeline.py --from compose --quality delivery` → exit 0, 317 s.

**Fricción:**
- El skill pide pedir el logo antes del render final; el usuario indicó "No logo", así que rendericé sin logo.
- El skill no dice qué hacer con los avisos de `hyperframes check` (17–25); no los revisé uno por uno.

## 7. Skill `tutorial-qa` (3 rondas)

**Qué dice:** `qa.py`, abrir TODAS las PNG, corregir con `tutorial.yaml` + `pipeline --from` y como máximo 3 rondas.

### Ronda 0 (estado inicial)
`qa.py` → exit 1 (39 s). Fallos:
- TUT C4: 3,40 s 74 % vacío; 30,9–33 s 90–94 % vacío (zoom al aviso solo en la esquina: el conflicto **L7**).
- TUT A2 cierre 3,5 s; RED A2 cierre 2,6 s.

Revisión visual (16 PNG, una por una): aviso en zoom con ~90 % vacío (TUT y RED; en RED, `qa.py` dio C4 PASS aunque la PNG de 16,7 s se ve vacía); en RED las etiquetas de la columna derecha del formulario aparecen cortadas ("Ape", "Carg", "Telé", "Orig"; V2); la fila nueva está cortada a la derecha; el subtítulo "Haz clic en Guardar contacto" sale después del guardado.

### Ronda 1 → `--from capture`
- **Decisión L7 (R2 contra C4):** quité `result: "#toast"` y dejé la fila nueva como resultado (`highlight`, R1/R3), igual que `_demo`. Saqué "Sale el aviso verde" de la narración (O2: no mencionar lo que no se encuadra). Razón: C4 es un FAIL medido por `qa.py` y el aviso solo en una esquina no se puede encuadrar sin vacío; con este cambio R2 queda sin objeto. La decisión final sigue pendiente del usuario (L7).
- Aperturas y cierres más cortos.
- Resultado: pipeline 445 s. `qa.py`: TUT C4 3,00 s 74 % y 30,00 s 87 %; TUT A2 cierre 3,4 s; RED T1 «Completa / los datos obligatorios» (palabra sola).

### Ronda 2 → `--from capture`
- `focus: "#login-form"` (encuadrar la tarjeta completa del login); `wait: "#rows tr.new"` en lugar de `wait: "#toast"` (la cámara va antes a la fila); otra redacción de `datos` en RED (T1); cierre y gancho más cortos.
- Resultado: pipeline 326 s. `qa.py`: TUT C4 3,00 s 73 %, 30,25 s 87 %; TUT A2 cierre 2,8 s; RED sin fallos automáticos.
- Revisión visual con hojas de contacto de las 14 PNG: el login ahora se ve bien encuadrado. Siguen los cortes V2 en RED y el subtítulo atrasado respecto de la acción.

### Ronda 3 → `--from tts`
- Cierre TUT "Siguiente: el buscador." → la tarjeta quedó en 2,7 s (sigue fallando). **Se agotaron las 3 rondas.**

### Final (delivery) + QA
`pipeline.py --from compose --quality delivery` → exit 0; `qa.py` → exit 1. Abrí una por una las 14 PNG de `qa-05`. Además extraje con ffmpeg cuadros de los clics (C3) y de las transiciones (C4) que las snapshots no cubren.

## Salidas finales

| Video | Ruta | Tipo | Formato | Duración | LUFS | Pico real |
| --- | --- | --- | --- | --- | --- | --- |
| tutorial | `proyectos/nexo-crm-contacto-v2/out/nexo-crm-contacto-v2-tutorial.mp4` | TUT | 16:9, 1920×1080, h264 30 fps + aac 48 kHz | 39,17 s | -14,0 | -2,0 dBTP |
| redes | `proyectos/nexo-crm-contacto-v2/out/nexo-crm-contacto-v2-redes.mp4` | RED | 9:16, 1080×1920, h264 30 fps + aac 48 kHz | 21,50 s | -13,9 | -2,3 dBTP |

Voz: Gemini TTS online (Kore). Música: Lyria `lyria-3.5`, una pista por video, generada una sola vez. No quedan clips offline ni música de relleno.

## Tabla QA final (`qa.py`, delivery)

| Regla / chequeo | tutorial | redes |
| --- | --- | --- |
| S3 resolución / duración / audio | PASS | PASS |
| A1 loudness / true peak | PASS (-14,0 / -2,0) | PASS (-13,9 / -2,3) |
| A2 silencio / pausas de voz | PASS | PASS |
| **A2 tarjeta de cierre** | **FAIL 2,7 s** | PASS 2,0 s |
| **C4 fotogramas vacíos** | **FAIL 3,00 s 73 %; 30,25 s 87 %** | PASS (auto) / **WARN visual: transiciones de ~0,3 s en 3,1 s y 14,6 s** |
| TUT2 / RED2-V5 duración | PASS 39,2 s | PASS 21,5 s |
| E3/TUT3 capítulos | PASS | PASS |
| O1 posición y estilo de la etiqueta | PASS | PASS |
| O2 subtítulo sobre elemento activo | PASS | PASS |
| R1 / R2 | PASS (0 resultados: vacuo) | PASS (0 resultados: vacuo) |
| T1 líneas / duración / última palabra / paso | PASS | PASS |
| T2 letra | PASS 44 px | PASS 48 px |
| C1 / C5 | PASS | PASS |
| V1 / V3 / V4 | — | PASS |
| **V2 (no lo chequea `qa.py`)** | — | **FAIL visual**: etiquetas "Apellido/Cargo/Teléfono/Origen" y la fila nueva cortadas en el borde derecho |
| L1–L4 subtítulos | PASS | PASS |

## Checklist de los 26 errores de la Parte 1

| # | Regla | Estado | Evidencia |
| --- | --- | --- | --- |
| 1 | E1 | corregido | TUT "Aquí aprendes a crear contactos." + tarjeta "Aprende a crear un contacto"; RED gancho "¿Contacto de feria?" + "¿Conociste a alguien en una feria?" (PNG 1,5 s / 1,12 s) |
| 2 | E2 | corregido | una lista; TUT pasos 1–5, RED 3–5; el formulario es un solo paso |
| 3 | C3 | corregido | cuadros TUT 16,3 s y 29,9 s, RED 2,6 s y 13,9–14,4 s: el botón está completo antes del clic |
| 4 | C4 | **sigue (reducido)** | TUT FAIL 3,00 s 73 % (login escaso) y 30,25 s 87 % (cámara atrasada tras el cambio de página); RED: transiciones de ~0,3 s casi vacías (3,1 s y 14,6 s) |
| 5 | C2 | corregido | sin campos duplicados ni fragmentos en las PNG ni en los cuadros extraídos |
| 6 | C1 | corregido | `qa.py` C1 PASS (contexto ≤ 1 s) |
| 7 | C5 | corregido | `qa.py` C5 PASS 48 px; se ve igual en todos los zooms |
| 8 | O1 | corregido | etiqueta pegada al bloque de subtítulo, lejos del logo y del menú; contraste ≥ 4,5:1 |
| 9 | O1 | corregido | opacidad 100 % (`qa.py` + visual) |
| 10 | O2, R2 | no aplica | el aviso ya no se encuadra (decisión L7); R2 queda sin objeto |
| 11 | O2 | corregido | en el paso 4 el subtítulo solo tapa Notas, que no se menciona (TUT 24,75 s, RED 10,37 s) |
| 12 | T1 | corregido | `qa.py` T1 PASS tras la ronda 1 |
| 13 | O3 | corregido | mismo estilo de etiqueta y subtítulo en TUT y RED |
| 14 | R3 | corregido | contorno naranja con brillo, bien visible (TUT 31,4 s, RED 15,3 s) |
| 15 | C6 | no aplica | no se teclean notas; el texto más largo tiene 20 caracteres |
| 16 | A2 | **sigue (TUT)** | sin silencios > 1 s, pero la tarjeta de cierre TUT dura 2,7 s (> 2,5); RED 2,0 s PASS |
| 17 | T3 | corregido | "Nexo CRM" en una línea en el título |
| 18 | E1 | corregido | TUT "Siguiente video: buscar un contacto"; RED "Mira el tutorial completo" |
| 19 | L1 | corregido | la app dice "Ingresa con tu cuenta"; narración y subtítulos en tú |
| 20 | L2 | corregido | solo "haz clic" |
| 21 | L3 | corregido | solo "contacto"; "Prospecto"/"Cliente" aparecen como valores de Etapa en la app, no en la narración |
| 22 | V1 | corregido | recorte real; la interfaz ocupa ~85 % del alto (`qa.py` 100 %) |
| 23 | V2 | **sigue** | en RED, las etiquetas de la columna derecha y la fila nueva quedan cortadas en el borde (PNG 4,57 s, 10,37 s, 15,26 s) |
| 24 | V3 | corregido | título solo en la apertura |
| 25 | V4 | corregido | título centrado; subtítulos entre 288 y 1536 px |
| 26 | V5, RED3 | corregido | RED sin login ni navegación, 21,5 s |

**Totales:** 21 corregidos, 3 siguen (#4 C4, #16 A2 en TUT, #23 V2 en RED) y 2 no aplican (#10, #15).

## Tiempo y costo por etapa

| Etapa | Tiempo | Costo |
| --- | --- | --- |
| Preflight + lectura de skills y reglas | ~1 min | 0 (doctor --online: 1 llamada TTS mínima) |
| Brief + login verificado | ~2 min | 0 |
| Guion + lint | ~1 min | 0 |
| Ensayo (ego) | ~1 min | 0 |
| Toma (×3: inicial, r1, r2) | 44 s + 48 s + 43 s | 0 |
| TTS online (r0 + r1 + r2 + r3) | 47 + 32 + 14 + 5 s | 23 clips, ≈ 1.297 caracteres (786 + 350 + 138 + 23), facturado por carácter |
| Edit | 19 + 31 + 18 + 17 s | 0 |
| Música Lyria | 49 s (una vez) | 2 pistas ≈ USD 0,16 |
| Mix | 20 + 10 + 6 + 5 s | 0 |
| Compose + render draft (×4) | ≈ 400 + 324 + 245 + 242 s | 0 |
| Compose + render delivery | 317 s | 0 |
| QA (×5) | ≈ 40 s cada uno + revisión visual | 0 |
| **Total** | **≈ 46 min** | **≈ USD 0,16 de Lyria + TTS por ~1,3 k caracteres** |

## Propuestas (por prioridad)

1. **Resolver L7 en la regla y en los skills (R2 contra C4).** El guion y el ejemplo piden `result: #toast`, y `_demo` y QA lo prohíben en la práctica. Propuesta: que compose encuadre el aviso **junto con** el elemento nuevo (encuadre compuesto) o con un zoom menor cuando el aviso esté solo. Mientras tanto, el skill de guion debería decir "aviso en una esquina vacía → usar la fila como `result`".
2. **`qa.py` debe chequear V2** (cajas de los elementos activos o mencionados recortadas por el borde en 9:16) y no dar PASS a R1/R2 con "0 resultados" cuando el paso tiene `highlight`/`wait` de confirmación. Además, C4 debería muestrear las transiciones de cámara tras un cambio de página (RED pasó con cuadros casi vacíos).
3. **Compose 9:16 con formularios de 2 columnas:** cuando el foco es un campo, encuadrar la fila completa (las dos columnas) o reducir la escala por debajo de 1,78; hoy corta "Apellido/Origen" y la fila nueva (V2).
4. **Tarjetas y TTS:** recortar el silencio inicial y final de cada clip (tts o edit) y no sumar lead + tail a la tarjeta de cierre; o subir el lint a una estimación real (~1,8 palabras/s + 0,6 s fijos) para que avise antes. Hoy A2 ≤ 2,5 s con "Siguiente…" no se puede cumplir.
5. **Sincronía voz-acción:** edit debería poder retrasar el clic hasta que la voz nombra el botón (p. ej. `click` después de N palabras, o `lead` configurable). Hoy "Haz clic en Guardar contacto" se oye cuando la fila ya está resaltada, y en RED "haz clic en Nuevo contacto" aparece sobre el formulario ya abierto.
6. **Cámara tras un cambio de página:** si el siguiente evento es `highlight`/`result` en otra pantalla, moverse en cuanto aparece la página nueva (o cortar los cuadros intermedios); hoy hay ~0,3–0,5 s casi vacíos (C4).
7. **Contradicción E2 / RED3 en los skills:** decir explícitamente cómo omitir campos opcionales en RED con una sola toma (p. ej. `videos[].skip_actions` o permitir el paso "detalles opcionales" sin aviso E2 cuando lleva `optional: true`).
8. Skill de ensayo: emular 1920×1080 en el ensayo (o decir que las cajas no coinciden), y corregir la afirmación de que capture imprime `[take] paso <id> ok`.
9. Voz: permitir `videos[].voice.style` (TUT calmado, RED enérgico), como ya sugiere el skill.
10. Snapshots de QA: incluir el instante previo a cada clic (C3) y las transiciones; los tiempos de las PNG se repiten entre rondas y no cubren esos momentos.
11. Detalles: `doctor.py` dice "corré" (voseo); aclarar en QA si el correo de una cuenta demo visible en pantalla cuenta como "credenciales"; el glosario choca con los valores literales de la interfaz (Etapa: Prospecto/Cliente) → permitir excepciones citadas entre comillas o por etiqueta de la interfaz.
