# Nuevas formas de entrada para tutoriales

Extends the pipeline (odd/tasks/pipeline-tutoriales.md) with new inputs: demo credentials sent by chat,
a usage video + instructions as reference, a running project's source code as knowledge, and a specific focus.

## Specs

- S1 Credentials by chat: "yo te puedo mandar credenciales por chat" / "Cimo se usarian cuentas demo te las paso por chat las credenciales" — the agent stores them in a gitignored per-project file, references them as env:NAME, never in git, memory, logs or tutorial.yaml.
- S2 Video + instructions as reference: "un video del uso de la app junto con instrucciones de como funciona" — the video teaches how the app works; the tutorial is recorded clean in the live app, not a copy of the video.
- S3 Specific focus: "pedirte que hagas un tutorial con un enfoque especifico" — objective, audience and focus drive step selection, wording and the 9:16 summary.
- S4 Project: "podira darte un proyecto ... El stack de proyectos no importa yo te puedo pasar el proyecto y decirte ya esta levantado vos solo accedes" — the app is already running; the agent only accesses it, and reads the source read-only to understand features and find stable selectors. Never runs project code.
- S5 "Son otras formas de hacer los tutoriales" — all inputs converge in one brief (proyectos/<slug>/brief.md) before the script.

## Tasks

- [x] T1 S1 — Per-project access file `acceso.local.yaml` loaded by load_tutorial + gitignore + unittest — inline — commit "feat: load per-tutorial demo credentials and keep reference videos apart"
- [x] T2 S2 — transcribe.py `--ref NAME` → proyectos/<slug>/referencias/NAME/ (gitignored); default replica/ unchanged — inline — same commit
- [x] T3 S1-S5 — templates/brief.md + skill `tutorial-brief`; update `tutorial`, `tutorial-guion`, `tutorial-ensayo-captura`, `tutorial-replicar`, README — worker — commit "feat: add tutorial brief skill for credentials, reference videos, source code and focus"

## Log

- L1 (user): "Ahora necesito mejorar este flujo, yo te puedo mandar credenciales por chat o un video del uso de la app junto con instrucciones de como funciona y luego pedirte que hagas un tutorial con un enfoque especifico, asi mimso podira darte un proyecto y deberias montarlo en local y hacer los ejemplos. Son otras formas de hacer los tutoriales"
- L2 (user): "Cimo se usarian cuentas demo te las paso por chat las credenciales. El stack de proyectos no importa yo te puedo pasar el proyecto y decirte ya esta levantado vos solo accedes"
- L3 (decision): harness blocks writing `.env*`, but `proyectos/<slug>/acceso.local.yaml` is writable → flat `NAME: value` map, gitignored, loaded into the process env by load_tutorial (overrides .env for that tutorial). No local deployment stage (S4: already running).
- L4 (contract): acceso.local.yaml = flat map `NAME: value`, loaded by common.load_tutorial → os.environ (overrides .env); invalid file → PipelineError naming it. Tests: `.venv/Scripts/python.exe -m unittest discover -s tests -v` (stdlib unittest, no pytest).
