# Brief: Cómo descargar tus XML del SRI con Perseo XML

<!-- Nunca escribir aquí valores de acceso ni datos del contribuyente: solo nombres env:NAME. -->

## Objetivo

Descargar de una vez todos los XML de los comprobantes electrónicos emitidos y recibidos de una fecha en SRI en línea, con la extensión Perseo XML. Antes de descargar se configura la carpeta de descargas (S2).

## Audiencia

(propuesta) Contadores y emprendedores ecuatorianos que ya usan SRI en línea y bajan los comprobantes uno por uno para importarlos en su sistema contable. Ya saben iniciar sesión en el SRI, pero no conocen la extensión.

## Tipo de video

| id | Tipo | Formato | Duración objetivo | Apertura | Cierre |
| --- | --- | --- | --- | --- | --- |
| tutorial | TUT | 16:9 | libre (~70–90 s) | Objetivo: "Aprendes a descargar XML." + requisito (Perseo XML instalada y sesión en el SRI) | Siguiente video: importar los XML (propuesto) |
| redes | RED | 9:16 | 15–35 s (~25 s) | Gancho: "¿Cientos de XML?" | "Mira nuestro perfil." + destino (N8, propuesto) |

Es el par por defecto (propuesto, `tutorial` decide el tipo). El vertical es un RED con sus propios pasos, nunca un TUT recortado.

## Enfoque

- Mostrar: la interfaz de la extensión (S5); Carpeta de descargas antes de descargar (S2); emitidos con "XML Desde el RIDE"; recibidos con "XML Para importar"; el resumen de la última descarga.
- Omitir: el login (lo hace el usuario: la toma empieza con la sesión abierta, S3), PDF/RIDE, "Borrar anteriores", las tarjetas de publicidad del popup y el clic en "Cambiar" (abre el selector de carpetas nativo de Windows, que no se puede grabar).
- Tono: informativo y tranquilo (TUT4, TUT6); en redes, rápido y directo.

## Dispositivo

- desktop: "haz clic" (L2).

## Glosario

Español neutro de Ecuador, trato de tú (L1, L4).

- comprobante — no usar: documento, archivo, factura (salvo el tipo "Factura" que muestra el SRI)
- extensión (Perseo XML) — no usar: complemento, plugin, programa
- descargar — no usar: bajar
- carpeta de descargas — no usar: directorio, ruta
- emitidos / recibidos: las etiquetas del SRI y de la extensión, tal cual

## Paleta (de la app)

Sale del popup de la extensión, `popup.html`:

- primary: `#ca4100` (`--primario`, popup.html:32; color de marca del popup)
- background: `#09090b` (`--texto`, popup.html:36; el negro del logo Perseo)
- surface: `#09090b` (banda de subtítulos = color oscuro de la marca)
- on_surface: `#ffffff`
- text: `#ffffff` (sobre las tarjetas oscuras)
- font: `Instrument Sans` (popup.html:11–27)

## Historia / escenario

- Escenario: ninguna. El gancho plantea un problema simple: descargar cientos de XML uno por uno desde el SRI.
- Datos que la cuentan: el resumen de la extensión ("Descargados") muestra que todo bajó de una vez.

## Destino del CTA

- (propuesto) "en el enlace de nuestro perfil". Todavía no se conoce el destino real: está en Preguntas abiertas.

## Fuentes

- App: SRI en línea (sesión real del usuario). Inicio de la toma: página de perfil `https://srienlinea.sri.gob.ec/sri-en-linea/contribuyente/perfil`, y desde ahí el menú. El enlace profundo de Consultas (S4) redirigió al login en el intento anterior.
- Enlace de Consultas (S4): `https://srienlinea.sri.gob.ec/comprobantes-electronicos-internet/pages/consultas/menu.jsf?...` (ver odd/tasks/perseo-xml.md).
- Videos de referencia: `referencias/uso-1` (emitidos, 164 s) y `referencias/uso-2` (recibidos + carpeta, 57 s).
- Extensión (solo lectura): `C:\Users\Francisco Lopez\Downloads\perseo-xml-1.0.9\perseo-xml`, ID `jakigokhcbfpebeiolidapdkeooiapeb`, versión de pruebas sin empaquetar.
- Logo: `brand/logo.png`; icono de la barra: `brand/ext-icon48.png`.
- Instrucciones del usuario (textuales):

> Ahora vamos a hacer otro tutorial, es para la herramienta llamada Perseo XML primero es este video ... luego este video ... si quieres hazlo desde cero porque tambien hay una opcion de configurar carpeta que la menciono hasta el final y debe ser antes de hacer las descargas del XML, censura nombres y credenciales si haces el tutorial desde cero este el link del SRI ... adicional se debe ver la interfaz de la extension, este es el logo a usar

> Falta la censura del correo tambien y numero de contacto

Respuestas: enfoque "Desde cero en ego-lite (recomendado)"; carpeta "Dentro de la extensión"; censura "RUC y nombre del contribuyente" (+ correo y teléfono, L9).

Conflicto: en el video (uso-2 00:36–00:53) la carpeta se menciona al final. Por instrucción del usuario va **antes** de las descargas.

## Acceso

- La cuenta del SRI es real y la sesión la abre el usuario en ego-lite. El agente nunca escribe valores de acceso y no hay `env:` de usuario ni de contraseña.
- Censura (S3, L9): `env:PERSEO_XML_RUC`, `env:PERSEO_XML_NOMBRE`, `env:PERSEO_XML_EMAIL`, `env:PERSEO_XML_TELEFONO` (valores solo en `acceso.local.yaml`). Se ven en el encabezado del SRI, en la página de perfil, en el campo RUC de la consulta y dentro de las claves de acceso de los emitidos.
- Datos de terceros (propuesto): en la tabla de recibidos aparecen el RUC y la razón social del emisor y la clave de acceso. Se censuran por selector (columnas 2 y 4 de `frmPrincipal:tablaCompRecibidos_data`), pendiente de confirmar en el ensayo.
- Login verificado en ensayo: **no**. La sesión expiró en el intento anterior y la toma depende de que el usuario inicie sesión justo antes.

## Conocimiento de la app

- Menú del portal: hamburguesa arriba a la izquierda → FACTURACIÓN ELECTRÓNICA → Producción → Consultas (video uso-1 00:10–00:17, fotograma 4; uso-2 fotograma 3).
- "Consulta de comprobantes electrónicos" muestra los enlaces "Comprobantes electrónicos emitidos" y "Comprobantes electrónicos recibidos" (video uso-1 00:17, fotograma 6).
- Emitidos: el campo "Fecha emisión" es `frmPrincipal:calendarFechaDesde_input`, un calendario dd/mm/aaaa (código content-script.js:307). La fecha tiene que ser anterior a hoy: si no, aparece el aviso "La fecha ingresada debe ser menor a la fecha actual" (video uso-1 00:36, fotograma 10). El botón es "Consultar" y la tabla de resultados es `frmPrincipal:tablaCompEmitidos` (código content-script.js:499).
- Recibidos: "Periodo emisión" son tres listas, `frmPrincipal:ano`, `frmPrincipal:mes` y `frmPrincipal:dia` (código content-script.js:21–23). La tabla es `frmPrincipal:tablaCompRecibidos` (código content-script.js:499). La página tiene el sello de reCAPTCHA (video uso-2 fotograma 6).
- "Anterior" vuelve a la lista de consultas (video uso-1 fotograma 8).
- Durante la consulta aparece una carga "Espere por favor" que cubre toda la pantalla (video uso-1 fotograma 11). Se espera la tabla con `wait:`.
- Popup: tiene "Comprobantes recibidos" con `#boton1` (XML, Para importar) y `#boton2` (PDF), y "Comprobantes emitidos" con `#boton3` (PDF) y `#boton4` (XML, Desde el RIDE). Al hacer clic, el botón pasa a "En proceso..." (deshabilitado, sin `<b>`) y vuelve a su contenido original con `procesoFinalizado` (código popup-script.js:53–70). El resumen `#download-info` se refresca cada 2 s y su contador es `#texto_correctos` ("Descargados") (código popup.html:622–646, popup-script.js:316). "Carpeta de descargas" es `#configure-folder` y abre `chrome://settings/downloads` en una pestaña nueva (código popup-script.js:85).
- Chrome Configuración → Descargas: tiene "Ubicación" y "Cambiar" dentro del shadow DOM. El recorder no llega ahí, así que no hay `focus` y la cámara queda en plano general.

## Flujo propuesto

1. `carpeta`: abre Perseo XML y haz clic en Carpeta de descargas. Se ve Ubicación / Cambiar, sin hacer clic en Cambiar. Vuelve al SRI.
2. `consultas`: menú → Facturación Electrónica → Producción → Consultas (navegación obvia; RED la omite).
3. `emitidos`: clic en Comprobantes electrónicos emitidos (navegación; RED la omite).
4. `fecha-emitidos`: escribe la fecha de emisión.
5. `consultar-emitidos`: Consultar → tabla de emitidos.
6. `descargar-emitidos`: abre Perseo XML → XML Desde el RIDE → resumen Descargados.
7. `recibidos`: Anterior → Comprobantes electrónicos recibidos (navegación; RED la omite).
8. `fecha-recibidos`: año, mes y día del periodo.
9. `consultar-recibidos`: Consultar → tabla de recibidos.
10. `descargar-recibidos`: abre Perseo XML → XML Para importar → resumen Descargados.

Login: no aparece en ningún video (lo hace el usuario antes de la toma). RED: `carpeta`, `consultar-emitidos`, `descargar-emitidos`, `descargar-recibidos`.

## Datos de la serie

- No se escribe ningún dato inventado: el SRI muestra datos reales del contribuyente y de terceros, y se censuran.
- Fechas de consulta (propuestas, a confirmar en el ensayo con pocos comprobantes): emitidos `15/11/2026`; recibidos `2026 / Noviembre / 1` (6 comprobantes en la referencia uso-2).

## Datos de ejemplo

- Fecha emisión: `15/11/2026` (provisional).
- Periodo emisión: `2026`, `Noviembre`, `1`.

## Preguntas abiertas

1. Destino del CTA del video de redes y siguiente video del tutorial: se propone "enlace de nuestro perfil" y "importar los XML". ¿Cuáles son los reales?
2. Fechas de la consulta: hacen falta una fecha de emitidos y un día de recibidos con pocos comprobantes, porque las descargas reales caen en el disco del usuario. ¿Las confirma el usuario o se eligen en el ensayo?
3. ¿Se censuran también el RUC y la razón social de los emisores y las claves de acceso de los recibidos (datos de terceros)? Se propone que sí.
4. ¿Se acepta que la pantalla de Configuración → Descargas se muestre en plano general (≈ 2,5 s, sin zoom a "Cambiar")?
5. La página de recibidos usa reCAPTCHA. Si bloquea la consulta automatizada, la toma de recibidos necesitará otra salida.
