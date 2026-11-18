# Brief: Crear un contacto en Nexo CRM

<!-- Nunca escribir aquí contraseñas, tokens ni usuarios: solo nombres env:NAME. -->

## Objetivo

Registrar un contacto nuevo (con Origen “Feria” y una nota) y verlo primero y resaltado en la lista. (instrucciones)

## Audiencia

Vendedores nuevos que registran su primer posible cliente; sin conocimientos técnicos. (instrucciones)

## Tipo de video

| id | Tipo (TUT/RED/PRO/NOV) | Formato | Duración objetivo | Apertura | Cierre |
| --- | --- | --- | --- | --- | --- |
| tutorial | TUT | 16:9 | libre (~50–60 s) | “Registra contactos de feria.” | Siguiente video: buscar un contacto |
| redes | RED | 9:16 | 15–35 s (~20 s) | Gancho: “¿Nuevo contacto?” + tarjeta “¿Lo conociste en una feria?” | Mira nuestro perfil + destino (N8) |

Tipos dados por el usuario (“tutorial completo en horizontal y un video corto para redes en vertical”).

## Enfoque

- Mostrar: login (primer video de la serie, TUT5), menú Contactos, “+ Nuevo contacto”, formulario completo, Guardar, aviso verde, fila nueva resaltada.
- Omitir: Cargo (opcional, no aporta a la historia); en RED además login, navegación, Empresa, Teléfono y Etapa.
- Tono: TUT pausado e informativo (TUT4, TUT6); RED rápido (RED3).

## Dispositivo

- desktop (“haz clic”, L2)

## Glosario

- contacto — no usar: cliente, registro (la app dice “contacto”). “Prospecto”, “Negociación” y “Cliente” solo como nombres de opciones de Etapa.
- Idioma: español neutro de Ecuador, tú; la app usa “Ingresa con tu cuenta” (tú, sin voseo).

## Paleta (de la app)

- primary: `#7c3aed` (`--brand`, botón “+ Nuevo contacto”) (código demo-apps/nexo-crm/index.html:7; ensayo getComputedStyle)
- background: `#1f1235` (menú lateral `aside`) (código demo-apps/nexo-crm/index.html:35; ensayo)
- surface: `#1f1235` (banda de subtítulos = oscuro de la marca)
- on_surface: `#ffffff`
- Secundario de la app (hover): `#5b21b6` (`--brand-d`, código :7). Fuente: Segoe UI (código :9).

## Historia / escenario

- Escenario: conociste a Sofía Vera en una feria y la registras como contacto nuevo.
- Datos que la cuentan: Origen “Feria”; Notas “Conocida en la feria de Quito” (29 caracteres, C6); Etapa “Prospecto” porque recién la conociste.

## Destino del CTA

- “en el enlace de nuestro perfil” (propuesto: el usuario no dio destino).

## Fuentes

- App (ya levantada): http://127.0.0.1:8766/
- Código fuente (solo lectura): demo-apps/nexo-crm/index.html
- Instrucciones del usuario (textuales):

> Nexo CRM es un CRM de ventas. Se ingresa con correo y contraseña. En el menú lateral está Contactos; ahí se ve la lista y el botón '+ Nuevo contacto'. El formulario pide Nombre, Apellido y Correo como obligatorios; también Empresa, Cargo, Teléfono, Etapa (Prospecto, Negociación, Cliente), Origen y Notas. Al guardar vuelve a la lista, el contacto aparece primero y resaltado, y sale un aviso verde. Hay un buscador arriba de la lista. Quiero el tutorial completo en horizontal y un video corto para redes en vertical sobre cómo crear un contacto. Está dirigido a vendedores nuevos que registran su primer posible cliente.

## Acceso

- Usuario: `env:NEXO_CRM_CONTACTO_V4_USER`
- Contraseña: `env:NEXO_CRM_CONTACTO_V4_PASSWORD`
- Rol de la cuenta demo: vendedor demo (datos en memoria; cada carga empieza limpia)
- Login verificado en ensayo: sí (sin 2FA/CAPTCHA/SSO)

## Conocimiento de la app

- Login: `#login-email`, `#login-password`, `#btn-login` (código :77-80); al entrar muestra Inicio.
- Menú lateral: `#nav-contactos` (código :90). Lista: `#rows`, buscador `#buscar` arriba (código :111-113).
- Botón `#btn-nuevo-contacto` “+ Nuevo contacto” (código :110).
- Formulario `form#contact-form` (contenedor único de todos los campos, 880×592 px; ensayo): `#c-nombre`, `#c-apellido`, `#c-empresa`, `#c-cargo`, `#c-email`, `#c-telefono`, `select#c-etapa`, `select#c-origen` (Sitio web, Referido, Feria, Llamada), `#c-notas`; `#btn-guardar` (código :118-135).
- Al guardar: el contacto va primero con clase `tr.new` (fondo `#f5f3ff`), vuelve a Contactos y aparece `#toast` verde “Contacto guardado correctamente” abajo a la derecha durante 2,5 s (código :186-190; ensayo: visible a 1,2 s).

## Flujo propuesto

1. Inicia sesión (login; RED lo omite).
2. Abre Contactos `#nav-contactos` (navegación obvia; RED lo omite).
3. Haz clic en “+ Nuevo contacto” `#btn-nuevo-contacto`.
4. Completa los datos (un solo paso, un plano de formulario): Nombre, Apellido, Empresa (opcional `#c-empresa`), Correo, Teléfono (opcional `#c-telefono`), Etapa (`#c-etapa`, se deja en Prospecto), Origen Feria, Notas.
5. Guarda el contacto `#btn-guardar` → aviso `#toast` → fila nueva `#rows tr:first-child`.

## Datos de la serie

- Empresa: Café Montaña
- Personas: Sofía Vera (Compras), sofia@cafemontana.ec, 099 245 7788
- Productos: —

## Datos de ejemplo

- Nombre “Sofía”, Apellido “Vera”, Empresa “Café Montaña”, Correo “sofia@cafemontana.ec”, Teléfono “099 245 7788”, Etapa “Prospecto”, Origen “Feria”, Notas “Conocida en la feria de Quito”.

## Preguntas abiertas

- Destino del CTA de redes: se usa el propuesto “en el enlace de nuestro perfil”; confirmar.
- Logo: no hay logo; la marca se muestra solo con el nombre “Nexo CRM” y la paleta.
- Siguiente video propuesto: “buscar un contacto” (usa el buscador de la lista).
