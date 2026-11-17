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
