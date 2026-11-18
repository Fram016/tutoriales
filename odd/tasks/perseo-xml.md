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

- [x] T1 S2 — Extension present in ego-lite as an unpacked test build (user: "estamos con una version de pruebas") — user + parent
- [x] T2 S5 — Spike: popup.html opened as a page, chrome.tabs available, background screenshot 180 ms at 2x — parent
- [x] T3 S3,S5 — Recorder censor + extension surface + follow tab; 326 tests; live on ext-demo only — worker — commit "feat: censor page data and composite extension popups"
- [ ] T4 S1-S5 — Brief + guion (TUT + RED), rehearsal with user login handoff, capture, pipeline, QA — worker
- [ ] T5 — Delivery and user review

## Log

- L1 (user): "Ahora vamos a hacer otro tutorial, es para la herramienta llamada Perseo XML primero es este video ... luego este video ... si quieres hazlo desde cero porque tambien hay una opcion de configurar carpeta que la menciono hasta el final y debe ser antes de hacer las descargas del XML, censura nombres y credenciales si haces el tutorial desde cero este el link del SRI ... adicional se debe ver la interfaz de la extension, este es el logo a usar"
- L2 (user answers): enfoque "Desde cero en ego-lite (recomendado)"; carpeta "Dentro de la extensión"; censura "RUC y nombre del contribuyente".
- L3 (evidence from the reference videos): flow = SRI en línea → Facturación Electrónica → Producción → Consultas → Comprobantes electrónicos emitidos/recibidos → fecha → Consultar → Perseo icon (toolbar, top right) → popup sections "Comprobantes recibidos: XML (para importar), PDF (RIDE recibidos)" and "Comprobantes emitidos: PDF (RIDE emitidos), XML (desde el RIDE)" → button shows "En proceso…", toolbar badge counts downloads (184 docs in uso-1). The popup also shows promo cards (Club Perseo, Perseo Firmas). The extension popup is a separate browser surface (not part of the tab screenshot). Real taxpayer data is on screen (header RUC + name, emitter names, claves de acceso).
- L5 (user): "La extension YA esta instalada, esa que colocas en el web store no es porque estamos con una version de pruebas" → unpacked at C:\Users\Francisco Lopez\Downloads\perseo-xml-1.0.9\perseo-xml, ID jakigokhcbfpebeiolidapdkeooiapeb, MV3, action popup popup.html, content scripts ride-xml.js + content-script.js on https://srienlinea.sri.gob.ec/*.
- L6 (code evidence): popup buttons #boton1..#boton4 send chrome.tabs.sendMessage to the tab found by chrome.tabs.query({active:true,currentWindow:true}) with actions descargarRecibidos, descargarRecibidosPDF, descargarEmitidos, descargarEmitidosXML; progress reaches the popup via runtime messages from background.js; #configure-folder ("Carpeta de descargas", bottom of popup) does chrome.tabs.create({url:'chrome://settings/downloads'}); #eliminarHistorial clears history. Changing the folder opens the native Windows folder picker (cannot be captured/automated).
- L7 (spike result): opening chrome-extension://jakigokhcbfpebeiolidapdkeooiapeb/popup.html with task.newPage() works; chrome.tabs exists in that page (so tabs.query can be patched to return the SRI tab); Page.captureScreenshot of that background tab works (180 ms) while the SRI tab is in front; 420x640 at DPR 2 renders crisp. Design: record popup.html as a second surface composited at the toolbar position (top-right) in compose.
- L4 (risk): real SRI account and real downloads; user logs in via ego handOff; downloaded XMLs land on the user's disk.
- L8 (live check on the real SRI, space 48): tabs.query patch inside the real popup returns the SRI tab (ok); censor on the SRI profile page blurs RUC and name (0 visible nodes) after fixing a re-install bug (a second installCensor with a new config was ignored; live leak 2 → 0, commit "fix: let a new censor config replace a previous install"). Values stored only in proyectos/perseo-xml/acceso.local.yaml as PERSEO_XML_RUC, PERSEO_XML_NOMBRE, PERSEO_XML_EMAIL, PERSEO_XML_TELEFONO (gitignored). Extension icon copied to proyectos/perseo-xml/brand/ext-icon48.png.
- L9 (user): "Falta la censura del correo tambien y numero de contacto" → censor now covers RUC, name, email and phone (env:PERSEO_XML_RUC/NOMBRE/EMAIL/TELEFONO); live check 0 visible nodes.
- L10 (user, redacted): "te pase las credenciales no me las vuevlas a pedir por esta sesion" and a corrected password. Decision: the user explicitly authorized automated SRI login for this session; credentials stored only in proyectos/perseo-xml/acceso.local.yaml (PERSEO_XML_SRI_USER / PERSEO_XML_SRI_PASSWORD, gitignored) and used by tools/sri_login.mjs (never printed). One attempt per expiry, no retry loops (account lock risk). Live login OK in space 48 on 2026-11-18. Recommended to the user: change the SRI password after the recording, since it was sent by chat.
