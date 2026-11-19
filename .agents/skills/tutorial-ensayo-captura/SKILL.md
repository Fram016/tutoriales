---
name: tutorial-ensayo-captura
description: "Trigger: ensayo, ensayar, grabar pantalla, captura, grabar la toma, toma, selectores, capture, rehearsal, record screen, take, selectors, ego-browser, ego lite, censura, difuminar, anuncios, hide. Rehearses the flow in ego-browser to find robust selectors (including focus/result/highlight targets), then records the single take for every video with tools/capture.py."
license: Apache-2.0
metadata:
  author: tutoriales
  version: "2.2"
---

## Activation Contract

Use after tutorial.yaml passes `tools/lint.py` and before tts/edit. Two phases: REHEARSAL (interactive, ego-browser) then TAKE (`tools/capture.py`). Rules by ID: `reglas/reglas-video.md`.

## Hard Rules

- One take for all videos: capture records every step of `steps:` once; each video in `videos:` reuses it. Never record a separate take per format.
- Load the `ego-browser` skill and run `ego-browser skill` first; follow its API and TaskSpace rules (one space for the rehearsal, `finish({ keep: [] })` at the end).
- Snapshot `@refs` are not stable and the recorder does not understand them or `loc=`. Write only raw CSS (`document.querySelector`, first match, top document), `text=…` or `xpath=…`. Prefer `#id`, `[name=…]`, `[data-testid=…]`, then `text="Exact label"`.
- The camera only follows logged boxes (C1, C3, R1–R3, V1, V2): every element the narration mentions or the viewer must read needs a selector in an action. Use `result: SEL` for every confirmation (toast, saved message), `highlight: SEL` for every new element (new row, card, menu item), `focus: SEL` for something read without a click.
- `result`/`highlight` targets must exist and be visible when the action runs: put `wait: SEL` first, and check transient elements (a toast that hides after ~2.5 s) are still on screen in rehearsal.
- N13: rehearse EVERY clicked/highlighted/focused selector and confirm it is VISIBLE (non-empty box, `elementFromPoint` at its center hits it or a descendant) and its visible text is what the narration names. Pages often keep hidden duplicates (the SRI side menu repeats "Consultas", "Comprobantes electrónicos recibidos"): scope to the visible container (`xpath=//li[contains(@class,'sri-listaLinks')]/a[...]`), never the first DOM match. The recorder logs `target_ok`/`target_text`; the take FAILS when `target_ok` is false.
- N23: inspect each surface (extension popup) and list its promos (cards, carousels, "Únete gratis") in `surfaces.<name>.hide: [CSS...]`; they are hidden before any frame.
- N25: apply the brief's Datos sensibles criterion uniformly: `censor.text` (`env:` values) + `censor.selectors` for the same columns in EVERY table shown (emitidos and recibidos alike: identity, third-party RUC/name, claves de acceso, montos). Browser pages reached with `follow: tab` (chrome://settings) are censored too (folder path with the Windows user); check them in rehearsal frames.
- The recorder does not reach into iframes; use `goto` to the frame URL instead. chrome:// pages: censor pierces shadow roots or falls back to `censor.regions`.
- 2FA, CAPTCHA or SSO: call `task.handOff()` during rehearsal, explain what the user must do, resume with `takeOverTaskSpace(id)`. capture.py has no handOff: prefer a demo account without 2FA; otherwise rely on the session left in the profile and start after login.
- Credentials come from `proyectos/<slug>/acceso.local.yaml` (or `.env`) via `env:NAME`. In rehearsal, read the file inside your own script only at the step that types them; never print, log, snapshot-report or return the values.
- Try selectors learned from source code first and confirm them in rehearsal.
- Never record personal tabs or real data. The take uses its own task space with a 1920x1080 emulated viewport.
- C9, C10: the recorder logs `frame_box` (control + its visible label: `label[for=id]` or the field wrapper) and `screen_at` for every type/select/click; type into the field itself (`#id`), not a wrapper, so the label is found.
- N10, N12: for type/select/click/focus it also logs `form_box` = the closest form container (`form`, `fieldset`, `[role=dialog]`, `dialog`, `.modal`/card-like element with ≥ 2 fields), viewport-clamped. compose builds the form shot from it.
- Long commands: run `capture.py` with the harness background runner (`bash_background`) or a timeout ≥ 900 s, never a short shell timeout; check the exit code and the log tail.
- Recapture only when the take itself is wrong (selector, missing `wait:`/`result:`/`highlight:`, wrong screen, private data); voice, `omit` and composition fixes never need a new take.
- D4: Chromium refuses `chrome.settingsPrivate.setPref('download.default_directory', ...)` (only the native picker changes it, and the picker is not recorded). So the folder is shown, not changed: `press_visual` on "Change" (cursor + ripple, never clicked) and `show_download_dir` on the followed chrome://settings tab (writes the folder into the Location row, DOM only). Downloads keep going to the user's current folder; say so in the worklog. Paths are never printed; the censor keeps blurring `C:\Users\<user>` while the folder names stay visible (check a frame).
- C4, N26: the take must not show long blank loads or two pages mixed; add `wait: SEL` for the loaded content instead of `pause:` (edit cuts blank/mixed frames, but a missing wait shows the spinner).

- I2: what the recording browser cannot do or show like Chrome is simulated in the page, never done: `show_text` relabels ("Agregar a ego" → "Agregar a Chrome"), `simulate_dialog` draws Chrome's confirmation, `press_visual` presses its buttons, top-level `hide` removes ego's own notices. Never click the real "Agregar a ego". Censor the Google account (avatar link `a[href*="accounts.google.com/SignOutOptions"]`) and greetings with the user's name.
- I3: a part that does not need the rest is its own take: `.venv/Scripts/python.exe tools/capture.py <slug> --config install.yaml --out takes/install`, then `.venv/Scripts/python.exe tools/merge_takes.py proyectos/<slug> proyectos/<slug>/takes/install <other take dir>` writes `capture/` (frames prefixed per take, times offset, step ids unique; the sources are only read).

## Execution Steps

1. REHEARSAL: open `app_url`, snapshot, and for each step run its actions exactly as written (same selector strings via `page.click`/`fill`/`waitForSelector`; for every click/focus/result/highlight check the N13 visibility + text match above and print only booleans and the matched text when it is not sensitive). For every form step confirm the form container: `el.closest('form, fieldset, [role=dialog], dialog, .modal, .card')` on each typed field returns ONE visible element whose box contains every field and label of the step and fits the viewport; note its selector. Snapshot after each step and confirm the result.
2. Fix tutorial.yaml: replace guessed selectors, add `wait:` for async results, add missing `result:`/`highlight:`, use `pause:` only where nothing observable exists. Rerun `tools/lint.py <slug>`.
3. Browser extensions: `goto: chrome-extension://<id>/popup.html`; take the id from `chrome://extensions` during rehearsal.
4. Surfaces: list promo selectors for `hide` (N23); confirm the summary selector after each download (N18). Censor: grab one frame per screen (also chrome:// pages) and confirm every sensitive category is blurred (N25).
5. TAKE: `.venv/Scripts/python.exe tools/capture.py <slug>` → `proyectos/<slug>/capture/{frames/, frames.json, actions.json}`. It prints `[take] paso <id> ok` per step and the measured fps.

## Failure handling

- `La toma se cortó: <error>`: read `capture/actions.json` → `failure` (e.g. `No encontré el elemento: #btn`) and the last step logged. Fix that selector or add a `wait:` in rehearsal, then repeat the full take.
- `Solo se capturaron N cuadros`: ego-lite stalled; check ego-browser is running and repeat.
- App unreachable: confirm the URL in a rehearsal snapshot first.

## Limits

Frames are CDP screenshots at ≈10-14 fps; edit.py interpolates to 30 fps. Screenshots carry no cursor: compose draws a constant-size cursor (C5) from logged points, so every click/hover/type must go through a selector, never a raw coordinate.

## Output Contract

Report: selectors changed, click/result/highlight/focus targets confirmed visible with their text (N13), `hide` selectors (N23), censor coverage per screen (N25), form container per form step (or "none found": no form shot possible), take result (frames, fps, steps), and any step that relies on an existing login session.
