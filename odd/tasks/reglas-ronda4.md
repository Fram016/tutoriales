# Reglas ronda 4: tutorial Perseo XML (resaltados verificados, partes, contexto, banda, censura uniforme)

Apply the user's review of proyectos/perseo-xml/out/perseo-xml-tutorial.mp4 (reglas/reglas-video.md §Parte 6, rules N13-N27) to tools and skills, then a fresh agent re-makes ONLY the Perseo XML tutorial (TUT 16:9).

## Specs

- S1 "El que me interesa es el Perseo xml tutorial nos basaremos en ese" — only the TUT 16:9 Perseo XML video is produced this round (no RED).
- S2 Every observation of §Parte 6 ("Errores graves", "Estructura y guion", "Texto y subtítulos", "Encuadre y composición", "Color y marca", "Datos sensibles") is fixed; "Lo que funciona" keeps working (except the closing card, removed by S3).
- S3 "quita el ultimo espacio que dice siguiente video no es necesario" — no closing card (N27).
- S4 "Y el logo de Perseo al inicio no se distingue" — readable logo (N24).
- S5 "Define un criterio: o todo es dato de demostración, o se difumina igual en todo el video." — criterion chosen (N25): blur uniformly everywhere taxpayer identity, third-party RUC/name, claves de acceso and amounts; browser settings path censored.

## Tasks

- [x] T1 S2,S5 — recorder/capture/edit: N13 verified targets, surface `hide` (N23), censor on chrome:// pages (N25), blank/mixed frames (N26), N14 sync — worker WB4
- [x] T2 S2,S3,S4 — compose/render: band ≤1/8 (N21), no pillarbox + legible scale (N20), surfaces never cut (N22), logo light variant (N24), context indicator (N17), parts + separators (N16), sentence captions (N19), optional closing (N27) — worker WA4
- [x] T3 S2 — qa/lint: checks for N13-N27 — worker WC4
- [x] T4 S2,S5 — skills/README/brief template: guion rules N15/N16/N18/N19/N14, requirement wording, censor criterion, ads hiding — worker WD4
- [x] T5 — Integration: 443 tests + smoke PASS 3.3 min — parent
- [x] T6 S1-S5 — Delivered proyectos/perseo-xml-v2/out/perseo-xml-v2-tutorial.mp4 (1:45). One take with manual_fallback (not needed); spotlight fixes f5b1b8c, 5f8d7a5. Remaining QA marks (tool limits): popup 1.32x (R1/C1), wide SRI form (N12), menu 6 s static (C8), two 1.5 s silences (A2) — parent

## Log

- L1 (user, verbatim in reglas/reglas-video.md §Parte 6).
- L2 (parent decisions): S5 criterion = blur uniformly (identity, third parties, claves de acceso, montos) in both emitidos and recibidos; the browser downloads settings page IS shown (narration says "Cambiar") with "Cambiar" highlighted (never clicked) and the folder path blurred; RED not produced this round.
- L3 (contract additions on top of reglas-ronda3.md L3):
  - tutorial.yaml: `surfaces.<name>.hide: [CSS...]` (elements hidden with display:none inside the surface page before any frame; N23). `censor.selectors` and `censor.text` also apply to pages reached with `follow: tab` (chrome://settings: open shadow roots must be pierced — walk shadowRoot recursively; if script injection is impossible on chrome://, fall back to `censor.regions` computed from DOM.getDocument(pierce:true)+DOM.getBoxModel and applied as blurred rects by compose). Steps may declare `part: N` (with `parts: [{n, title}]` at top level) and `context: sri|extension` (default: extension while a surface is open, else page). `closing` optional for TUT.
  - recorder events: `target_ok` (bool: visible, non-empty box, elementFromPoint hits the element or a descendant), `target_text` (visible text of the target, trimmed, ≤60 chars; omitted when it matches a censor pattern). The take FAILS when target_ok is false (N13). Text selectors must prefer visible, in-viewport, interactive matches (the SRI side menu has hidden duplicates).
  - timeline/layout: `parts` with start times, separator cards; `context` per step; caption items carry `sentence` index; band height ≤ 135 px at 1080.
- L4 (evidence from the delivered video, perseo-xml run): text= matched hidden SRI menu links → highlights on empty boxes and on "Certificados"; Perseo popup cut at the right edge at ≈1:25; logo black on black card; band 180 px; establishing shots at 0.833× with pillarbox; Settings page dropped because the path showed the Windows user name.
