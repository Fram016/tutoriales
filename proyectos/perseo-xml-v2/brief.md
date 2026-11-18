# Brief: Perseo XML: tus comprobantes del SRI

<!-- Rehecho desde cero (odd/tasks/reglas-ronda4.md T6, S1–S5). Sin valores de credenciales ni de censura. -->

## Objetivo

Descargar de una vez los XML de los comprobantes emitidos y recibidos del SRI con la extensión Perseo XML, después de revisar la carpeta de descargas.

## Audiencia

Contadores y usuarios de Perseo que descargan comprobantes del SRI para importarlos; saben entrar a SRI en línea, no conocen la extensión (propuesta).

## Tipo de video

| id | Tipo (TUT/RED/PRO/NOV) | Formato | Duración objetivo | Apertura | Cierre |
| --- | --- | --- | --- | --- | --- |
| tutorial | TUT | 16:9 | libre, 3 partes (N16) | "Aprendes a descargar XML." | ninguno (N27, S3): termina en el resumen de la última descarga |

Solo TUT 16:9 en esta ronda (S1); no hay RED.

## Enfoque

- Mostrar: la extensión como protagonista (abrirla, carpeta, descargar), el SRI solo para consultar; el resumen de la extensión después de CADA descarga (N18).
- Omitir: login (la sesión del SRI ya está abierta, es requisito), PDF RIDE, Borrar anteriores.
- Tono: informativo y pausado (TUT4, TUT6).

## Dispositivo

- desktop: "haz clic" (L2).

## Glosario

- comprobante — no usar: documento, archivo
- extensión — no usar: complemento, plugin
- descargar — no usar: bajar
- carpeta de descargas — no usar: directorio, ruta
- Etiquetas exactas: "Carpeta de descargas", "Comprobantes electrónicos emitidos/recibidos", "Consultar", "Anterior", "XML Desde el RIDE", "XML Para importar", "Periodo emisión", "Change" (la configuración de ego está en inglés).

## Paleta (de la app)

- primary: `#ca4100` (`--primario`, código popup.html:31)
- background: `#09090b` (`--texto`, color oscuro de Perseo, popup.html:35)
- surface: `#09090b`
- on_surface: `#ffffff`
- logo (N24): `brand/logo.png` es negro; compose genera la variante clara para la tarjeta oscura (S4).
- Fuente: Segoe UI (Instrument Sans no tiene @font-face en hyperframes).

## Datos sensibles

- Criterio (N25, S5): difuminado uniforme en todo el video.
- Categorías: identidad del contribuyente (RUC, nombre, correo, teléfono), RUC y razón social de terceros, claves de acceso, montos, ruta de carpeta con el usuario de Windows.
- Dónde aparecen (pantalla → censor):
  - Perfil, encabezado de todas las páginas del SRI, campo RUC de las consultas → `censor.text` env:PERSEO_XML_RUC, env:PERSEO_XML_NOMBRE, env:PERSEO_XML_EMAIL, env:PERSEO_XML_TELEFONO.
  - Tabla de emitidos → `td:nth-child(3)` clave, `6/7/8` montos (ensayo: cabeceras leídas en vivo).
  - Tabla de recibidos → `td:nth-child(2)` RUC y razón social emisor, `4` clave, `7/8/9` montos.
  - chrome://settings/downloads → patrón `'[A-Za-z]:\\Users\\[^\\]+'`.

## Historia / escenario

- Escenario: ninguna. El problema simple: bajar uno por uno los XML del SRI toma tiempo; la extensión los descarga todos de una consulta.
- Datos que la cuentan: consultas cortas (una fecha, un punto de emisión) para que la descarga sea rápida.

## Destino del CTA

- No aplica (TUT sin cierre, N27).

## Fuentes

- App (ya levantada): https://srienlinea.sri.gob.ec/sri-en-linea/contribuyente/perfil (sesión real del usuario, login automático autorizado: odd/tasks/perseo-xml.md L10).
- Videos de referencia: conocimiento de `proyectos/perseo-xml/` (worklog); no se reutilizan su brief ni su tutorial.yaml.
- Código fuente (solo lectura): extensión `perseo-xml-1.0.9/perseo-xml` (popup.html, popup-script.js, publicidad.js, content-script.js).
- Instrucciones del usuario (textuales): reglas/reglas-video.md §Parte 6 (N13–N27) y odd/tasks/reglas-ronda4.md S1–S5:

> "El que me interesa es el Perseo xml tutorial nos basaremos en ese" · "quita el ultimo espacio que dice siguiente video no es necesario" · "Y el logo de Perseo al inicio no se distingue" · "Define un criterio: o todo es dato de demostración, o se difumina igual en todo el video."

## Acceso

- Usuario: `env:PERSEO_XML_SRI_USER`
- Contraseña: `env:PERSEO_XML_SRI_PASSWORD`
- Rol de la cuenta: contribuyente real (autorizado por el usuario para esta sesión).
- Login verificado en ensayo: sí (una vez con `tools/sri_login.mjs`, espacio 64, 2026-11-18).

## Conocimiento de la app

- Popup: `body` de 460 px (código popup.html:53); promo única `#publicidad-perseo` (popup.html:611, publicidad.js:256) → `surfaces.popup.hide`.
- Botones: `#boton1` XML Para importar (recibidos), `#boton4` XML Desde el RIDE (emitidos); al hacer clic el botón dice "En proceso..." y recupera su `<b>XML</b>` al terminar (popup-script.js:57-70); el resumen se refresca cada 2 s (popup-script.js:319); `.estadisticas` = Descargados + Con error.
- `#configure-folder` abre `chrome://settings/downloads` (pestaña nueva); el botón "Change" (`#changeDownloadsPath`) abre el selector nativo de Windows: se muestra, nunca se hace clic (L2).
- "XML Desde el RIDE" no admite Notas de Crédito (codDoc 04): se deja el tipo Factura.
- Emitidos: con establecimiento elegido el punto de emisión es obligatorio ("Ingrese el punto de emisión") (ensayo).
- "Anterior" recarga la página entera durante varios segundos (ensayo): el paso espera el enlace visible.
- Menú del SRI: enlaces ocultos duplicados → selectores en `li.sri-listaLinks` y en el panelmenu (ensayo).

## Flujo propuesto

Parte 1: Configurar la carpeta
1. Abre Perseo XML (extensión).
2. Haz clic en Carpeta de descargas → configuración del navegador con "Change" resaltado, ruta difuminada (extensión).

Parte 2: Comprobantes emitidos
3. En el SRI, abre el menú → Facturación Electrónica → Producción → Consultas (SRI).
4. Haz clic en Comprobantes electrónicos emitidos (SRI).
5. Completa la consulta: fecha, tipo Factura, establecimiento, punto de emisión (SRI, un formulario = un paso).
6. Haz clic en Consultar → lista (SRI).
7. Abre Perseo XML → XML Desde el RIDE → resumen (extensión).

Parte 3: Comprobantes recibidos
8. Haz clic en Anterior (SRI).
9. Haz clic en Comprobantes electrónicos recibidos (SRI).
10. Elige año, mes y día; tipo Factura (SRI, un formulario).
11. Haz clic en Consultar → lista (SRI).
12. Abre Perseo XML → XML Para importar → resumen; el video termina aquí (extensión).

## Datos de la serie

- Empresa: la del usuario (datos reales, difuminados; no hay datos demo en el SRI).
- Consultas: emitidos 13/11/2026, Factura, 001-901 (12); recibidos 01/11/2026, Factura (6).

## Datos de ejemplo

- Fecha de emisión "13/11/2026", establecimiento "001", punto "901"; periodo 2026 / Noviembre / 1.

## Preguntas abiertas

- El requisito literal dura ~6,8 s (lint TUT1 pide ≤ 5 s); se mantuvo el texto pedido.
- Descargas reales en la carpeta Descargas del usuario (12 + 6 XML por toma).
