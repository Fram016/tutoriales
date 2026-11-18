# Tutorial Perseo XML (extensión) desde cero

Record the Perseo XML browser extension (bulk XML/PDF download from SRI en línea) from scratch in ego-lite, with censoring and the extension popup visible.
Reference videos transcribed in proyectos/perseo-xml/referencias/uso-1 (emitidos, 164 s) and uso-2 (recibidos + configurar carpeta, 57 s). Logo: proyectos/perseo-xml/brand/logo.png.

## Specs

- S1 "Ahora vamos a hacer otro tutorial, es para la herramienta llamada Perseo XML" — reference videos "C:\Users\Francisco Lopez\Videos\2026-11-18 08-10-18.mp4" then "C:\Users\Francisco Lopez\Videos\2026-11-18 08-13-48.mp4".
- S2 "si quieres hazlo desde cero porque tambien hay una opcion de configurar carpeta que la menciono hasta el final y debe ser antes de hacer las descargas del XML" — user chose: from scratch in ego-lite; the folder setting is "Dentro de la extensión"; it goes before the downloads.
- S3 "censura nombres y credenciales si haces el tutorial desde cero" — user chose to censor: "RUC y nombre del contribuyente" (SRI header + RUC field of the query). Credentials are never typed by the agent (the user logs in).
- S4 SRI link: "https://srienlinea.sri.gob.ec/comprobantes-electronicos-internet/pages/consultas/menu.jsf?&contextoMPT=https://srienlinea.sri.gob.ec/tuportal-internet&pathMPT=Facturaci%F3n%20Electr%F3nica%20%2F%20Producci%F3n&actualMPT=Consultas%20&linkMPT=%2Fcomprobantes-electronicos-internet%2Fpages%2Fconsultas%2Fmenu.jsf%3F&esFavorito=S"
- S5 "adicional se debe ver la interfaz de la extension, este es el logo a usar" — the extension popup must be visible in the video; brand logo Perseo (black, "sistema contable").

## Tasks

- [ ] T1 S2 — User installs Perseo XML (nggkmolkfkhfdjgbclinjcojpikldbhp) in ego-lite; confirm via targets — user + parent
- [ ] T2 S5 — Spike: open the action popup via CDP (service worker chrome.action.openPopup) and screenshot/interact with the popup target — parent
- [ ] T3 S3,S5 — Recorder: `censor` (selectors + text regex blur injected in-page, survives navigation) and popup surface capture composited by compose — worker
- [ ] T4 S1-S5 — Brief + guion (TUT + RED), rehearsal with user login handoff, capture, pipeline, QA — worker
- [ ] T5 — Delivery and user review

## Log

- L1 (user): "Ahora vamos a hacer otro tutorial, es para la herramienta llamada Perseo XML primero es este video ... luego este video ... si quieres hazlo desde cero porque tambien hay una opcion de configurar carpeta que la menciono hasta el final y debe ser antes de hacer las descargas del XML, censura nombres y credenciales si haces el tutorial desde cero este el link del SRI ... adicional se debe ver la interfaz de la extension, este es el logo a usar"
- L2 (user answers): enfoque "Desde cero en ego-lite (recomendado)"; carpeta "Dentro de la extensión"; censura "RUC y nombre del contribuyente".
- L3 (evidence from the reference videos): flow = SRI en línea → Facturación Electrónica → Producción → Consultas → Comprobantes electrónicos emitidos/recibidos → fecha → Consultar → Perseo icon (toolbar, top right) → popup sections "Comprobantes recibidos: XML (para importar), PDF (RIDE recibidos)" and "Comprobantes emitidos: PDF (RIDE emitidos), XML (desde el RIDE)" → button shows "En proceso…", toolbar badge counts downloads (184 docs in uso-1). The popup also shows promo cards (Club Perseo, Perseo Firmas). The extension popup is a separate browser surface (not part of the tab screenshot). Real taxpayer data is on screen (header RUC + name, emitter names, claves de acceso).
- L4 (risk): real SRI account and real downloads; user logs in via ego handOff; downloaded XMLs land on the user's disk.
