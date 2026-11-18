---
name: tutorial-brief
description: "Trigger: brief, enfoque, enfoque específico, tipo de video, glosario, credenciales, cuenta demo, te paso las credenciales, video de referencia, video de uso, instrucciones de cómo funciona, proyecto, código fuente, ya está levantado, cómo funciona la app, audiencia, focus, credentials, reference video, usage video, source code, project. Collects and merges every tutorial input (live app, demo credentials, usage video, instructions, project source, focus, video types, glossary) into proyectos/<slug>/brief.md before any script."
license: Apache-2.0
metadata:
  author: tutoriales
  version: "2.0"
---

## Activation Contract

Use at the start of every video, whatever the input: live app URL, demo credentials sent by chat, a usage video with instructions, a running project's source code, a specific focus, or a video to replicate. Output: `proyectos/<slug>/brief.md` from `templates/brief.md`. No `tutorial.yaml` before the brief exists. Rules: `reglas/reglas-video.md`.

## Hard Rules

- Credentials (demo accounts only):
  - Write them to `proyectos/<slug>/acceso.local.yaml` (gitignored), a flat `NAME: value` map. Names: slug uppercased with `-` → `_`, plus `_USER` / `_PASSWORD` (e.g. `CRM_CLIENTES_USER`). `load_tutorial` loads it into the env and it overrides `.env`; tutorial.yaml uses `env:NAME`.
  - Confirm by name only ("Guardé CRM_CLIENTES_USER y CRM_CLIENTES_PASSWORD"); never echo values.
  - Never put values in brief.md, tutorial.yaml, commits, Engram/`mem_save`, subagent prompts, logs or summaries.
  - If the account looks real or production, warn and ask for a demo one.
  - Remind the user once that the chat keeps what they pasted; suggest rotating the password.
- Reference video (knowledge, not a copy): `.venv/Scripts/python.exe tools/transcribe.py <video> --slug <slug> --ref <name>` → `proyectos/<slug>/referencias/<name>/{transcript.txt, frames/*.jpg, frames.json}`. To reproduce a video's flow and narration, use `tutorial-replicar`.
- User's written instructions win over the video; note the conflict.
- Project source: never install, build, run, migrate or seed it, nor run its scripts or tests. Read it read-only for features, routes, validation, visible labels and stable selectors (`id`, `name`, `data-testid`, `aria-label`). Paths outside this repo need consent. Large codebase: one read-only explorer with a bounded question.
- Focus: ask at most one consolidated question, only when Objetivo or Audiencia is missing; otherwise propose values and mark them as proposed.

## Fields the script depends on

- **Tipo de video**, one row per output (Parte 3): id, type, format, target duration, opening, closing. Default when the user only says "tutorial": `tutorial` TUT 16:9 + `redes` RED 9:16 from the same steps, marked as proposed.
- **Dispositivo** (L2): `desktop` → "haz clic"; `mobile` → "toca". Goes to `device:`.
- **Glosario** (L3): one term per concept, using the label the interface shows, with its forbidden synonyms (e.g. `contacto` — no: cliente, prospecto, registro). Defined here, before any narration.
- **Datos de la serie** (TUT7): the same fictitious company, people and products for every video of the series; short values (C6). Reuse the existing series data if the brief of a sibling video has it.
- **Idioma** (L1, L4): español neutro de Ecuador, trato de tú, no voseo, no regional idioms ("aquí", "registrar"). If the demo app itself shows voseo, report it as an open question (L1 covers interface data).
- **Flujo propuesto**: numbered, one action with a visible result per step (E2); mark login and optional fields so RED can omit them (RED3).

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
3. Store credentials (if any); fill Acceso with `env:NAME` names and the account role.
4. Each reference video: read `transcript.txt` whole, view the keyframes; record screens, terms and flow with source `(video <name> mm:ss)`.
5. Read the project source; record features, rules and selectors with source `(código <path>:<line>)`.
6. Fill Objetivo, Audiencia, Tipo de video, Enfoque, Dispositivo, Glosario, Flujo propuesto, Datos de la serie and Datos de ejemplo.
7. Verify access: rehearse the login in ego-browser (`tutorial-ensayo-captura` rehearsal rules). Mark "Login verificado"; note 2FA/CAPTCHA/SSO.
8. Write remaining doubts under Preguntas abiertas; ask only those that block the script.
9. Hand off to `tutorial-guion`.

## Output Contract

Report: brief path, objective and audience (proposed or given), video types per output, device, glossary terms, sources used, credential names stored (names only), login verification result, open questions.
