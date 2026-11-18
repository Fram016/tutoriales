---
name: tutorial-ensayo-captura
description: "Trigger: ensayo, ensayar, grabar pantalla, captura, grabar la toma, toma, selectores, capture, rehearsal, record screen, take, selectors, ego-browser, ego lite. Rehearses the flow in ego-browser to find robust selectors (including focus/result/highlight targets), then records the single take for every video with tools/capture.py."
license: Apache-2.0
metadata:
  author: tutoriales
  version: "2.1"
---

## Activation Contract

Use after tutorial.yaml passes `tools/lint.py` and before tts/edit. Two phases: REHEARSAL (interactive, ego-browser) then TAKE (`tools/capture.py`). Rules by ID: `reglas/reglas-video.md`.

## Hard Rules

- One take for all videos: capture records every step of `steps:` once; each video in `videos:` reuses it. Never record a separate take per format.
- Load the `ego-browser` skill and run `ego-browser skill` first; follow its API and TaskSpace rules (one space for the rehearsal, `finish({ keep: [] })` at the end).
- Snapshot `@refs` are not stable and the recorder does not understand them or `loc=`. Write only raw CSS (`document.querySelector`, first match, top document), `text=…` or `xpath=…`. Prefer `#id`, `[name=…]`, `[data-testid=…]`, then `text="Exact label"`.
- The camera only follows logged boxes (C1, C3, R1–R3, V1, V2): every element the narration mentions or the viewer must read needs a selector in an action. Use `result: SEL` for every confirmation (toast, saved message), `highlight: SEL` for every new element (new row, card, menu item), `focus: SEL` for something read without a click.
- `result`/`highlight` targets must exist and be visible when the action runs: put `wait: SEL` first, and check transient elements (a toast that hides after ~2.5 s) are still on screen in rehearsal.
- The recorder does not reach into iframes or shadow DOM; use `goto` to the frame/page URL instead.
- 2FA, CAPTCHA or SSO: call `task.handOff()` during rehearsal, explain what the user must do, resume with `takeOverTaskSpace(id)`. capture.py has no handOff: prefer a demo account without 2FA; otherwise rely on the session left in the profile and start after login.
- Credentials come from `proyectos/<slug>/acceso.local.yaml` (or `.env`) via `env:NAME`. In rehearsal, read the file inside your own script only at the step that types them; never print, log, snapshot-report or return the values.
- Try selectors learned from source code first and confirm them in rehearsal.
- Never record personal tabs or real data. The take uses its own task space with a 1920x1080 emulated viewport.
- C9, C10: the recorder logs `frame_box` (control + its visible label: `label[for=id]` or the field wrapper) and `screen_at` for every type/select/click; type into the field itself (`#id`), not a wrapper, so the label is found.
- N10, N12: for type/select/click/focus it also logs `form_box` = the closest form container (`form`, `fieldset`, `[role=dialog]`, `dialog`, `.modal`/card-like element with ≥ 2 fields), viewport-clamped. compose builds the form shot from it.
- Long commands: run `capture.py` with the harness background runner (`bash_background`) or a timeout ≥ 900 s, never a short shell timeout; check the exit code and the log tail.
- Recapture only when the take itself is wrong (selector, missing `wait:`/`result:`/`highlight:`, wrong screen, private data); voice, `omit` and composition fixes never need a new take.
- C4: the take must not show long blank loads; add `wait: SEL` for the loaded content instead of `pause:` (edit cuts near-blank frames, but a missing wait shows the spinner).

## Execution Steps

1. REHEARSAL: open `app_url`, snapshot, and for each step run its actions exactly as written (same selector strings via `page.click`/`fill`/`waitForSelector`; for focus/result/highlight check `querySelector` returns a visible element with a non-empty box). For every form step confirm the form container: `el.closest('form, fieldset, [role=dialog], dialog, .modal, .card')` on each typed field returns ONE visible element whose box contains every field and label of the step and fits the viewport; note its selector. Snapshot after each step and confirm the result.
2. Fix tutorial.yaml: replace guessed selectors, add `wait:` for async results, add missing `result:`/`highlight:`, use `pause:` only where nothing observable exists. Rerun `tools/lint.py <slug>`.
3. Browser extensions: `goto: chrome-extension://<id>/popup.html`; take the id from `chrome://extensions` during rehearsal.
4. TAKE: `.venv/Scripts/python.exe tools/capture.py <slug>` → `proyectos/<slug>/capture/{frames/, frames.json, actions.json}`. It prints `[take] paso <id> ok` per step and the measured fps.

## Failure handling

- `La toma se cortó: <error>`: read `capture/actions.json` → `failure` (e.g. `No encontré el elemento: #btn`) and the last step logged. Fix that selector or add a `wait:` in rehearsal, then repeat the full take.
- `Solo se capturaron N cuadros`: ego-lite stalled; check ego-browser is running and repeat.
- App unreachable: confirm the URL in a rehearsal snapshot first.

## Limits

Frames are CDP screenshots at ≈10-14 fps; edit.py interpolates to 30 fps. Screenshots carry no cursor: compose draws a constant-size cursor (C5) from logged points, so every click/hover/type must go through a selector, never a raw coordinate.

## Output Contract

Report: selectors changed, result/highlight/focus targets confirmed, form container per form step (or "none found": no form shot possible), take result (frames, fps, steps), and any step that relies on an existing login session.
