# Brief: Perseo XML: tus comprobantes del SRI (v3)

<!-- Ronda 6 (odd/tasks/perseo-ronda6.md T2, S1–S5; D1–D5, P1 revisada). Base: proyectos/perseo-xml-v2/brief.md.
     Sin valores de credenciales ni de censura. -->

## Objetivo

Descargar los XML de los comprobantes emitidos y recibidos del SRI con la extensión Perseo XML, con una carpeta de descargas para cada tipo (D4).

## Audiencia

Contadores y usuarios de Perseo que descargan comprobantes del SRI para importarlos; saben entrar a SRI en línea, no conocen la extensión.

## Tipo de video

| id | Tipo (TUT/RED/PRO/NOV) | Formato | Duración objetivo | Apertura | Cierre |
| --- | --- | --- | --- | --- | --- |
| tutorial | TUT | 16:9 | < 60 s (`max_seconds: 58`, P1 revisada), 3 partes (N16) | "Aprendes a descargar tus comprobantes." + requisito en la tarjeta | ninguno (N27): termina en el resumen de la última descarga |

Solo TUT 16:9 (T2); no hay RED.

## Enfoque

- Mostrar (D1, en secuencia con conectores): ingresar al SRI en línea → abrir Perseo XML → Carpeta de descargas → "Change" → carpeta Emitidos → menú del SRI hasta los emitidos → consultar → "XML desde el RIDE" (D2: transforma los RIDE en XML) → resumen; carpeta Recibidos → Anterior → recibidos → periodo → consultar → "XML para importar" (D2: listos para importar en Perseo) → resumen.
- D4: el selector nativo de Windows no se graba; el video muestra el clic en "Change" y la configuración con la carpeta nueva (solo visual, decisión del padre: Chromium no deja cambiar la carpeta por settingsPrivate). Las descargas reales van a la carpeta actual del usuario.
- Omitir: login (la sesión ya está abierta, es requisito), PDF RIDE, Borrar anteriores.
- Tono: informativo, ritmo ágil (`pace: fast`, tempo ≤ 1,05, P4).

## Dispositivo

- desktop: "haz clic" (L2).

## Glosario

- comprobante — no usar: documento, archivo
- extensión — no usar: complemento, plugin
- descargar — no usar: bajar
- carpeta de descargas — no usar: directorio, ruta
- Etiquetas exactas: "Carpeta de descargas", "Comprobantes electrónicos emitidos/recibidos", "Consultar", "Anterior", "XML Desde el RIDE", "XML Para importar", "Change" (configuración en inglés).
- Pronunciación (D3): RIDE → "ri de".

## Paleta (de la app)

- primary `#ca4100`, background/surface `#09090b`, on_surface `#ffffff`; logo claro generado por compose (N24); fuente Segoe UI.

## Datos sensibles

- Criterio (N25): difuminado uniforme, igual que v2: identidad del contribuyente (`env:` en acceso.local.yaml), RUC/razón social de terceros, claves de acceso y montos por columna en ambas tablas, y la ruta de la carpeta con el usuario de Windows (`'[A-Za-z]:\\Users\\[^\\]+'`): el nombre de usuario difuminado, "\Downloads\Perseo XML\Emitidos|Recibidos" visible.

## Historia / escenario

- Ninguna; consultas cortas para descargas rápidas: emitidos 13/11/2026, 001-901 (12 facturas); recibidos 01/11/2026 (6 facturas).

## Destino del CTA

- No aplica (TUT sin cierre, N27).

## Fuentes

- App: https://srienlinea.sri.gob.ec/sri-en-linea/contribuyente/perfil (sesión real, login con tools/sri_login.mjs).
- Instrucciones del usuario (textuales, reglas/reglas-video.md §Parte 8):

> "Haz mas coherente los dialogos y por ejemplo debes mencionar explicitamente, Ingresa a la plataforma del SRI, luego ingresa a... y sigue con frases coherentes, no mostraste tambien como configurar correctamente la carpeta de descargas, no importa que consumas un poco mas de tiuempo siempre que sea claro solo no llegues al minuto, y explica que por ejemplo en emitidos transforma los RIDE a XML ademas RIDE se pronuncia RI DE no raid" · "Algo adicional mantene un solo tono de voz hubieron cambios de tono de voz, eso añade como orden"

## Acceso

- Usuario: `env:PERSEO_XML_SRI_USER`; contraseña: `env:PERSEO_XML_SRI_PASSWORD` (en acceso.local.yaml, nunca impresos).
