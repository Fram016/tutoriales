# Worklog — nexo-crm-contacto-v3 (T6, odd/tasks/reglas-ronda2.md, S3)

Agente desde cero (no se leyeron `proyectos/nexo-crm-contacto/` ni `-v2/`). Instrucciones del usuario: Log L8 de `odd/tasks/reglas-video.md` (pegadas textuales en `brief.md`). Reglas: `reglas/reglas-video.md` (Parte 1–4).
Inicio: **22:37:05**. Fin del pipeline (qa MP4): **23:05:19**. Fin del trabajo (worklog): **23:07:41**.

## 1. `tutorial` (entrada) + preflight

- Dijo: decidir tipo (TUT 16:9 + RED 9:16, el vertical es RED), brief primero, doctor, FAST WORKFLOW (`--to compose` → `qa.py --pre` + snapshots, máx. 3 rondas → UN render delivery → `qa.py` → re-render solo del video que falle).
- Hice: leí los 8 skills + `ego-browser skill` (guía v2.2.1 completa), `reglas-ronda2.md` hasta `## Log`, `reglas-video.md` completo, L8.
- `tools/doctor.py --online` → exit 0, 0 fallas, 9,1 s (Gemini TTS OK).
- Fricción: ninguna.

## 2. `tutorial-brief` (22:37:47 → 22:38:40)

- Dijo: plantilla `templates/brief.md`; paleta extraída de la app (N5), historia (N4), destino del CTA (N8, si no se sabe: "en el enlace de nuestro perfil", propuesto), credenciales solo por nombre, verificar login en ensayo.
- Hice: leí `demo-apps/nexo-crm/index.html` (solo lectura). Paleta: primary `#7c3aed` (`--brand`, :7/:15), background/surface `#4c1d95` (inicio del degradado del hero, :21), on_surface `#ffffff`, fuente "Segoe UI". Historia: "conociste a una persona en una feria" → Origen "Feria", nota "Conocida en la feria Expo" (25 car.). Datos de la serie: Sofía Vera, Café Andino. Glosario: contacto (no: cliente, prospecto, registro). Credenciales: `NEXO_CRM_CONTACTO_V3_USER` / `NEXO_CRM_CONTACTO_V3_PASSWORD` (ya estaban en `acceso.local.yaml`; solo se leyeron los nombres de las claves).
- Preguntas abiertas: destino del CTA (propuesto), logo (no hay), siguiente video ("buscar un contacto", propuesto).
- Fricción: el código fuente de la app contiene la cuenta demo en claro (`DEMO = {...}`); no se copió a ningún lado. Para `surface` elegí el violeta oscuro del hero y no el `#1f1235` del menú lateral (casi negro) porque la observación de Parte 4 pide evitar cajas negras; la plantilla no dice cuál de los oscuros elegir.

## 3. `tutorial-guion` (22:38:40 → 22:39:30)

- Dijo: schema v2, un formulario = un paso (E2), `omit` para RED, N1 instrucción primero, N2 apertura distinta del título, presupuesto de palabras.
- Hice: 5 pasos (`login`, `contactos`, `nuevo`, `datos`, `guardar`); `tutorial` TUT `steps: all`; `redes` RED `steps: [nuevo, datos, guardar]`, `omit` de campos opcionales.
- `lint.py` #1 → exit 1: `[TUT1] videos.tutorial.opening: tiene que decir el objetivo («En este video aprendes a…»)` + aviso `[RED2] ~15 s`. Corregí: título "Nexo CRM · Contactos" (dónde) y voz "Aprendes a registrar contactos." (qué), para no repetir la idea (N2); RED `nuevo` más largo.
- `lint.py` #2 → exit 0, 0 avisos.
- Fricción: TUT1 exige "aprendes a…" y N2 prohíbe que la apertura repita el título; con el título por defecto "Cómo crear un contacto…" ambas reglas chocan. Hubo que cambiar el título a un rótulo de lugar.

## 4. `tutorial-ensayo-captura` (22:39:35 → 22:40:45)

- Ensayo: un task space ego-browser ("ensayo nexo-crm-contacto-v3", id 36), script `.mjs` fuera del repo; credenciales leídas dentro del script solo en el paso de login, nunca impresas. Todos los selectores confirmados con caja visible: `#login-*`, `#nav-contactos`, `#btn-nuevo-contacto`, `#c-*` + `label[for]`, `#btn-guardar`, `#toast` (sigue visible a 1,2 s), `#rows tr:first-child` (clase `new`). Login verificado. 7,1 s.
- `finish({ keep: [] })`: el primer intento falló (busqué el id por nombre con un script mal citado); a las 22:43 `taskSpace(36).finish({ keep: [] })` → "finished 36". ego-browser avisó de una actualización de Ego Lite disponible: no se actualizó (requiere permiso del usuario).
- Toma: `capture.py` → `ok: 715 cuadros (~13.2 fps), 5 pasos`, 55,2 s.
- Fricción: el ensayo no detecta problemas de encuadre (p. ej. `focus: "#rows"` más ancho que un plano de detalle); se ve recién en `qa.py --pre`.

## 5. FAST WORKFLOW: `pipeline --from tts --to compose` + `qa.py --pre` (rondas)

### Intento 0 (perdido) 22:40:50 → 22:50:20
- `pipeline.py --from tts --to compose` lanzado con el timeout por defecto de mi herramienta de shell (120 s): el proceso murió a las 22:42:50 tras tts + edit + música del tutorial. Sin salida visible, interpreté que seguía en segundo plano y esperé sondeando 7,5 min. **Error mío: ~9,5 min perdidos.**
- 22:50:42 reintento → `music` falló: Lyria `400 recitation` ("Request blocked due to copyright/recitation content") con el prompt RED "Upbeat rhythmic pop, punchy drums, bright synths, energetic". Cambié el prompt a "Original rhythmic electronic groove, light claps, warm synth bass, bright plucks, energetic".

### Ronda 1 (22:51:31 → 22:55:30)
- `pipeline` exit 0 en 66,5 s: tts 0,5 | edit 13,8 | music 25,2 (Lyria redes) | mix 3,8 | compose 23,2. Mezcla: tutorial −14,0 LUFS / −2,2 dBTP; redes −14,0 / −1,8.
- `qa.py --pre` (≈25 s) FAIL:
  - tutorial A2 silencios 1,2 s (opening→login, login→contactos); C9 `#rows` 2204 px de ancho fuera del encuadre.
  - redes A2 silencios 2,0/2,0/1,3 s; C1 9,10–12,54 s a 1,31× (la nota de ancho completo en 9:16); N1 `datos` 0,7 s tarde; R2/N6 aviso 0,6 s limpio.
- Snapshots revisados: 13/21 TUT y 9/13 RED. Hallazgos visuales: RED corta campos a la derecha ("Ape", "Carg", "Telé", "Orig"), la fila resaltada en RED casi no se ve (0,25 s encuadrada, regresión de "Lo que sí funciona"), en RED aparecen ya llenos los campos omitidos.
- Cambios: login + "Llegas al Inicio."; contactos `focus: "#buscar"` + "Aquí ves tu lista y el buscador." (el usuario menciona el buscador); RED `omit` + `#c-notas`; narraciones RED más largas (nuevo, datos en dos frases, guardar).

### Ronda 2 (22:55:33 → 22:58:55) — recaptura (cambió una acción)
- `pipeline --from capture --to compose` exit 0 en 117,9 s: capture 55,0 | tts 17,5 | edit 16,8 | music 0,2 | mix 4,5 | compose 23,9.
- `qa.py --pre`: tutorial **PASS**; redes solo R2.result_clear y N6.result (0,60 s).
- Snapshots revisados: 15/21 TUT, 10/11 RED (el resto, tramos sin cambios ya revisados en ronda 1). La fila nueva en RED seguía sin verse (cámara 0,25 s).
- Cambio: RED `guardar` → "Haz clic en Guardar contacto. Sale el aviso y tu contacto queda primero, resaltado." (alarga el paso: la fila queda encuadrada 1,9 s).

### Ronda 3 (22:58:59 → 22:59:38) — solo `--video redes`
- `pipeline --from tts --to compose --video redes` exit 0 en 27,2 s (tts 6,2 | edit 10,1 | music 0,1 | mix 1,4 | compose 9,3). RED 18,6 s.
- `qa.py --pre --video redes`: solo R2/N6 (igual que antes). Layout: highlight 14,26–17,07 s, cámara en la fila 15,16–17,07 s.
- Se agotaron las 3 rondas. R2/N6 RED no se puede arreglar desde la entrada (ver Fricción): se pasó al render.

## 6. `tutorial-render` (22:59:51 → 23:04:47)

- `pipeline.py --only render --quality delivery` exit 0: redes 237 s y tutorial 296 s **en paralelo** (6 workers c/u) → total 295,8 s. Renders usados: **1** (sin re-render).

## 7. `tutorial-qa` MP4 (23:04:53 → 23:05:19) + verificación visual

- `qa.py nexo-crm-contacto-v3` FAIL (ver tablas). Extraje fotogramas del MP4 con ffmpeg a un directorio temporal: redes 15,6 s y 16,5 s (fila "Sofía Vera" resaltada en morado, bien visible) y tutorial 37,5 s (fila resaltada + banda).
- No re-renderé: los dos FAIL que quedan (C4 TUT 33,34–33,59 s y R2/N6 RED) son defectos de composición/edición, no de entrada; re-renderizar daría el mismo MP4.

## Tiempos (reloj de pared)

| Etapa | Inicio–fin | Duración |
| --- | --- | --- |
| Lectura de skills/reglas + doctor | 22:37:05–22:37:47 | 0,7 min |
| Brief | 22:37:47–22:38:40 | 0,9 min |
| Guion + lint ×2 | 22:38:40–22:39:30 | 0,8 min |
| Ensayo ego-browser | 22:39:35–22:39:42 | 0,1 min |
| Captura #1 | 22:39:49–22:40:45 | 0,9 min |
| Intento 0 (timeout de mi shell + espera) | 22:40:50–22:50:20 | **9,5 min (desperdicio)** |
| Reintento con Lyria bloqueado | 22:50:42–22:51:23 | 0,7 min |
| Ronda 1 (tts→compose + qa --pre + revisión) | 22:51:31–22:55:30 | 4,0 min |
| Ronda 2 (capture→compose + qa --pre + revisión) | 22:55:33–22:58:55 | 3,4 min |
| Ronda 3 (redes tts→compose + qa --pre) | 22:58:59–22:59:38 | 0,7 min |
| Render delivery (2 en paralelo) | 22:59:51–23:04:47 | **4,9 min** |
| qa MP4 + fotogramas | 23:04:53–23:06:00 | 1,1 min |
| **Total pipeline** (captura → qa MP4) | 22:39:49–23:05:19 | **25,5 min** (≈16 min sin el intento 0) |
| **Total de pared** (inicio → worklog) | 22:37:05–23:07:41 | **30,6 min** |

Presupuesto 10–12 min: **no cumplido**. Las etapas más lentas: render (4,9 min, 1 sola vez), el intento perdido (9,5 min, error de operación), dos capturas (55 s c/u) y la revisión de ~60 snapshots en 3 rondas.

## Salidas finales

| Video | Ruta | Tipo | Formato | Duración | LUFS / pico | Pasos |
| --- | --- | --- | --- | --- | --- | --- |
| tutorial | `proyectos/nexo-crm-contacto-v3/out/nexo-crm-contacto-v3-tutorial.mp4` | TUT | 16:9, 1920×1080, h264+aac | 40,73 s | −14,1 LUFS / −2,1 dBTP | 1–5 |
| redes | `proyectos/nexo-crm-contacto-v3/out/nexo-crm-contacto-v3-redes.mp4` | RED | 9:16, 1080×1920, h264+aac | 18,60 s | −13,9 LUFS / −1,7 dBTP | 3, 4, 5 (sin números) |

Voz: Gemini TTS (voz/estilo por defecto de `.env`), clips re-sintetizados solo al cambiar el texto. Música: Lyria, una pista por video (tutorial "Soft corporate ambient…", redes "Original rhythmic electronic groove…"). Costo: 2 pistas Lyria ≈ USD 0,16 (+1 solicitud bloqueada por "recitation") + TTS de ~12 clips iniciales y 6 re-sintetizados.

## QA final

### `qa.py --pre` (ronda 3)

| Video | Resultado | Fallas |
| --- | --- | --- |
| tutorial | PASS | — |
| redes | FAIL | R2.result_clear (0,60 s limpio < 0,8 s), N6.result (aviso encuadrado 0,60 s) |

### `qa.py` MP4 (`qa/<id>.json`)

| Video | Resolución | Duración | A1 | C4 | Otras |
| --- | --- | --- | --- | --- | --- |
| tutorial | PASS | PASS (40,73 ±0,3) | PASS (−14,1 / −2,1) | **FAIL** 33,34 s 85 % vacío; 33,59 s 84 % | N6 PASS, T1 PASS |
| redes | PASS | PASS (18,60) | PASS (−13,9 / −1,7) | PASS | **R2, N6 FAIL** (como en --pre) |

Veredicto visual: TUT aprobado salvo ~0,4 s casi vacío tras el clic en Guardar (la pantalla cambia antes de que la cámara corte al aviso). RED: aviso y fila resaltada visibles; quedan campos cortados en el borde derecho (V2/C9 visual) y el área del aviso con mucho vacío.

## Checklist §Parte 4 (con evidencia)

Snapshots: `hf-<id>/.hyperframes/artifacts/snapshots/qa-03|qa-04/at-*.png`.

### Tutorial (horizontal)

| Observación | Estado | Evidencia |
| --- | --- | --- |
| Todo en zoom, nunca pantalla completa | Corregido (C7 PASS) | qa-03 tutorial at-2.895s (login completo), at-8.455s (Inicio completo) |
| Texto desfasado ("Haz clic en Nuevo contacto" con el formulario abierto) | Corregido (N1 PASS) | at-15.116s (subtítulo sobre la lista, antes del clic), at-33.246s ("Haz clic en Guardar contacto" sobre el formulario) |
| Etiqueta "Paso 5 · Guarda…" = subtítulo | Corregido (N2 PASS) | chip solo "Paso N" en todas |
| Apertura redundante | Corregido (N2.opening PASS) | tarjeta "Nexo CRM · Contactos" + voz "Aprendes a registrar contactos." (at-1.298s) |
| Subtítulos flotando sobre la interfaz | Corregido (N3 PASS) | banda inferior morada en todas |
| Formulario fijo 12 s | Corregido (C8 PASS) | at-17.859s, 19.024s, 20.693s, 22.685s, 24.161s: campo por campo |
| Etiqueta "Nombre" cortada | Corregido (C9 PASS) | at-17.859s |
| No se ve el aviso | Corregido en TUT (N6 PASS) | at-34.564s; pero C4 MP4 marca 33,34–33,59 s casi vacío antes del aviso |
| Se perdió la historia de la feria | Corregido (N4) | at-24.161s ("Origen, Feria, porque la conociste ahí"), at-29.419s (nota "Conocida en la feria…") |
| Colores no son los del sistema / naranja / cajas negras / otra marca | Corregido (N5 PASS) | chip `#7c3aed`, banda `#4c1d95`, contorno morado at-36.064s; sin logo (pregunta abierta) |

### Redes (vertical)

| Observación | Estado | Evidencia |
| --- | --- | --- |
| Abre en "Paso 3" | Corregido (N7 PASS) | sin chip en todo el RED |
| Campos cortados a la derecha ("Ape", "Carg", "Telé") | **Sigue presente** | qa-03 redes at-6.062s, at-8.348s ("Ape", "Carg", "Telé", "Orig" cortados mientras se escribe Nombre/Correo; el control activo sí está completo, por eso C9 pasa) |
| "Vera" en un campo que no se ve | Corregido | at-6.946s (Apellido encuadrado al escribir) |
| Salta entre pantalla llena y franjas | Corregido (N9 PASS) | composición única, banda abajo |
| Fotograma casi vacío / clic sobre la nada | Clic corregido (C10 PASS); vacío parcial | at-13.741s/at-14.657s: aviso encuadrado con ~60 % de fondo vacío (C4 MP4 PASS) |
| El gancho no se cumple (feria) | Corregido | at-9.914s "En Origen, elige Feria."; la nota se omite en RED (se ve vacía en at-12.657s) |
| Cierre sin destino | Corregido (N8 PASS) | at-17.821s "Tutorial completo en el enlace de nuestro perfil" |
| Texto repetido | Corregido | sin chip |
| Colores ajenos | Corregido (N5 PASS) | banda y contorno morados |

### Lo que sí funciona (no debe romperse)

| Ítem | Estado | Evidencia |
| --- | --- | --- |
| Resaltado de la fila nueva visible (ahora morado) | Se mantiene | TUT at-36.064s; RED fotograma MP4 16,5 s (en ronda 1/2 se había perdido en RED; corregido en ronda 3) |
| Gancho del vertical | Se mantiene | at-0.91s "Conociste a alguien en la feria: regístralo así" + voz "¿Contacto de feria?" |
| Duración del vertical (~21 s) | Se mantiene | 18,6 s |
| TUT cierra con el siguiente video | Se mantiene | at-39.479s "Siguiente video: buscar un contacto" |
| Trato de tú | Se mantiene | L1–L4 PASS |

## Los 26 errores de Parte 1

| Estado | Cantidad | Números |
| --- | --- | --- |
| Corregido | 23 | 1, 2, 3, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22 (UI 71 %), 24, 25, 26 |
| Sigue presente | 2 | 4 (C4: TUT 33,34–33,59 s), 23 (V2: campos cortados en RED) |
| Solo falla automática | 1 | 10 (R2 en RED: el subtítulo va en la banda, no encima del aviso, pero qa exige 0,8 s sin subtítulo y el aviso dura 1,0 s en RED) |

## Fricciones

1. **Timeout de mi shell (120 s) vs pipeline**: lanzar `pipeline.py` sin timeout largo lo mata sin aviso; perdí 9,5 min creyendo que seguía en segundo plano.
2. **Lyria "recitation"**: el prompt de ejemplo del skill para RED ("Upbeat rhythmic pop, punchy drums, bright synths") fue bloqueado; el skill no lo advierte.
3. **R2/N6 en RED**: edit acelera la ventana del aviso (vive 2,5 s en la app → ~1,0 s a 3×) y compose gasta 0,5 s en el paneo; qa además cuenta el subtítulo de la banda como "encima" del aviso. No hay entrada en tutorial.yaml que lo arregle.
4. **Campos cortados en 9:16**: C9 solo verifica el control activo; las columnas vecinas quedan cortadas ("Ape", "Telé") y qa pasa.
5. **C4 en TUT tras el clic en Guardar**: la pantalla cambia antes del corte al aviso (C10) → ~0,4 s casi vacío.
6. **`omit` en RED**: los campos omitidos aparecen ya llenos en los planos siguientes y el campo omitido al final (Notas) se ve enfocado y vacío.
7. **Fila resaltada en RED**: con la narración corta, la fila quedaba encuadrada 0,25 s; hubo que alargar la narración (sube A2/R2 en contra).
8. **TUT1 vs N2**: "aprendes a…" obligatorio + apertura distinta del título obliga a usar un título que no sea "Cómo crear…".

## Propuestas priorizadas

1. (Alta) edit: en RED/PRO/NOV, no acelerar la ventana `result` (aviso) — mantenerla a velocidad real ≥ 0,8 s + el paneo — y que qa R2 ignore subtítulos que estén en la banda (N3) y no se solapen con el aviso.
2. (Alta) compose 9:16: en formularios de 2 columnas, encuadrar la columna completa o la fila de campos (sin cortar etiquetas vecinas); qa: check V2 para etiquetas visibles cortadas en el borde, no solo el control activo.
3. (Alta) compose: al cambiar de pantalla tras un clic, cortar en el mismo instante al encuadre nuevo (aviso/fila) para evitar el C4 de 0,3–0,5 s.
4. (Media) edit: hold mínimo del `highlight` encuadrado (≥ 1,5 s también en RED, porque es el resultado), independiente de la narración.
5. (Media) skill tutorial-voz/edición: advertir del bloqueo "recitation" de Lyria y dar prompts de RED que no citen géneros comerciales ("pop"); `music.py` podría reintentar con un prompt neutro.
6. (Media) skill tutorial: indicar que `pipeline.py` debe correr con timeout ≥ 15 min en el shell del agente (o dar `--detach` con log) para no perder la salida.
7. (Baja) `omit`: mostrar el valor final del campo omitido (o no enfocarlo) para que no aparezca vacío y enfocado.
8. (Baja) plantilla del brief: aclarar qué oscuro usar para `surface` cuando la app tiene varios (menú casi negro vs violeta de marca).

## Pendientes / preguntas abiertas

- Logo: no hay; videos sin logo (render lo pide antes del render final: queda abierto).
- Destino del CTA: "en el enlace de nuestro perfil" (propuesto, confirmar).
- Siguiente video: "buscar un contacto" (propuesto).
- Ego Lite tiene una actualización disponible (no aplicada; requiere aprobación).
- Directorios temporales fuera del repo (scripts de ensayo y fotogramas): `C:/Users/FRANCI~1/AppData/Local/Temp/gpFDT5Dq/ga4AQ1cJ/tmp.uxL9iBleql`, `.../tmp.zgIT4vQwyz`.
