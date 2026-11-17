# Brief: Cómo crear tu primer contacto en Nexo CRM

<!-- Copiar a proyectos/<slug>/brief.md. Todo tutorial parte de este brief, antes del guion.
     Nunca escribir aquí contraseñas, tokens ni usuarios: solo nombres env:NAME. -->

## Objetivo

Que un vendedor nuevo cargue su primer prospecto en Nexo CRM y lo vea guardado: el contacto aparece primero y resaltado en la lista, con el aviso verde "Contacto guardado correctamente", y lo encuentra con el buscador. (propuesto a partir de las instrucciones)

## Audiencia

Vendedores nuevos que usan Nexo CRM por primera vez para cargar prospectos; saben vender, no necesariamente usar un CRM. Sin conocimientos técnicos. (instrucciones: "vendedores nuevos que cargan su primer prospecto")

## Enfoque

- Mostrar: ingreso con correo y contraseña, menú lateral → Contactos, botón "+ Nuevo contacto", los tres campos obligatorios (Nombre, Apellido, Correo), los datos opcionales útiles para ventas (Empresa, Cargo, Teléfono, Etapa, Origen, Notas), Guardar contacto, contacto primero y resaltado + aviso verde, buscador.
- Omitir: Inicio/KPI (solo de paso tras el login), Oportunidades y Reportes ("Próximamente"), botón Cancelar, mensaje de error de validación (camino feliz; se menciona en la narración que los campos con asterisco son obligatorios).
- Tono: cercano, de compañero que te enseña ("Ahora cargamos…"), español latinoamericano neutro, sin voseo aunque la app lo use en sus textos.
- Duración 16:9 (completo): 60-90 s (instrucciones).
- Duración 9:16 (resumen, ≤ 60-70 s): menos de 45 s (instrucciones; más estricto que el máximo del skill).

## Fuentes

- App (ya levantada): http://127.0.0.1:8766/ (HTML local, datos en memoria; cada carga empieza limpia)
- Videos de referencia: ninguno
- Código fuente (solo lectura): `demo-apps/nexo-crm/index.html`
- Marca: no se entregó; se propone paleta derivada de la app (violeta `#7c3aed`), sin logo. Ver Preguntas abiertas.
- Instrucciones del usuario (textuales):

> Nexo CRM es un CRM de ventas. Se ingresa con correo y contraseña. En el menú lateral está Contactos; ahí se ve la lista y el botón '+ Nuevo contacto'. El formulario pide Nombre, Apellido y Correo como obligatorios; también Empresa, Cargo, Teléfono, Etapa (Prospecto, Negociación, Cliente), Origen y Notas. Al guardar vuelve a la lista, el contacto aparece primero y resaltado, y sale un aviso verde. Hay un buscador arriba de la lista. Enfoque: vendedores nuevos que cargan su primer prospecto; tono cercano; 16:9 de 60-90 s y 9:16 de menos de 45 s.

## Acceso

<!-- Solo nombres y rol de la cuenta; los valores viven en proyectos/<slug>/acceso.local.yaml (gitignored). -->

- Usuario: `env:NEXO_CRM_CONTACTO_USER`
- Contraseña: `env:NEXO_CRM_CONTACTO_PASSWORD`
- Rol de la cuenta demo: cuenta demo única de la app ("equipo de ventas"); dominio `.demo`, no es una cuenta real.
- Login verificado en ensayo: sí (ego-browser, 2026-11-17; sin 2FA, CAPTCHA ni SSO)

## Conocimiento de la app

- Login: formulario `#login-form` con `#login-email` (name=email, label "Correo electrónico") y `#login-password` (name=password, label "Contraseña"); botón `#btn-login` "Ingresar". Error: `#login-error` "Correo o contraseña incorrectos." (código demo-apps/nexo-crm/index.html:82-88)
- Tras el login se oculta `#login`, se muestra `#app` y la vista `#view-inicio` ("Hola, equipo de ventas 👋"); el correo de la cuenta demo aparece en el encabezado `#user-email`. (código index.html:173-181)
- Menú lateral: `#nav-inicio`, `#nav-contactos`, `#nav-oportunidades`, `#nav-reportes` (enlaces `<a>` sin href, con data-view). (código index.html:96-99)
- Contactos: `#view-contactos`, título "Contactos", botón `#btn-nuevo-contacto` "+ Nuevo contacto", buscador `#buscar` (placeholder "Buscar por nombre o empresa..."), tabla con filas en `#rows`; 3 contactos iniciales (Ana Torres, Luis Pérez, Carla Mena). (código index.html:114-120, 155-159)
- Buscador: filtra en cada tecla por nombre + apellido + empresa, sin distinguir mayúsculas. (código index.html:162-168, 185)
- Formulario `#contact-form` en `#view-nuevo`: `#c-nombre`*, `#c-apellido`*, `#c-empresa`, `#c-cargo`, `#c-email`* (label "Correo electrónico *"), `#c-telefono`, `#c-etapa` (select: Prospecto, Negociación, Cliente; por defecto Prospecto), `#c-origen` (select: Sitio web, Referido, Feria, Llamada), `#c-notas` (textarea); botones `#btn-cancelar` y `#btn-guardar` "Guardar contacto". (código index.html:122-144)
- Validación: nombre y apellido no vacíos y correo con formato `x@y.z`; si falla muestra `#form-error` "Completá nombre, apellido y un correo válido." (código index.html:186-191)
- Al guardar: el contacto se inserta primero, su fila lleva la clase `tr.new` (fondo violeta claro), vuelve a Contactos y aparece `#toast` "Contacto guardado correctamente" durante 2,5 s. (código index.html:192-193)
- La app usa voseo en sus textos ("Ingresá con tu cuenta", "Organizá…", "Completá…"); la narración no debe copiarlo. (código index.html:78, 86, 140)
- Paleta de la app: violeta `--brand #7c3aed`, oscuro `--brand-d #5b21b6`, barra lateral `#1f1235`, fuente "Segoe UI". (código index.html:7, 9, 34)

## Flujo propuesto

1. Ingresamos con correo y contraseña → se ve Inicio ("Hola, equipo de ventas").
2. Abrimos Contactos en el menú lateral → se ve la lista y "+ Nuevo contacto".
3. Tocamos "+ Nuevo contacto" → se abre el formulario.
4. Completamos los obligatorios: Nombre, Apellido, Correo → campos llenos.
5. Agregamos Empresa, Cargo y Teléfono → campos llenos.
6. Elegimos Etapa Prospecto y Origen Feria, y escribimos una nota → selects y notas llenos.
7. Tocamos "Guardar contacto" → vuelve a la lista, el contacto aparece primero y resaltado, y sale el aviso verde.
8. Buscamos por apellido en el buscador → la lista muestra solo el nuevo contacto.

## Datos de ejemplo

- Nombre: Sofía
- Apellido: Ramírez
- Empresa: Café Montaña
- Cargo: Jefa de compras
- Correo: sofia.ramirez@cafemontana.com
- Teléfono: 099 456 7890
- Etapa: Prospecto
- Origen: Feria
- Notas: Conocimos en la feria de Quito. Quiere una cotización para el próximo mes.
- Búsqueda: Ramírez

## Preguntas abiertas

- Marca: no se entregó logo ni colores; se usa la paleta de la app (primario `#7c3aed`, acento `#a78bfa`, fondo `#1f1235`, texto `#ffffff`, fuente Segoe UI) y sin logo. No bloquea el guion; el render mostrará "sin logo".
- El correo de la cuenta demo se ve al tipearlo en el login y en el encabezado de la app. Es una cuenta demo (dominio `.demo`), así que se acepta en el video; la contraseña se ve enmascarada. No bloquea.
