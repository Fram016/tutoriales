---
name: tutorial-ensayo-captura
description: "Trigger: ensayo, ensayar, grabar pantalla, captura, grabar la toma, toma, selectores, capture, rehearsal, record screen, take, selectors, ego-browser, ego lite. Rehearses the flow in ego-browser to find robust selectors, then records the take with tools/capture.py."
license: Apache-2.0
metadata:
  author: tutoriales
  version: "1.0"
---

## Activation Contract

Use after tutorial.yaml exists and before tts/edit. Two phases: REHEARSAL (interactive, ego-browser) then TAKE (`tools/capture.py`).

## Hard Rules

- Load the `ego-browser` skill and run `ego-browser skill` first; follow its API and TaskSpace rules (one space for the rehearsal, `finish({ keep: [] })` at the end).
- Snapshot `@refs` are not stable and the recorder does not understand them or `loc=`. Write only raw CSS (`document.querySelector`, first match, top document), `text=…` or `xpath=…`. Prefer `#id`, `[name=…]`, `[data-testid=…]`, then `text="Exact label"`.
- The recorder does not reach into iframes or shadow DOM; use `goto` to the frame/page URL instead.
- 2FA, CAPTCHA or SSO: call `task.handOff()` during rehearsal, explain what the user must do, resume with `takeOverTaskSpace(id)`. capture.py has no handOff: prefer a demo account without 2FA; otherwise rely on the session the rehearsal left in the profile and start the steps after login. Check that in rehearsal.
- Never record personal tabs or real data. The take uses its own task space with a 1920x1080 emulated viewport.

## Execution Steps

1. REHEARSAL: open `app_url`, snapshot, and for each step run its actions exactly as written in tutorial.yaml (same selector strings via `page.click`/`fill`/`waitForSelector`). Snapshot after each step and confirm the expected result.
2. Fix tutorial.yaml: replace guessed selectors, add `wait:` for async results, add `pause:` only where nothing observable exists, set `hold_ms` where the result must stay visible.
3. Browser extensions: open the popup/options page as a normal page with `goto: chrome-extension://<id>/popup.html`; take the id from `chrome://extensions` during rehearsal.
4. TAKE: `.venv/Scripts/python.exe tools/capture.py <slug>` → `proyectos/<slug>/capture/{frames/, frames.json, actions.json}`. It prints `[take] paso <id> ok` per step and the measured fps.

## Failure handling

- `La toma se cortó: <error>`: read `capture/actions.json` → `failure` (e.g. `No encontré el elemento: #btn`) and the last step logged. Fix that selector or add a `wait:` in rehearsal, then repeat the full take.
- `Solo se capturaron N cuadros`: ego-lite stalled; check ego-browser is running and repeat.
- App unreachable: confirm the URL in a rehearsal snapshot first.

## Limits

Frames are CDP screenshots at ≈10-14 fps; edit.py interpolates to 30 fps. Screenshots carry no cursor: render draws a synthetic cursor and click ripples from the logged points, so every click/hover/type must go through a selector, never a raw coordinate.

## Output Contract

Report: selectors changed, take result (frames, fps, steps), and any step that relies on an existing login session.
