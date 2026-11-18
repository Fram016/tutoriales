# Brief: Cómo crear un contacto en Nexo CRM

<!-- Copiar a proyectos/<slug>/brief.md. Todo tutorial parte de este brief, antes del guion.
     Nunca escribir aquí contraseñas, tokens ni usuarios: solo nombres env:NAME. -->

## Objetivo

Crear un contacto nuevo en Nexo CRM (datos obligatorios + detalles) y verlo primero y resaltado en la lista de Contactos (instrucciones).

## Audiencia

Vendedores nuevos que registran su primer posible contacto de venta en Nexo CRM; sin conocimientos técnicos (instrucciones).

## Tipo de video

<!-- Uno por salida (reglas/reglas-video.md, Parte 3). Por defecto: TUT 16:9 + RED 9:16, ambos
     desde la misma lista de pasos; el vertical es RED, nunca un TUT recortado. -->

El usuario pidió "el tutorial completo en horizontal y un video corto para redes en vertical" → TUT 16:9 + RED 9:16 (dado, no propuesto).

| id | Tipo (TUT/RED/PRO/NOV) | Formato | Duración objetivo | Apertura | Cierre |
| --- | --- | --- | --- | --- | --- |
| tutorial | TUT | 16:9 | libre (≈ 50–70 s; sin capítulos, < 5 min) | En este video aprendes a crear un contacto. | Siguiente video: buscar un contacto. |
| redes | RED | 9:16 | 15–35 s | Gancho: ¿Conociste a alguien en una feria? | Mira el tutorial completo. |

## Enfoque

- Mostrar: login (TUT5, primer video de la serie), menú Contactos, botón "+ Nuevo contacto", formulario (obligatorios y detalles), Guardar contacto, aviso verde y fila nueva resaltada.
- Omitir: buscador (queda como siguiente video del TUT), Cancelar, validación con error, Oportunidades/Reportes. En RED: login, navegación a Contactos y campos opcionales (RED3).
- Tono: TUT pausado e informativo (TUT4, TUT6); RED rápido, texto en pantalla protagonista (RED3, RED4).

## Dispositivo

<!-- L2: escritorio → "haz clic"; celular → "toca". -->

- desktop / mobile: desktop ("haz clic").

## Glosario

<!-- L3: un término por concepto, definido antes del guion, con los sinónimos prohibidos.
     Idioma: español neutro de Ecuador, trato de tú, sin voseo ni modismos (L1, L4). -->

- contacto — no usar: cliente, prospecto, registro (ojo: "Prospecto" y "Cliente" son valores del campo Etapa; no se nombran en la narración para no chocar con L3)
- etapa — no usar: estado, fase
- origen — no usar: fuente, canal
- aviso — no usar: notificación, mensaje emergente
- Idioma: español neutro de Ecuador, trato de tú, sin voseo ni modismos (L1, L4).

## Fuentes

- App (ya levantada): http://127.0.0.1:8766/
- Videos de referencia: ninguno.
- Código fuente (solo lectura): demo-apps/nexo-crm/index.html
- Instrucciones del usuario (textuales):

> Nexo CRM es un CRM de ventas. Se ingresa con correo y contraseña. En el menú lateral está Contactos; ahí se ve la lista y el botón '+ Nuevo contacto'. El formulario pide Nombre, Apellido y Correo como obligatorios; también Empresa, Cargo, Teléfono, Etapa (Prospecto, Negociación, Cliente), Origen y Notas. Al guardar vuelve a la lista, el contacto aparece primero y resaltado, y sale un aviso verde. Hay un buscador arriba de la lista. Quiero el tutorial completo en horizontal y un video corto para redes en vertical sobre cómo crear un contacto. Está dirigido a vendedores nuevos que registran su primer posible cliente.

## Acceso

<!-- Solo nombres y rol de la cuenta; los valores viven en proyectos/<slug>/acceso.local.yaml (gitignored). -->

- Usuario: `env:NEXO_CRM_CONTACTO_V2_USER`
- Contraseña: `env:NEXO_CRM_CONTACTO_V2_PASSWORD`
- Rol de la cuenta demo: cuenta demo de ventas (app local de demostración, datos en memoria).
- Login verificado en ensayo: sí (ego-browser, ver worklog: ensayo). Sin 2FA, CAPTCHA ni SSO.

## Marca

- Sin marca entregada: paleta tomada de la app (código demo-apps/nexo-crm/index.html:7, :32).
- primary `#7c3aed` (morado de la app), accent `#ea580c` (naranja: contraste ≥ 3:1 sobre blanco para R3 y legible sobre fondo oscuro), background `#1f1235` (barra lateral de la app), text `#ffffff`, font `Segoe UI` (la de la app).
- Sin logo (indicación del usuario): `brand/` queda sin logo.svg/logo.png.

## Conocimiento de la app

<!-- Funciones, pantallas, reglas y selectores aprendidos; cada dato con su fuente:
     (instrucciones), (video <NAME> mm:ss), (código <ruta>:<línea>), (ensayo). -->

- Login: `#login-email`, `#login-password`, `#btn-login` ("Ingresar"); textos en tú ("Ingresa con tu cuenta de Nexo CRM") (código demo-apps/nexo-crm/index.html:76-86).
- Tras el login se ve Inicio con KPIs; menú lateral `#nav-contactos` (código :94-98).
- Contactos: título, botón `#btn-nuevo-contacto` "+ Nuevo contacto", buscador `#buscar`, tabla `#rows` con 3 contactos de ejemplo (código :116-121, :145-149).
- Formulario: `#c-nombre`, `#c-apellido`, `#c-empresa`, `#c-cargo`, `#c-email`, `#c-telefono`, `#c-etapa` (Prospecto/Negociación/Cliente), `#c-origen` (Sitio web/Referido/Feria/Llamada), `#c-notas`; `#btn-guardar` "Guardar contacto" (código :124-142).
- Validación: nombre, apellido y correo válido; si fallan muestra "Completa nombre, apellido y un correo válido." (código :178-181).
- Al guardar: el contacto se agrega primero (`#rows tr:first-child`, clase `new`, fondo `#f5f3ff`), vuelve a Contactos y muestra `#toast` "Contacto guardado correctamente" abajo a la derecha durante 2,5 s (código :170, :182-183, :59).
- Datos en memoria: cada carga de página empieza limpia (código :144).

## Flujo propuesto

1. Inicia sesión con el correo y la contraseña de la cuenta demo. **Login: solo TUT** (TUT5; RED lo omite, RED3/V5).
2. Abre Contactos desde el menú lateral; se ve la lista. **Navegación obvia: solo TUT** (RED3).
3. Haz clic en "+ Nuevo contacto"; se abre el formulario.
4. Completa los datos: Nombre, Apellido y Correo (obligatorios) + Empresa y Origen. Un solo paso (E2: un formulario = un paso); Cargo, Teléfono, Etapa y Notas no se llenan para que RED muestre lo mínimo (conflicto E2/RED3, ver worklog).
5. Haz clic en "Guardar contacto"; el contacto queda primero y resaltado en la lista (sale el aviso verde, no encuadrado: ver L7).

## Datos de la serie

<!-- TUT7: los mismos datos ficticios en todos los videos de la serie (clientes, productos, empresa).
     Textos cortos (C6). Nunca datos reales. -->

- Empresa: equipo de ventas de Nexo CRM (cuenta demo); contactos ya existentes en la app: Ana Torres (Andes Foods), Luis Pérez (Grupo Litoral), Carla Mena (Ferretería Sur).
- Personas: Sofía Vera, compras de Café Montaña (contacto nuevo de esta serie).
- Productos: no aplica.

## Datos de ejemplo

<!-- Datos ficticios a tipear en este video, tomados de Datos de la serie. -->

- Nombre: Sofía · Apellido: Vera · Correo: sofia@cafemontana.ec
- Empresa: Café Montaña · Origen: Feria (Etapa queda en su valor por defecto)
- Reservados para la serie (no tipeados aquí): Cargo: Compras · Teléfono: 099 222 3344 · Notas: Visitó el stand

## Preguntas abiertas

- L7 (pendiente del usuario): R2 (zoom al aviso ≥ 800 ms) vs C4 (fotograma > 70 % vacío) con el aviso solo en la esquina inferior derecha. Primero se siguió el skill de guion (`result: #toast`); qa.py dio C4 FAIL (90–94 % vacío), y en la ronda 1 se usó la fila nueva como resultado (`highlight`), igual que `_demo` (ver worklog).
- Sin logo: tutorial-render pide pedir el logo antes del render final; el usuario indicó "No logo", se renderiza sin logo.
