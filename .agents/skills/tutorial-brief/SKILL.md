---
name: tutorial-brief
description: "Trigger: brief, enfoque, enfoque específico, credenciales, cuenta demo, te paso las credenciales, video de referencia, video de uso, instrucciones de cómo funciona, proyecto, código fuente, ya está levantado, cómo funciona la app, audiencia, focus, credentials, reference video, usage video, source code, project. Collects and merges every tutorial input (live app, demo credentials, usage video, instructions, project source, focus) into proyectos/<slug>/brief.md before any script."
license: Apache-2.0
metadata:
  author: tutoriales
  version: "1.0"
---

## Activation Contract

Use at the start of every tutorial, whatever the input: live app URL, demo credentials sent by chat, a usage video with instructions, a running project's source code, a specific focus, or a video to replicate. Output: `proyectos/<slug>/brief.md` from `templates/brief.md`. No `tutorial.yaml` before the brief exists.

## Hard Rules

- Credentials (demo accounts only):
  - Write them to `proyectos/<slug>/acceso.local.yaml` (gitignored), a flat `NAME: value` map. Names: slug uppercased with `-` → `_`, plus `_USER` / `_PASSWORD` (e.g. `CRM_CLIENTES_USER`). `load_tutorial` loads it into the env and it overrides `.env`; tutorial.yaml uses `env:NAME`.
  - Confirm to the user by name only ("Guardé CRM_CLIENTES_USER y CRM_CLIENTES_PASSWORD"); never echo values back.
  - Never put values in brief.md, tutorial.yaml, commits, Engram/`mem_save`, subagent prompts, logs or summaries.
  - If the account looks real or production (personal email, admin of a live company, real customer data), warn and ask for a demo one before using it.
  - Remind the user once that the chat history keeps what they pasted; suggest rotating the password after the tutorial.
- Reference video (knowledge, not a copy): `.venv/Scripts/python.exe tools/transcribe.py <video> --slug <slug> --ref <name>` → `proyectos/<slug>/referencias/<name>/{transcript.txt, frames/*.jpg, frames.json}`. One `<name>` per video (letters, digits, `-`, `_`). The take is recorded clean in the live app. To reproduce a video's flow and narration instead, use `tutorial-replicar`.
- User's written instructions win over the video when they conflict; note the conflict in the brief.
- Project source (the app is already running; the user only gives access):
  - Never install, build, run, migrate or seed the project, and never run its scripts or tests.
  - Read source read-only for features, routes, validation rules, visible labels and stable selectors (`id`, `name`, `data-testid`, `aria-label`).
  - Paths outside this repo need the user's consent unless already granted.
  - Large codebase: delegate one read-only explorer with a bounded question (e.g. "routes, form fields and validation of invoice creation, with file:line") instead of reading everything.
- Focus: ask at most one consolidated question, only when Objetivo or Audiencia is missing; otherwise propose values and mark them as proposed. The brief drives the script.

## Decision Gates

| Input | Action |
| --- | --- |
| Credentials in chat | Write acceso.local.yaml, confirm names only |
| Usage video + instructions | transcribe `--ref`, read transcript + keyframes |
| Project path ("ya está levantado") | Read source read-only (or one bounded explorer) |
| "Replicar/mejorar este video" | Brief, then `tutorial-replicar` (mode B) |
| No app URL or no access | Record in Preguntas abiertas and ask |

## Execution Steps

1. Create `proyectos/<slug>/` and copy `templates/brief.md` to `brief.md`.
2. Paste the user's instructions verbatim under Fuentes.
3. Store credentials (if any) and fill Acceso with `env:NAME` names and the account role.
4. Process each reference video: read `transcript.txt` whole, view the keyframes; record screens, terminology and flow in Conocimiento de la app with source `(video <name> mm:ss)`.
5. Read the project source; record features, rules and selectors with source `(código <path>:<line>)`.
6. Fill Objetivo, Audiencia, Enfoque, Flujo propuesto (numbered, one visible outcome per step) and fictional Datos de ejemplo.
7. Verify access: rehearse the login in ego-browser with the stored credentials (`tutorial-ensayo-captura` rehearsal rules). Mark "Login verificado" and note 2FA/CAPTCHA/SSO.
8. Write remaining doubts under Preguntas abiertas; ask only those that block the script.
9. Hand off to `tutorial-guion`.

## Output Contract

Report: brief path, objective and audience (proposed or given), sources used, credential names stored (names only), login verification result, open questions.
