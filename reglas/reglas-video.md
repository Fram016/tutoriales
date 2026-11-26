# Reglas de video

Fuente: correcciones del usuario sobre el video de prueba de Nexo CRM (copiadas textualmente).
Es la referencia normativa del pipeline: los skills, `tools/lint.py` y `tools/qa.py` citan estas reglas por su ID.

## Parte 1: Errores detectados

H = horizontal, V = vertical.

| # | Video | Tiempo | Qué está mal | Regla |
|---|---|---|---|---|
| 1 | H, V | 0:00 | Abre solo con el título, sin decir qué se va a lograr | E1 |
| 2 | H, V | — | Pasos distintos: H tiene 7 y V tiene 5, y “completar datos” está repartido en 3 pasos | E2 |
| 3 | H | 0:15 | Clic sobre zona vacía: el botón “+ Nuevo contacto” no está en cuadro | C3 |
| 4 | V | 0:08, 0:22 | Pantallas casi vacías durante cargas | C4 |
| 5 | H | 0:21, 0:31 | Fundido entre dos zooms: se ven campos duplicados (“Ramírez” dos veces) y textos sueltos (“to”) | C2 |
| 6 | H | 0:12, 0:18 | Planos generales largos con texto ilegible | C1 |
| 7 | H, V | todo | El cursor cambia de tamaño según el zoom | C5 |
| 8 | H | Pasos 2, 4, 7 | La etiqueta “Paso” tapa el logo “Nexo CRM” y tiene bajo contraste sobre el morado | O1 |
| 9 | V | 0:16 | Etiqueta “Paso 3” semitransparente: la animación no termina | O1 |
| 10 | H | 0:43 | El subtítulo y el cursor tapan el aviso “Contacto guardado” | O2, R2 |
| 11 | H | 0:21–0:25 | El subtítulo tapa los campos Etapa y Origen | O2 |
| 12 | H, V | varios | Frases cortadas: “…con el / correo”, “Sale el aviso / verde” | T1 |
| 13 | H, V | — | Estilos de subtítulo distintos entre versiones (gris redondeado y negro recto) | O3 |
| 14 | H, V | 0:46 | El resaltado de la fila nueva casi no se ve | R3 |
| 15 | H | 0:37 | La nota se teclea completa y lenta | C6 |
| 16 | H | 0:57–1:02 | 4,7 s de silencio con la tarjeta de cierre quieta | A2 |
| 17 | H | 0:00 | El título parte la marca: “Nexo / CRM” | T3 |
| 18 | H, V | — | Cierra sin siguiente paso ni llamado a la acción | E1 |
| 19 | H, V | — | Mezcla de registros: la interfaz dice “Ingresá” (vos) y la narración usa “tú” | L1 |
| 20 | H, V | — | Dice “tocamos” en una interfaz de escritorio | L2 |
| 21 | H, V | — | Alterna “cliente”, “prospecto” y “contacto” para lo mismo | L3 |
| 22 | V | todo | Es el horizontal achicado: la interfaz ocupa ~55 % del alto y abajo queda ~25 % vacío | V1 |
| 23 | V | varios | Textos y botones cortados en los bordes: “orreo”, “Guardar co…” | V2 |
| 24 | V | todo | Título fijo arriba durante los 41 s | V3 |
| 25 | V | 0:00 | Título dentro de la zona tapada por la app | V4 |
| 26 | V | 0:02 | Login en plano muy abierto, ilegible e innecesario en redes | V5 |

## Parte 2: Reglas

### E: Estructura

**E1. Apertura y cierre obligatorios.**
Los primeros 3 s deben decir qué se va a lograr (en tutoriales) o plantear el problema (en redes).
Los últimos 2–3 s deben mostrar un siguiente paso o un llamado a la acción.
Prohibido abrir o cerrar solo con el título o con “¡Listo!”.

**E2. Un guion, una lista de pasos.**
Las versiones H y V se generan desde la misma lista de pasos.
Un paso = una acción con un resultado visible.
Prohibido dividir una misma acción en varios pasos.
En V se permite omitir pasos, pero se conserva la numeración original o se renumera de forma coherente.

**E3. Un objetivo por video.**
Si el guion pasa de unos 5 min, se divide en capítulos con separador (“Parte N: …”) y la etiqueta muestra “Parte N · Paso M”.

### C: Cámara y movimiento

**C1. Dos niveles de zoom.**
Contexto (1,0×): máximo 1,0 s.
Detalle (1,8–2,5×): en toda acción de escribir, hacer clic o leer.

**C2. Transiciones de cámara.**
Entre encuadres de la misma pantalla, usa paneo o zoom interpolado de 400–600 ms con curva suave (ease-in-out).
Prohibido el fundido entre dos encuadres de la misma pantalla.

**C3. Objetivo del clic visible.**
El elemento que se va a tocar debe estar completo dentro del cuadro al menos 500 ms antes del clic.

**C4. Sin pantallas vacías.**
Ningún fotograma (fuera de la intro y el cierre) puede tener más del 70 % del área sin contenido.
Las cargas se cortan o se cubren con una transición.

**C5. Cursor constante.**
Tamaño fijo en píxeles de salida (unos 48 px en 1080p), sin importar el zoom.
Halo suave en el clic.

**C6. Tecleo.**
Velocidad de 12–15 caracteres por segundo.
Si el texto pasa de 30 caracteres, acelera ×3 después de los primeros 15.

### O: Elementos superpuestos (etiquetas, subtítulos, avisos)

**O1. Etiqueta de paso.**
No puede superponerse a ningún elemento de la interfaz (logo, menú, encabezado).
Contraste de al menos 4,5:1 con su fondo.
Opacidad final del 100 %.

**O2. Zona prohibida para subtítulos.**
El subtítulo no puede taparse con el elemento activo, un aviso emergente ni un campo que se mencione en la narración.
Si hay conflicto, se mueve el encuadre, no el elemento.

**O3. Un solo estilo.**
Subtítulos y etiquetas con la misma tipografía, color, radio de esquinas y posición en todas las versiones.

### R: Resultado

**R1.** El resultado final se muestra en zoom de detalle, nunca en plano general.

**R2. Avisos de confirmación.**
Zoom al aviso y mínimo 800 ms visible sin subtítulo ni cursor encima.

**R3. Elemento nuevo.**
Se resalta con un contorno o pulso del color de acento, con contraste de al menos 3:1 frente a las filas vecinas.

### T: Texto

**T1. Segmentación de subtítulos.**
Máximo 2 líneas de 42 caracteres.
Duración mínima de 1,2 s.
Prohibido terminar una línea en artículo, preposición o conjunción.
Prohibido que un subtítulo cruce un cambio de paso.

**T2. Tamaño mínimo:** 40 px de alto de letra en la resolución de salida.

**T3. Marca indivisible.**
El nombre del producto nunca se parte entre líneas.
Si no entra, se reduce el tamaño o se reescribe.

### L: Idioma (español neutro de Ecuador)

**L1.** Trato de “tú” en la narración, los subtítulos y los datos de la interfaz demo. Prohibido el voseo (“ingresá”, “tenés”).

**L2.** Verbos según el dispositivo: “hacer clic” en escritorio y “tocar” en celular.

**L3.** Glosario fijo: un término por concepto, definido antes de generar (por ejemplo, “contacto”).

**L4.** Sin modismos regionales: “aquí” y no “acá”; “registrar” y no “cargar”.

### A: Audio

**A1. Volumen:** −14 LUFS, con picos por debajo de −1 dBTP.

**A2. Silencios:** ninguno mayor a 1,0 s. La tarjeta de cierre dura como máximo 2,5 s.

### V: Vertical (9:16)

**V1. Reencuadre real.**
Recorte 9:16 que sigue al elemento activo.
La interfaz ocupa al menos el 70 % del alto.
Prohibido poner el video horizontal achicado dentro del marco.

**V2. Sin cortes de elementos clave.** Ningún botón, campo o etiqueta mencionada puede quedar cortada por el borde.

**V3. Título solo en la apertura (máximo 3 s).** Después, solo la etiqueta de paso.

**V4. Zonas seguras.** Nada importante en el 15 % superior ni en el 20 % inferior.

**V5. Duración de 15–35 s.** Omite el login y las acciones obvias.

### Validación automática sugerida

Para que la IA se autocorrija, después de generar puede revisar automáticamente:

- Pantallas vacías (C4): fotogramas casi uniformes.
- Superposición (O1, O2, R2): que el área de los subtítulos y etiquetas no choque con la del elemento activo o del aviso.
- Audio (A1, A2): volumen y silencios.
- Subtítulos (T1): largo de línea y palabra final.
- Idioma (L1–L4): buscar en el texto los términos prohibidos (“ingresá”, “tocamos” en escritorio, “acá”).

## Parte 3: Reglas por tipo de video

Antes de generar, la IA debe recibir o decidir el tipo de video, porque ese dato define la estructura, la duración, el ritmo y el formato.

### TUT: Tutorial

Propósito: que la persona complete una tarea. Formato principal: horizontal 16:9.

**TUT1. Estructura obligatoria, en este orden:**
1. Objetivo (3 s): “En este video aprendes a…”.
2. Requisitos (opcional, máximo 5 s): permisos, datos previos.
3. Pasos numerados.
4. Resultado visible, en zoom de detalle.
5. Siguiente video (2–3 s).

**TUT2.** Duración libre, definida por la tarea. Si pasa de 5 min, aplica capítulos (E3).

**TUT3. Capítulos para videos largos:**
- Índice al inicio.
- Separador al abrir cada parte.
- Etiqueta “Parte N · Paso M”.
- Mini resumen cada 2–3 min (“Hasta aquí ya tienes…”).

**TUT4. Ritmo pausado:**
- Mínimo 1,5 s de pausa después de cada resultado parcial.
- Se recortan las esperas y el tecleo largo, pero no las explicaciones.

**TUT5.** Se muestran todos los pasos, incluido el login si es la primera vez que se usa el sistema.

**TUT6.** Sin gancho de marketing. La apertura informa, no vende.

**TUT7.** Datos de ejemplo: los mismos de toda la serie (clientes, productos, empresa).

### RED: Video corto para redes

Propósito: atraer y llevar al tutorial completo. Formato: vertical 9:16.

**RED1. Estructura obligatoria:**
1. Gancho (1–2 s): un problema o una pregunta. Ejemplo: “¿Conociste un cliente en una feria?”.
2. 3 o 4 acciones clave.
3. Resultado.
4. Llamado a la acción (2 s): “Mira el tutorial completo” o “Guarda este video”.

**RED2.** Duración: 15–35 s.

**RED3. Ritmo rápido:**
- Ningún plano dura más de 3 s sin cambio visual.
- Se omiten el login, la navegación obvia y los campos opcionales.

**RED4.** Texto en pantalla protagonista: el video se tiene que entender sin sonido.

**RED5.** Aplican todas las reglas V (reencuadre, zonas seguras).

### PRO: Promocional

Propósito: convencer de usar el producto o una función. Formato: el que pida el canal.

**PRO1.** Estructura obligatoria: problema, solución (el producto), beneficio medible o visible y llamado a la acción.

**PRO2.** Duración: 20–60 s.

**PRO3.** Se muestran resultados, no procesos: máximo 2 interacciones seguidas con la interfaz.

**PRO4.** Sin etiquetas de paso ni numeración.

**PRO5.** Música marcada y cortes al ritmo de la música.

**PRO6.** Cierre con logo y llamado a la acción concreto: prueba gratis, contacto o enlace.

### NOV: Anuncio de novedad

Propósito: informar un cambio o una nueva función a usuarios actuales.

**NOV1.** Estructura obligatoria: qué cambió, dónde está (ruta en la interfaz) y para qué sirve.

**NOV2.** Duración: 15–30 s.

**NOV3.** Un solo cambio por video.

**NOV4.** Mostrar la ubicación exacta: zoom al menú o botón nuevo con resaltado (R3).

**NOV5.** Cierre con enlace al tutorial completo, si existe.

### Tabla de decisión

| | Tutorial | Redes | Promocional | Novedad |
|---|---|---|---|---|
| Formato | 16:9 | 9:16 | Según canal | 16:9 o 9:16 |
| Duración | Libre (capítulos si pasa de 5 min) | 15–35 s | 20–60 s | 15–30 s |
| Apertura | Objetivo | Gancho | Problema | Qué cambió |
| Etiqueta de paso | Sí | Opcional | No | No |
| Login | Sí, si es la primera vez | No | No | No |
| Ritmo | Pausado | Rápido | Dinámico | Directo |
| Música | Suave o ninguna | Rítmica | Marcada | Suave |
| Cierre | Siguiente video | Llamado a la acción | Logo y llamado a la acción | Enlace al tutorial |

### Aplicado a tus videos

El horizontal debe generarse como TUT. Hoy le faltan el objetivo (TUT1) y el siguiente video (TUT1).

El vertical debe generarse como RED, no como TUT recortado. Hoy le faltan el gancho (RED1) y el llamado a la acción (RED1). Además incluye el login (RED3) y es más largo de lo necesario: 41 s cuando debería durar 15–35 s (RED2).

## Parte 4: Observaciones de la segunda prueba (texto del usuario)

### Tutorial (horizontal, 39 s)

- Todo el video está en zoom. Nunca se ve la pantalla completa, así que no se entiende dónde está cada cosa dentro del sistema.
- El texto va desfasado. “Haz clic en Nuevo contacto” aparece con el formulario ya abierto (≈0:16), y “Haz clic en Guardar contacto” aparece sobre la lista ya guardada (≈0:31).
- Hay texto repetido. La etiqueta “Paso 5 · Guarda el contacto” y el subtítulo “Haz clic en Guardar contacto” dicen lo mismo.
- La apertura es redundante. “Cómo crear un contacto en Nexo CRM” y “Aprende a crear un contacto” repiten la misma idea.
- Los subtítulos flotan sobre la interfaz. Quedan en medio de la pantalla, encima del campo Notas y de la tabla.
- El formulario está fijo unos 12 s (de 0:16 a 0:28) con el mismo encuadre. Se vuelve monótono.
- El encuadre corta el formulario: la etiqueta “Nombre” queda cortada arriba.
- No se ve el aviso de confirmación. Pasa directo del botón Guardar a la lista.
- Se perdió la historia. Ya no hay contexto de la feria ni nota, y “Feria” se elige como origen sin explicación.
- Los colores no son los del sistema.
- El número de “Paso”, la línea bajo el título y el contorno de la fila nueva son naranjas, mientras que todo el CRM es morado.
- Los subtítulos son cajas negras puras que se ven pesadas sobre la interfaz clara.
- El video parece de otra marca que la del producto.

### Redes (vertical, 21 s)

- Abre en “Paso 3”. Confunde, porque en redes nadie vio los pasos 1 y 2.
- Se cortan campos a la derecha (“Ape”, “Carg”, “Telé”), y se escribe “Vera” en un campo que no se ve (≈0:08).
- El encuadre salta entre pantalla llena y franjas moradas arriba y abajo (≈0:03 y ≈0:14).
- Hay un fotograma casi vacío con el clic sobre la nada (≈0:14).
- El gancho no se cumple. Promete la historia de la feria y después no la muestra.
- El cierre “Mira el tutorial completo” no dice dónde verlo.
- Tiene el mismo texto repetido que el tutorial (etiqueta y subtítulo).
- Los colores no son los del sistema: naranja en las etiquetas, la línea del gancho y el resaltado, más cajas negras en los subtítulos, que no combinan con el morado del CRM ni con las franjas moradas del fondo.

### Lo que sí funciona

- El resaltado de la fila nueva se ve claramente (aunque debería ser morado).
- El gancho del vertical funciona como apertura.
- La duración del vertical (21 s) es adecuada.
- El tutorial cierra con el siguiente video.
- El trato de “tú” es correcto en todo el video.

### Reglas derivadas (decisiones de implementación, ronda 2)

Cada observación se convierte en una regla verificable. ID entre corchetes.

- **[C7] Plano de ubicación.** Al entrar a cada pantalla nueva se muestra la pantalla completa (1,0×, hasta 1,0 s, respetando C1) y luego zoom interpolado al primer elemento. Nunca todo el video en zoom.
- **[C8] Encuadre vivo.** Ningún encuadre idéntico dura más de 4 s en TUT ni 3 s en RED: en formularios la cámara acompaña campo por campo.
- **[C9] Encuadre completo del control.** El encuadre de un campo incluye su etiqueta visible; nada del control activo queda cortado (V2 también en 16:9).
- **[C10] Corte en cambio de pantalla.** Cuando la pantalla cambia, la cámara corta al nuevo encuadre; no hay paneo sobre zonas vacías ni clic sobre la nada.
- **[N1] Sincronía.** La narración y el subtítulo que piden una acción terminan antes de que la acción ocurra (o como máximo 0,3 s después del clic); nunca describen algo que ya pasó.
- **[N2] Sin texto repetido.** La etiqueta muestra solo “Paso N” (TUT); el título del paso no se repite en el subtítulo. En la apertura, la tarjeta y la narración no dicen la misma idea dos veces.
- **[N3] Subtítulos en banda.** Los subtítulos van en una banda fija fuera de la interfaz (abajo en 16:9; banda dedicada en 9:16), nunca flotando sobre campos o tablas.
- **[N4] Historia coherente.** Si la apertura plantea una historia (por ejemplo la feria), los datos de ejemplo y la narración la cumplen y explican cada dato elegido (Origen “Feria”, nota con el contexto).
- **[N5] Colores del sistema.** Etiquetas, líneas, resaltados y bandas usan la paleta de la app (primario, oscuro y claro de la interfaz). Prohibido introducir colores ajenos a la marca. Subtítulos sin cajas negras puras.
- **[N6] Aviso visible.** R2 prevalece sobre C4: el aviso de confirmación siempre se muestra (≥ 800 ms) y su ventana queda exenta de C4.
- **[N7] Redes sin numeración.** En RED no se muestran etiquetas “Paso N”.
- **[N8] Llamado a la acción con destino.** El cierre de RED y PRO dice dónde ver o hacer la acción (“en el enlace del perfil”, “en nuestro canal de YouTube”).
- **[N9] Encuadre vertical estable.** En 9:16 la composición es una sola: no alterna entre pantalla llena y franjas.

## Parte 5: Ajustes de la tercera prueba (texto del usuario)

> “esta mucho mejor y si me agrada las mejoras aplicalas, sumale que no haga tanto zoom un poco menos de zoom y cuando sean cosas de formularios quizas pantalla completa sin zoom con recuadro remarcado o que me recomiendas?”

### Reglas derivadas (recomendación aceptada para aplicar)

- **[C1 revisada] Menos zoom.** Detalle: 1,4–1,8× (antes 1,8–2,5×). Contexto (pantalla completa) hasta 1,0 s, igual que antes.
- **[N10] Plano de formulario.** Cuando la acción ocurre dentro de un formulario (form, diálogo o tarjeta con varios campos), el encuadre muestra el formulario completo, ajustado a su tamaño (en general 1,1–1,5×, nunca por encima de 1,8×), y no se mueve campo por campo. Si el formulario no entra legible, se divide en el menor número de encuadres posible, de arriba hacia abajo.
- **[N11] Recuadro del campo activo.** El campo activo se marca con un recuadro del color primario de la marca y un leve oscurecimiento del resto del cuadro (spotlight, opacidad ≤ 25 %). El recuadro se desplaza de campo en campo con una animación de 250–400 ms. Ese desplazamiento cuenta como cambio visual para C8.
- **[N12] Formularios en vertical.** En 9:16 el formulario se encuadra entero a lo ancho; ningún campo ni etiqueta queda cortado en los bordes (V2).

## Parte 6: Observaciones del tutorial Perseo XML (texto del usuario)

> “El que me interesa es el Perseo xml tutorial nos basaremos en ese Tenías razón, hay bastantes. Revisé el video completo (93 s, 10 pasos). Te las ordeno de más a menos grave.”

### Errores graves

- Hay resaltados sobre zonas vacías. El recuadro naranja aparece sobre un rectángulo en blanco que no corresponde a nada (≈0:12, ≈0:15, ≈0:23). El espectador no sabe dónde hacer clic.
- Algunos resaltados marcan el elemento equivocado. El subtítulo dice “Haz clic en Comprobantes electrónicos emitidos”, pero el recuadro está sobre “Certificados” (≈0:27).
- El texto no coincide con la pantalla.
  - “Abre Perseo XML y haz clic en Carpeta de descargas” aparece sobre la página del SRI, sin Perseo abierto (≈0:07).
  - “En la configuración, con Cambiar eliges dónde se guardan tus XML”: nunca se ve la configuración ni el botón Cambiar (≈0:08–0:15).
  - “El resumen muestra cuántos comprobantes se descargaron” aparece sobre la tabla del SRI, no sobre el resumen (≈0:54).
  - “Haz clic en Consultar. Aparece la lista” llega cuando la lista ya está en pantalla (≈1:13).
- Hay una pantalla en blanco. Durante “Ahora vuelve a Consultas…” no se ve nada (≈0:58).
- Algunos fotogramas mezclan dos vistas. Se ven dos pantallas pegadas, con textos cortados como “Cr / usu” (≈0:27).

### Estructura y guion

- No todos los pasos son acciones. “Paso 3: Se abre el formulario”, “Paso 7: Se abre su formulario” y “Paso 8: El tipo Factura ya viene elegido” describen lo que pasa, no lo que hace el usuario. Inflan el conteo a 10 pasos.
- El Paso 1 mezcla dos tareas: abrir Perseo XML y configurar la carpeta de descargas.
- El video tiene dos flujos casi iguales sin separarlos: descargar emitidos y descargar recibidos. Debería dividirse en partes:
  - Parte 1: Configurar la carpeta
  - Parte 2: Comprobantes emitidos
  - Parte 3: Comprobantes recibidos
- El protagonista se pierde. El tutorial es de Perseo XML, pero la mayor parte del tiempo se navega el SRI. Perseo aparece al inicio, en el Paso 6 y en el Paso 10. Hay que dejar claro cuándo se trabaja en el SRI y cuándo en Perseo.
- El requisito es ambiguo. “Perseo XML instalada” no aclara qué es. Mejor: “Necesitas la extensión Perseo XML instalada y tu sesión del SRI abierta”.
- El resumen de descarga solo se muestra al final (Paso 10). En el Paso 6, que es la primera descarga, no se ve el resultado.

### Texto y subtítulos

- Hay frases cortadas entre subtítulos.
  - “…anterior a hoy. Para una consulta corta, / elige el establecimiento…”
  - “Mientras trabaja, el botón dice En proceso. Al terminar, / el resumen muestra…”
- Algunos subtítulos son muy largos: dos instrucciones en un solo bloque, como “Abre Perseo XML. En Comprobantes emitidos, haz clic en XML Desde el RIDE.”

### Encuadre y composición

- El encuadre no es coherente.
  - Hay planos donde la página del SRI ocupa solo una parte del cuadro, con negro alrededor (≈0:07).
  - Otros planos muestran formularios y tablas completos con letra diminuta (≈0:27, ≈0:42).
  - Y otros tienen zoom fuerte.
- La ventana de Perseo aparece cortada en el borde derecho (≈1:25), justo cuando muestra el resumen “6 descargados, 0 con error”.
- La franja negra inferior es fija y quita espacio. Ocupa alrededor de 1/6 de la pantalla todo el video, mientras el contenido arriba se ve pequeño.
- Los anuncios de la ventana de Perseo distraen. Club Perseo, Facturito y “Únete gratis” se ven y cambian en cada aparición, mientras se intenta explicar dónde hacer clic.

### Color y marca

- El logo de Perseo casi no se ve en la intro y el cierre. El texto “Perseo” es gris oscuro sobre fondo negro; solo se distingue la “P”.
- El naranja de las etiquetas y resaltados sí es coherente con Perseo, pero contrasta fuerte con el azul del SRI. Ayuda a distinguir cuándo se está en cada sistema, pero conviene usarlo solo para Perseo y los resaltados.

### Datos sensibles

- El difuminado no es parejo. En los comprobantes recibidos se difuminan el RUC y los nombres, pero en los emitidos se ven completas las claves de acceso y los montos. Define un criterio: o todo es dato de demostración, o se difumina igual en todo el video.

### Lo que funciona

- La pantalla de requisito previo.
- El cierre con “Siguiente video: importar los XML en Perseo”.
- El audio está bien nivelado (−14 LUFS).
- Las etiquetas de paso son consistentes y legibles.
- El trato de “tú” es correcto en todo el video.

> “y quita el ultimo espacio que dice siguiente video no es necesario. Y el logo de Perseo al inicio no se distingue”

### Reglas derivadas (ronda 4)

- **[N13] Resaltado verificado.** Todo elemento resaltado o clicado debe estar visible en su caja (no oculto, no vacío, en el punto de clic está el propio elemento) y su texto visible debe coincidir con lo que nombra la narración. Si no hay coincidencia, la toma falla.
- **[N14] Lo narrado está en pantalla.** Mientras la narración o el subtítulo mencionan algo (Perseo abierto, la configuración, el botón Cambiar, el resumen, la lista), eso debe verse en ese momento. Una instrucción termina antes de que ocurra su efecto (refuerza N1).
- **[N15] Paso = acción del usuario.** Lo que “pasa” (se abre un formulario, un valor ya viene elegido) no es un paso: va en la narración del paso anterior o siguiente. Un paso = una sola tarea.
- **[N16] Partes.** Cuando el video tiene dos o más flujos (aunque dure menos de 5 min), se divide en partes con separador “Parte N: título” y etiqueta “Parte N · Paso M” (E3/TUT3 aplicados a flujos, no solo a la duración).
- **[N17] Contexto visible.** Un indicador muestra dónde se trabaja: “En el SRI” o “En Perseo XML”. El color de marca de Perseo se usa solo para Perseo y para los resaltados; el contexto SRI usa un color neutro.
- **[N18] Resultado de cada descarga.** Después de cada descarga se muestra el resumen de la extensión (cantidad descargada y errores) en detalle.
- **[N19] Subtítulos por oración.** Un bloque de subtítulo = una oración = una instrucción. Nunca se corta una oración entre dos bloques (si no entra, se reescribe más corta).
- **[N20] Escala coherente y legible.** Sin bordes negros alrededor de la página (sin pillarbox). Texto de la interfaz legible en todo momento (letra de la interfaz ≥ 16 px en la salida); el zoom se mantiene en un rango estable sin saltos bruscos.
- **[N21] Banda delgada.** La banda de subtítulos ocupa como máximo 1/8 de la altura (≤ 135 px en 1080).
- **[N22] Superficies completas.** La ventana de la extensión nunca queda cortada por el borde del cuadro.
- **[N23] Sin anuncios.** Las promociones de la ventana de la extensión (tarjetas, carruseles, “Únete gratis”) se ocultan en la toma.
- **[N24] Logo legible.** El logo se muestra en su variante clara sobre fondos oscuros (o sobre un fondo claro), con contraste ≥ 3:1.
- **[N25] Censura uniforme.** Criterio del proyecto Perseo XML: se difuminan en todo el video la identidad del contribuyente (RUC, nombre, correo, teléfono), el RUC y la razón social de terceros, las claves de acceso y los montos, en todas las tablas por igual. Las páginas del navegador (configuración) también se censuran (ruta de carpeta con el usuario de Windows).
- **[N26] Sin pantallas en blanco ni vistas mezcladas.** Las cargas y transiciones de navegación se cortan; nunca se ven dos páginas pegadas o superpuestas en un mismo cuadro.
- **[N27] Cierre opcional.** “quita el ultimo espacio que dice siguiente video no es necesario”: la tarjeta de cierre ya no es obligatoria en TUT; si no hay cierre, el video termina en el resultado final (sustituye la parte de cierre de E1/TUT1).

## Parte 7: Ritmo y zoom del tutorial Perseo XML v2 (texto del usuario)

> “Esta mucho mejor pero hay un proboema, dura un minuto para funciones que se pueden mostrar en maximo 45 segundos, ademas no se ve tan bien realmente siento qeu va a un ritmo lento y diria usar menos zoom para que se vean mejor los formularios”

### Reglas derivadas (ronda 5)

- **[P1] Duración objetivo.** El tutorial de una función corta (como Perseo XML) dura como máximo 45 s en total, incluidas apertura y separadores. `videos[].max_seconds` fija el tope; el lint y el QA lo exigen.
- **[P2] Ritmo ágil (`pace: fast`).** Sustituye a TUT4 (pausa mínima de 1,5 s) cuando el video declara `pace: fast`:
  - pausas tras un resultado de 0,5 s;
  - esperas y descargas aceleradas hasta 8× (o cortadas, dejando el estado inicial y el final);
  - separadores de parte de 0,8 s y apertura de 2 s como máximo;
  - voz algo más rápida (tempo ×1,1–1,15 sin cambiar el tono);
  - ningún plano sin cambio visual por más de 2,5 s.
- **[P3] Menos zoom.** Detalle 1,15–1,4× (sustituye 1,4–1,8× de C1 en `pace: fast` y en general para interfaces de escritorio); formularios encuadrados enteros a 1,0–1,2×; el plano de ubicación puede ser el propio plano del formulario. La legibilidad se mantiene con la banda delgada (N21) y sin bordes negros (N20).

> “No, cuando muestras los pasos no deja leer es muy rapdio” (sobre la versión de 43,4 s)

- **[P4] Tiempo de lectura.** Todo texto en pantalla se ve al menos el tiempo de leerlo: separadores de parte ≥ 1,5 s; cada subtítulo ≥ caracteres/15 + 0,4 s (mínimo 1,5 s); la etiqueta de paso no cambia antes de 1,5 s. Para cumplir el tope de P1 se acorta la narración o se juntan pasos, nunca el tiempo de lectura. El tempo de voz baja a ×1,05 como máximo.

## Parte 8: Diálogos, carpeta y pronunciación (texto del usuario)

> “Haz mas coherente los dialogos y por ejemplo debes mencionar explicitamente, Ingresa a la plataforma del SRI, luego ingresa a... y sigue con frases coherentes, no mostraste tambien como configurar correctamente la carpeta de descargas, no importa que consumas un poco mas de tiuempo siempre que sea claro solo no llegues al minuto, y explica que por ejemplo en emitidos transforma los RIDE a XML ademas RIDE se pronuncia RI DE no raid”

### Reglas derivadas (ronda 6)

- **[D1] Narración en secuencia.** La narración cuenta el recorrido completo con conectores explícitos y nombra cada lugar: “Ingresa a la plataforma del SRI en línea.”, “Luego entra a Facturación Electrónica, Producción y Consultas.”, “Después…”, “Por último…”. Cada frase sigue a la anterior; nada de frases sueltas.
- **[D2] Explicar qué hace cada opción.** Cuando la herramienta transforma algo, se dice: en emitidos, “XML desde el RIDE” transforma los RIDE (PDF) en XML; en recibidos, “XML para importar” descarga los XML listos para importar.
- **[D3] Pronunciación.** `pronunciation: {TÉRMINO: lectura}` en tutorial.yaml: la voz lee la forma indicada (RIDE → “ri de”); los subtítulos muestran el término original.
- **[D4] Configuración completa de la carpeta.** Se muestra el clic en “Cambiar / Change” y la carpeta resultante en la configuración (una carpeta para emitidos y otra para recibidos, configurada antes de cada descarga). El selector nativo de Windows no se graba: el video corta del clic al resultado. Al terminar la toma se restaura la carpeta original del usuario.
- **[P1 revisada] Duración.** Este tutorial puede durar más de 45 s si gana claridad, siempre menos de 60 s (`max_seconds: 58`).

> “Algo adicional mantene un solo tono de voz hubieron cambios de tono de voz, eso añade como orden”

- **[D5] Un solo tono de voz.** Todo el video usa la misma voz, el mismo estilo y el mismo tempo en todos los clips. Las frases de un video se generan juntas en una misma tanda (nunca se mezclan clips de corridas anteriores con otro estilo o tempo), y cada clip se nivela al mismo volumen antes de la mezcla. El QA compara el tono medio (frecuencia fundamental) y el volumen de cada clip contra la mediana del video y marca los que se desvían.

## Parte 9: Instalación de la extensión (texto del usuario)

> “Ahora algo extra que se me paso por alto, simula la instalacion del plugin, el video quedo perfecto pero toca indicar como instalar tambien, esto ya hace que supere el minuto asi que no apliques restricciones de tiempo, solo manten el tono coherente el estilo de voz y habla de igual forma. Que necesito que enseñes, a buscar la tienda de extensiones y como se instala despues el tutorial que ya tenemos”

### Reglas derivadas (ronda 7)

- **[I1] Instalación primero.** Cuando el producto es una extensión, el tutorial empieza mostrando cómo buscar la tienda de extensiones (Chrome Web Store), encontrar la extensión e instalarla; después sigue el uso.
- **[I2] Simulación honesta.** Lo que el navegador no deja grabar o hacer por programa (el botón “Agregar a Chrome” en otro navegador, la ventana nativa de confirmación, el estado instalado) se simula dentro de la página con el mismo texto y aspecto que verá el usuario en Chrome; no se instala nada de verdad.
- **[I3] Tomas unidas.** Un tutorial puede armarse con varias tomas (`tools/merge_takes.py`) cuando una parte no necesita repetir las demás; la narración completa se sigue generando en una sola lectura (D5).
- **[P1 revisada 2] Sin tope de duración** para este tutorial (“no apliques restricciones de tiempo”); se mantienen P4 (lectura), D1-D5 y la misma voz, estilo y tempo de la v3.

## Parte 10: Resultado final con video del usuario (texto del usuario)

> “"C:\Users\Francisco Lopez\Videos\2026-11-19 09-39-50.mp4" ahi te dejo un video de algo que debes añadir al final como resultado final”
>
> Narración del propio video: “y ahora debes hacer lo siguiente para la parte final, yo estoy mostrando como voy a descargas la carpeta Perse Xml, voy a mostrar los emitidos, regreso y muestro los recibidos, censura la información delicada de la carpeta de descargas y simplemente muestra cómo se ve el resultado final”

### Reglas derivadas (ronda 8)

- **[F1] Resultado final.** El tutorial cierra mostrando el resultado en el equipo: la carpeta Perseo XML en Descargas, con Emitidos y Recibidos y sus XML.
- **[F2] Video del usuario como toma.** Un video aportado por el usuario se convierte en una toma (`tools/import_video_take.py`): cuadros con la censura aplicada antes de guardarlos, pasos y recuadros definidos a mano por tiempo, y se une con `merge_takes` (I3). Su audio original no se usa; la narración sigue saliendo de una sola lectura (D5).
- **[F3] Censura de escritorio.** En capturas del escritorio se difumina: otros archivos y carpetas de Descargas, nombres de los XML (llevan la clave de acceso con RUC), barra lateral con nombres personales y la barra de tareas; se deja legible lo que el resultado necesita mostrar (carpeta Perseo XML, Emitidos, Recibidos, tipo “Documento XML”, cantidad de archivos).

> “Tambien cambia la euforia y animo que hable mejor mas vendedor y con energia ahorita se escucha muy sozo y aburrido”

- **[D6] Voz con energía de vendedor.** El estilo de la narración es entusiasta, sonriente y convincente, con ritmo ágil (nunca plano o monótono). Se fija en `voice.style` del tutorial y aplica a toda la lectura (D5).

## Parte 11: Narración que explica, no dicta (texto del usuario)

> “debes indicar como se ve el formulario de tegistrarse cuando muestras como hacer login, debes decir, "si eres usuario del sistema contafacil ingresa con tu contraseña y clave en caso de no tener credenciales llena el formulario de registro para hacer uso de la extemsion" cuando explicas como cambiar la carpeta de descargas debes explicar por que por ejemplo "vamos a cambiar la carpeta de descargas oara qur todos los xml que descarguemos del sri vayan a una carpeta especifica" o algo similar, en vez de decir clic en change deberias hablar en español y un poco descriptivo "se debe dar clic en cambiar o change para seleccionar la carpeta de adecuada", cuando seleccionas laa fechas del sri, no debes decir la fecha que deben escoger si no "seleccionan fecha" o algo similar, lo que te indique es para tu ejercicio no parte del tutorial, adicional para tutoriales la voz esta bien pero debe ser mas energica un poco mas animada.”

### Reglas derivadas (ronda 9)

- **[G1] Alternativas visibles.** Si una pantalla ofrece dos caminos (iniciar sesión o registrarse), el video muestra ambos: abre el formulario alternativo un momento y la narración dice cuándo usar cada uno (“Si ya eres usuario…, ingresa…; si no tienes credenciales, llena el formulario de registro…”).
- **[G2] El porqué antes del cómo.** Un paso de configuración (carpeta, opción, ajuste) empieza diciendo para qué sirve (“para que todos los XML que descargues del SRI vayan a una carpeta específica”).
- **[G3] Etiquetas en español.** Un botón con etiqueta en inglés se nombra primero en español y luego tal como aparece (“haz clic en Cambiar, o Change, para elegir la carpeta adecuada”); nunca solo el término en inglés.
- **[G4] Los datos del ejercicio no se dictan.** Fechas, filtros y valores que el usuario indicó para la grabación son del ejercicio, no del tutorial: la narración dice la acción genérica (“selecciona la fecha”, “elige el periodo”), nunca el valor.
- **[D6] revisada.** En tutoriales la voz es más enérgica y animada que en v4: entusiasta, con sonrisa, ritmo ágil y énfasis en los verbos de acción.
