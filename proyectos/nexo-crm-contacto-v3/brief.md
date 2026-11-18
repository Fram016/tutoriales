# Brief: Cómo crear un contacto en Nexo CRM

<!-- Nunca escribir aquí contraseñas, tokens ni usuarios: solo nombres env:NAME. -->

## Objetivo

Registrar un contacto nuevo en Nexo CRM (Contactos → + Nuevo contacto → datos → Guardar contacto) y verlo primero y resaltado en la lista. (instrucciones)

## Audiencia

Vendedores nuevos que registran su primer posible contacto de venta; sin experiencia previa en Nexo CRM. (instrucciones)

## Tipo de video

Pedido explícito del usuario: "tutorial completo en horizontal y un video corto para redes en vertical".

| id | Tipo (TUT/RED/PRO/NOV) | Formato | Duración objetivo | Apertura | Cierre |
| --- | --- | --- | --- | --- | --- |
| tutorial | TUT | 16:9 | libre (~45–60 s) | Objetivo: "Aprendes a registrar contactos." | Siguiente video: buscar un contacto |
| redes | RED | 9:16 | 15–35 s (~20 s) | Gancho: "¿Contacto de feria?" | Mira nuestro perfil + "Tutorial completo en el enlace de nuestro perfil" (N8) |

## Enfoque

- Mostrar: ubicación de Contactos en el menú lateral (C7), botón "+ Nuevo contacto", el formulario completo, el aviso verde y la fila nueva resaltada.
- Omitir en RED: login, navegación a Contactos, campos opcionales que no cuentan la historia (Cargo, Teléfono, Etapa).
- Tono: TUT calmado e informativo (TUT4, TUT6); RED rápido y protagonizado por el texto (RED3, RED4).

## Dispositivo

- desktop → "haz clic" (L2)

## Glosario

- contacto — no usar: cliente, prospecto, registro (nota: "Prospecto" y "Cliente" solo como valores de Etapa, entre comillas, que es lo que muestra la interfaz)
- Etapa, Origen, Notas — tal cual los muestra la interfaz
- Idioma: español neutro de Ecuador, trato de tú, sin voseo ni modismos (L1, L4). La app usa "Ingresa" (tú): sin voseo.

## Paleta (de la app)

- primary: `#7c3aed` — `--brand`, botón primario y avatar (código demo-apps/nexo-crm/index.html:7, :15)
- background: `#4c1d95` — violeta oscuro de la marca, inicio del degradado del hero de login (código demo-apps/nexo-crm/index.html:21)
- surface: `#4c1d95` — banda de subtítulos = background (morado, no negro puro; N5)
- on_surface: `#ffffff`
- Referencias: `--brand-d` `#5b21b6` (hover, :7), menú lateral `#1f1235` (:33), fila nueva `#f5f3ff` (:51). Fuente de la app: "Segoe UI" (:9).

## Historia / escenario

- Escenario: conociste a una persona en una feria y la registras como posible venta.
- Datos que la cuentan: Origen "Feria" (explicado: "porque la conociste ahí"), Notas "Conocida en la feria Expo" (25 caracteres, C6), Etapa "Prospecto".

## Destino del CTA

- "en el enlace de nuestro perfil" (propuesto, valor por defecto del skill; el usuario no lo indicó).

## Fuentes

- App (ya levantada): http://127.0.0.1:8766/ (datos en memoria; cada carga parte limpia)
- Videos de referencia: ninguno
- Código fuente (solo lectura): demo-apps/nexo-crm/index.html
- Instrucciones del usuario (textuales):

> Nexo CRM es un CRM de ventas. Se ingresa con correo y contraseña. En el menú lateral está Contactos; ahí se ve la lista y el botón '+ Nuevo contacto'. El formulario pide Nombre, Apellido y Correo como obligatorios; también Empresa, Cargo, Teléfono, Etapa (Prospecto, Negociación, Cliente), Origen y Notas. Al guardar vuelve a la lista, el contacto aparece primero y resaltado, y sale un aviso verde. Hay un buscador arriba de la lista. Quiero el tutorial completo en horizontal y un video corto para redes en vertical sobre cómo crear un contacto. Está dirigido a vendedores nuevos que registran su primer posible cliente.

## Acceso

- Usuario: `env:NEXO_CRM_CONTACTO_V3_USER`
- Contraseña: `env:NEXO_CRM_CONTACTO_V3_PASSWORD`
- Rol de la cuenta demo: cuenta demo de ventas (app local, datos en memoria)
- Login verificado en ensayo: ver worklog (ensayo ego-browser)

## Conocimiento de la app

- Login: `#login-email`, `#login-password`, `#btn-login`; error `#login-error` (código demo-apps/nexo-crm/index.html:76-80)
- Menú lateral: `#nav-contactos` (código :90); inicio muestra KPI `#kpi-contactos` (:102)
- Contactos: `#btn-nuevo-contacto` "+ Nuevo contacto", buscador `#buscar`, filas `#rows` (:110-113)
- Formulario `#contact-form`: `#c-nombre`, `#c-apellido`, `#c-empresa`, `#c-cargo`, `#c-email`, `#c-telefono`, `#c-etapa` (select), `#c-origen` (select: Sitio web, Referido, Feria, Llamada), `#c-notas`; cada campo con `label[for]` (:120-130)
- Guardar: `#btn-guardar` "Guardar contacto"; validación nombre, apellido y correo (:135, :185)
- Al guardar: vuelve a Contactos, fila nueva primera con clase `tr.new`, aviso `#toast` "Contacto guardado correctamente" 2,5 s (:144, :189-190)

## Flujo propuesto

1. login — Inicia sesión (correo + contraseña + Ingresar) → Inicio. [login: RED lo omite]
2. contactos — Clic en Contactos del menú lateral → lista. [navegación obvia: RED la omite]
3. nuevo — Clic en "+ Nuevo contacto" → formulario.
4. datos — Completa el formulario (un solo paso, E2): Nombre, Apellido, Correo, Empresa, Cargo, Teléfono, Etapa, Origen, Notas. [opcionales que RED omite con `videos[].omit`: `#c-cargo`, `#c-telefono`, `#c-etapa`]
5. guardar — Clic en "Guardar contacto" → aviso verde (`#toast`) + fila nueva resaltada (`#rows tr:first-child`).

## Datos de la serie

- Empresa: Café Andino
- Personas: Sofía Vera (Gerente de compras)
- Productos: —

## Datos de ejemplo

- Nombre "Sofía", Apellido "Vera", Correo "sofia@cafeandino.ec", Empresa "Café Andino", Cargo "Compras", Teléfono "099 245 1180", Etapa "Prospecto", Origen "Feria", Notas "Conocida en la feria Expo".

## Preguntas abiertas

- Destino del CTA de redes: se propone "en el enlace de nuestro perfil" (el usuario no lo dio).
- Logo: no hay logo; los videos salen sin logo (brand/ vacío). El skill de render pide preguntar por él antes del render final: queda abierto.
- Siguiente video de la serie: se propone "buscar un contacto" (la app tiene buscador).
