# Brief: Perseo XML: instala, conecta tu cuenta y descarga tus comprobantes (v5)

<!-- odd/tasks/perseo-xml-v5.md T1 (S1, S3; decisiones D-a..D-h). Fuente: el video de uso del usuario del 2026-11-25
     (referencias/uso/transcript.txt + frames/). Sin valores de credenciales ni de censura: solo nombres env:NAME. -->

## Objetivo

Instalar la extensión Perseo XML (I1), iniciar sesión con la cuenta de Contafacil, guardar un cliente con sus claves del SRI, entrar al SRI con «Llenar en el SRI» y descargar los XML de los comprobantes emitidos y recibidos, cada tipo en su propia carpeta de descargas (S1, D-d).

## Audiencia

Contadores y usuarios de Perseo que descargan comprobantes del SRI; saben entrar a SRI en línea, todavía no tienen la extensión ni conocen sus pestañas «Claves SRI» y «Descargas».

## Tipo de video

| id | Tipo (TUT/RED/PRO/NOV) | Formato | Duración objetivo | Apertura | Cierre |
| --- | --- | --- | --- | --- | --- |
| tutorial | TUT | 16:9 | sin tope (P1 revisada 2), 5 partes (N16), `pace: fast`, `tempo: 1.05` (D-f) | «Aprendes a instalar y usar Perseo XML.» + requisito en la tarjeta | ninguno (N27): termina en el resumen de la descarga de recibidos |

Solo TUT 16:9; no hay RED (D-f).

## Enfoque

- Parte 1 Instalar la extensión: la toma `takes/install` de v4 tal cual (misma ficha e id `nggkmolkfkhfdjgbclinjcojpikldbhp`; I1, I2 simulado) (video uso 00:00–00:23).
- Parte 2 Iniciar sesión y agregar cliente: «Crear cuenta» solo se menciona y se señala (no se crea ninguna cuenta); «Iniciar sesión» con la cuenta de Contafacil; «+ Agregar» un cliente «Prueba» con sus claves del SRI, que quedan en una bóveda para reusarlas (video uso 00:23–01:41).
- Parte 3 Configurar la carpeta y entrar al SRI: «Descargas» → «Carpeta de descargas» → Change → carpeta Emitidos (D4, solo visual); «Claves SRI» → «Acceder al SRI» → elegir el cliente «Prueba» → «Llenar en el SRI» → «Ingresar» en el SRI (video uso 01:41–02:48).
- Parte 4 Comprobantes emitidos: Facturación Electrónica → Producción → Consultas → emitidos, fecha 21/11/2026, Consultar; «XML Desde el RIDE» (D2: transforma los RIDE en XML); resumen (procesados, descargados, con error) y «Detalle de registros» (video uso 02:48–04:44).
- Parte 5 Comprobantes recibidos: carpeta Recibidos (D4); Anterior → recibidos, 2026 / Noviembre / 24, Consultar; «XML Para importar»; resumen (N18) (video uso 04:58–05:50).
- Omitir: comprimir los XML en un ZIP (el usuario lo retira: «No, mejor no muestras eso», video uso 04:58); crear una cuenta de Contafacil; la carpeta de Descargas en el Explorador (ver Preguntas abiertas).
- Tono: vendedor entusiasta, misma voz y estilo que v4 (D5, D6, D-f).

## Dispositivo

- desktop: «haz clic» (L2).

## Glosario

- Igual que v4: comprobante (no documento, archivo), extensión (no complemento, plugin), descargar (no bajar), carpeta de descargas (no directorio, ruta).
- Nuevo: cliente (no contribuyente): el registro de la bóveda con las claves del SRI de un RUC.
- Etiquetas exactas (D-g): «Claves SRI», «Descargas», «Iniciar sesión», «Crear cuenta», «+ Agregar», «Guardar cliente», «Acceder al SRI», «Llenar en el SRI», «Carpeta de descargas», «XML Desde el RIDE», «XML Para importar», «Detalle de registros»; SRI: «Ingresar», «Consultar», «Anterior»; Chrome: «Change».
- Pronunciación (D3): RIDE → «ri-de».
- Idioma: español neutro de Ecuador, tú (L1, L4). El video del usuario dice «Contafacil» para el sistema de la cuenta.

## Paleta (de la app)

- Igual que v4 (popup.html, variables CSS): primary `#ca4100`, background/surface `#09090b`, on_surface `#ffffff`, fuente Segoe UI (D-f).
- logo (N24): `brand/logo.png`, la variante usada en v4 sobre `#09090b`.

## Datos sensibles

- Criterio (N25, D-e): difuminado uniforme en todo el video.
- Texto (`censor.text`, valores solo en `acceso.local.yaml`): env:PERSEO_XML_RUC, env:PERSEO_XML_NOMBRE, env:PERSEO_XML_EMAIL, env:PERSEO_XML_TELEFONO, env:PERSEO_XML_EXT_USER, env:PERSEO_XML_SRI_USER (la identificación que el usuario pidió censurar, video uso 02:41), ruta con el usuario de Windows en chrome://settings/downloads.
- Selectores: panel `#acceso-usuario`, `#acceso-avatar` (nombre de la cuenta de Contafacil), `#acceso-login-identificacion`, `#acceso-identificacion`, `.acceso-opcion-detalle`, todo `input[type="password"]` (aunque muestre puntos); SRI: nombre del contribuyente del encabezado (por texto), columnas de emitidos y recibidos como v4 (clave de acceso, RUC y razón social del emisor, montos); Parte 1: cuenta de Google y saludo de la tienda (v4).
- `#registros-container`: en el video muestra solo la serie (establecimiento-punto-secuencial) y el estado, no claves de acceso (video uso 04:40); no se difumina. Si en la toma muestra claves, se agrega a `censor.selectors`.

## Historia / escenario

- Ninguna; la consulta de emitidos del 21 de noviembre y la de recibidos desde el 24 (pedidas por el usuario).

## Destino del CTA

- No aplica (TUT sin cierre, N27).

## Fuentes

- App: SRI en línea `https://srienlinea.sri.gob.ec/sri-en-linea/inicio/NAT` + extensión Perseo XML 1.2.1 (tienda), panel lateral `chrome-extension://nggkmolkfkhfdjgbclinjcojpikldbhp/popup.html` (D-b).
- Video de referencia: `C:\Users\Francisco Lopez\Videos\2026-11-25 16-57-31.mp4` → `proyectos/perseo-xml-v5/referencias/uso/` (375,2 s, 122 cuadros clave).
- Código fuente: no aplica.
- Instrucciones del usuario (textuales, S1–S4):

> "Debes hacer tutorial en base a lo siguiente que te indico en el video \"C:\Users\Francisco Lopez\Videos\2026-11-25 16-57-31.mp4\" analiza el video mira el funcionamiento de la extensión \"Perseo XML\""
>
> "luego recrea los pasos con ego lite"
>
> "censura datos delicados"
>
> "Si en caso necesitas hacer el video y al extensión no te deja volver a recrear el login busca como reinstalalrla o limpiar los datos"

## Acceso

- Cuenta de la extensión (Contafacil): `env:PERSEO_XML_EXT_USER`, `env:PERSEO_XML_EXT_PASSWORD`.
- SRI (cliente «Prueba»): `env:PERSEO_XML_SRI_USER`, `env:PERSEO_XML_SRI_PASSWORD`.
- Censura: `env:PERSEO_XML_RUC`, `env:PERSEO_XML_NOMBRE`, `env:PERSEO_XML_EMAIL`, `env:PERSEO_XML_TELEFONO`.
- Rol: cuenta del usuario para la demo (datos de prueba que pasó él mismo, video uso 02:34).
- Login verificado en ensayo: sí, por el orquestador (D-d paso 5: «Llenar en el SRI» + «Ingresar», sin captcha). Este brief no ensayó nada.

## Conocimiento de la app

- El panel tiene dos pestañas: «Claves SRI» (`#tab-claves`) y «Descargas» (`#tab-descargas`); en una pestaña del SRI se abre en Descargas (D-d) (video uso 00:23, 04:40).
- Sin sesión: «Crear cuenta» (`#acceso-seg-registro`) e «Iniciar sesión» (`#acceso-login-identificacion`, `#acceso-login-clave`, `#acceso-login-accion`; abierta: `#acceso-abierta`) con la cuenta de Contafacil (video uso 00:29–00:51; D-d).
- Cliente: «+ Agregar» → `#acceso-form-cuenta` con `#acceso-identificacion`, `#acceso-alias`, `#acceso-clave` y «Guardar cliente» (sin id). Guarda las claves del SRI «en una bóveda que te permite reusarlo» (video uso 00:57–01:41; D-d).
- «Acceder al SRI» (`#acceso-ir-sri`) abre el login del SRI en la pestaña principal; el cliente se elige con `label.acceso-opcion` (el radio está oculto) y «Llenar en el SRI» (`#acceso-llenar`) llena el login: «Datos llenados. Revisa y pulsa Ingresar en el SRI.»; luego «Ingresar» (`#kc-login`) (video uso 02:11–02:48; D-d). La extensión cierra el panel tras llenar; el grabador lo neutraliza (D-h).
- «Carpeta de descargas» (`#configure-folder`) abre chrome://settings/downloads; Change (`#changeDownloadsPath`) abre el selector nativo (D4: solo visual) (video uso 01:41–02:11).
- Emitidos: «XML Desde el RIDE» (`#boton4`) transforma los RIDE en XML («debido a las tecnologías que usamos… transformar el RIDE… a XML», video uso 03:38–03:57). Recibidos: «XML Para importar» (`#boton1`).
- Resumen de la última descarga: procesados (`#texto`), descargados (`#texto_correctos`), con error (`#texto_error`) y «Detalle de registros» (`<details>`, `#registros-container`) para revisar, filtrar o descargar a mano (video uso 03:57–04:17).
- Anuncios del panel («Conoce Perseo»: Facturito, Club Perseo, Perseo Firmas) en `#publicidad-perseo`: se ocultan (N23, D-b).

## Flujo propuesto

Parte 1: Instalar la extensión (toma `takes/install`, en Chrome)
1. Busca «Chrome Web Store» en Google.
2. Entra a la tienda.
3. Busca «Perseo XML».
4. Abre la ficha.
5. «Agregar a Chrome» (I2).
6. «Agregar extensión»; queda «Quitar de Chrome».

Parte 2: Iniciar sesión y agregar cliente (toma `takes/uso`, en Perseo XML)
7. Abre el panel en «Claves SRI»; se señala «Crear cuenta» (hover).
8. Login de la extensión: usuario y contraseña de Contafacil → «Iniciar sesión». (login)
9. «+ Agregar» un cliente (bóveda de claves del SRI).
10. Llena identificación, nombre «Prueba» y clave → «Guardar cliente».

Parte 3: Configurar la carpeta y entrar al SRI
11. «Descargas» → «Carpeta de descargas» (pestaña de configuración).
12. Change → carpeta Emitidos (D4, solo visual).
13. «Claves SRI» → «Acceder al SRI» (en el SRI se abre el login).
14. Elige el cliente «Prueba».
15. «Llenar en el SRI».
16. «Ingresar» en el SRI. (login)

Parte 4: Comprobantes emitidos (en el SRI, luego en Perseo XML)
17. Facturación Electrónica → Producción → Consultas.
18. Comprobantes electrónicos emitidos.
19. Fecha 21/11/2026.
20. Consultar.
21. «XML Desde el RIDE» (D2).
22. Resumen y «Detalle de registros» (N18).

Parte 5: Comprobantes recibidos
23. «Carpeta de descargas» → Change → Recibidos (D4).
24. Anterior.
25. Comprobantes electrónicos recibidos.
26. 2026 / Noviembre / 24.
27. Consultar (reCAPTCHA invisible: `manual_fallback`).
28. «XML Para importar» y su resumen (N18).

## Datos de la serie

- Empresa y comprobantes: los de la cuenta del SRI del usuario, difuminados (N25), como en v3/v4.
- Cliente de la bóveda: «Prueba» (pedido por el usuario, video uso 01:29).

## Datos de ejemplo

- Emitidos: fecha 21/11/2026 («Para el ejemplo vas a colocar la fecha 21», video uso 03:31).
- Recibidos: 2026 / Noviembre / 24 («voy a consultar desde 24», video uso 05:12).
- Cliente: alias «Prueba»; identificación y clave como env:NAME.

## Preguntas abiertas

- Resultado en el Explorador (F1, «Esta carpeta debes mostrarla», video uso 04:44 y 06:00): no se importa en esta tanda. Los cuadros clave están cada ~5 s. Ahí las carpetas Emitidos y Recibidos están directo en Descargas, no en `Descargas\Perseo XML\…` como fija D-d. Descargas lista casi solo archivos personales, y la primera vista de Emitidos tiene 32 filas seleccionadas para el ZIP que el usuario descartó. Un `resultado.yaml` necesita revisar el video cuadro a cuadro (trim y cajas, como v4).
- Carpeta: el usuario crea «emitidos» y «recibidos» directo en Descargas (video uso 01:47–01:53); D-d usa `Descargas\Perseo XML\Emitidos` y `…\Recibidos` (se sigue D-d).
- Escritura exacta del sistema de la cuenta: «Contafacil» (así lo dice el usuario); confirmar con la etiqueta del panel.
- Emitidos del 21/11 sin filtro de establecimiento: en el video son 152 comprobantes (descarga larga, se acelera en edit).
