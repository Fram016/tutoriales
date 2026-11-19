# Brief: Perseo XML: instala la extensión y descarga tus comprobantes (v4)

<!-- Ronda 7 (odd/tasks/perseo-instalacion.md T2-T3, S1-S4; I1-I3, P1 revisada 2). Base: proyectos/perseo-xml-v3/brief.md
     (video aprobado: "el video quedo perfecto"). Sin valores de credenciales ni de censura. -->

## Objetivo

Instalar la extensión Perseo XML desde la Chrome Web Store (I1) y, con ella, descargar los XML de los comprobantes emitidos y recibidos del SRI con una carpeta de descargas para cada tipo (el tutorial v3 sin cambios de contenido).

## Audiencia

Contadores y usuarios de Perseo que descargan comprobantes del SRI; saben entrar a SRI en línea, todavía no tienen la extensión.

## Tipo de video

| id | Tipo (TUT/RED/PRO/NOV) | Formato | Duración objetivo | Apertura | Cierre |
| --- | --- | --- | --- | --- | --- |
| tutorial | TUT | 16:9 | sin tope (S3, P1 revisada 2), 4 partes (N16) | "Aprendes a instalar y usar Perseo XML." + requisito en la tarjeta | ninguno (N27): termina en el resumen de la última descarga |

Solo TUT 16:9; no hay RED.

## Enfoque

- Parte 1 Instalar la extensión (I1, D1 «Primero…»): Google → «Chrome Web Store» → la tienda → buscar «Perseo XML» → ficha de la extensión → «Agregar a Chrome» → ventana de Chrome «¿Quieres agregar "Perseo XML"?» → «Agregar extensión» → «Quitar de Chrome» (instalada).
- I2: nada se instala de verdad. ego muestra «Agregar a ego» y no abre la ventana nativa de Chrome: el botón se rotula como en Chrome (`show_text`), la ventana se dibuja en la página con el mismo texto (`simulate_dialog`), los dos clics son visuales (`press_visual`) y la instalación se muestra con «Quitar de Chrome». El aviso de ego «Cambia a ego para instalar extensiones» se oculta (`hide`).
- Partes 2-4: el tutorial v3 tal cual (Configurar la carpeta, Comprobantes emitidos, Comprobantes recibidos), misma toma (I3: `tools/merge_takes.py`), misma voz, estilo, tempo y pronunciación (S4, D5: una sola lectura de todo el video). Solo cambian la numeración de partes y los conectores (D1).
- Omitir: el paso de fijar la extensión en la barra (está fuera de la página; no se inventa la interfaz del navegador).

## Dispositivo

- desktop: "haz clic" (L2).

## Glosario

- Igual que v3: comprobante (no documento, archivo), extensión (no complemento, plugin), descargar (no bajar), carpeta de descargas (no directorio, ruta).
- Etiquetas exactas nuevas: "Chrome Web Store", "Agregar a Chrome", "Agregar extensión", "Quitar de Chrome".
- Pronunciación (D3): RIDE → "ri de".

## Paleta (de la app)

- Igual que v3: primary `#ca4100`, background/surface `#09090b`, on_surface `#ffffff`; fuente Segoe UI. Insignia de contexto «En Chrome» (neutra) en la Parte 1.

## Datos sensibles

- Parte 1: la cuenta de Google del perfil que graba (avatar) y el saludo con el nombre de la tienda («<Nombre>, tal vez te guste») se difuminan.
- Partes 2-4: el criterio de v3 (N25), ya aplicado en su toma.

## Historia / escenario

- Ninguna; la misma consulta de v3.

## Destino del CTA

- No aplica (TUT sin cierre, N27).

## Fuentes

- Ficha pública: https://chromewebstore.google.com/detail/perseo-xml/nggkmolkfkhfdjgbclinjcojpikldbhp
- Instrucción del usuario (textual, reglas/reglas-video.md §Parte 9):

> "Ahora algo extra que se me paso por alto, simula la instalacion del plugin, el video quedo perfecto pero toca indicar como instalar tambien, esto ya hace que supere el minuto asi que no apliques restricciones de tiempo, solo manten el tono coherente el estilo de voz y habla de igual forma. Que necesito que enseñes, a buscar la tienda de extensiones y como se instala despues el tutorial que ya tenemos"
