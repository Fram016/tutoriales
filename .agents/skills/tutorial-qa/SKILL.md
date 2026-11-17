---
name: tutorial-qa
description: "Trigger: revisar video, control de calidad, verificar tutorial, revisar zoom, revisar subtítulos, está bien el video, QA, quality check, review video, snapshots. Runs tools/qa.py and visually reviews every snapshot before delivery; fixes via tutorial.yaml + pipeline.py --from."
license: Apache-2.0
metadata:
  author: tutoriales
  version: "1.0"
---

## Activation Contract

Use after every render and always before delivering. Do not report a tutorial as done without a passing QA.

## Hard Rules

- Command: `.venv/Scripts/python.exe tools/qa.py <slug> [--variant full|short]`. It checks ffprobe (resolution, duration, audio) and loudness, writes one snapshot per step at its mid-point and prints the PNG paths.
- Open EVERY printed PNG with the image-reading tool. Never pass QA based on the text output alone.
- Any visible personal data, real credentials, notifications or personal tabs = fail; fix and re-record.

## Per-snapshot checklist

- Zoom frames the element being used; nothing important is cut off; not zoomed on empty space.
- Synthetic cursor sits on the clicked/typed element, not offset.
- Caption readable (contrast, size, not covering the action) and matches what this step's narration says.
- Screen shows the step's expected state (not a loading spinner or the previous page).
- 9:16: the action falls inside the 1080x1080 window; title band and caption don't overlap it.
- Brand: logo, colors and font correct in intro/outro.

## Fix → rerun from the right stage

| Problem | Edit | Rerun |
| --- | --- | --- |
| Wrong/blank screen, spinner, wrong element, private data | actions, `wait:`, selectors in tutorial.yaml | `tools/pipeline.py <slug> --from capture` |
| Narration wording, voice, pacing | `narration`, `voice:` | `--from tts` |
| Result shown too briefly | `hold_ms` | `--from capture` |
| Summary too long / wrong steps | `summary:` flags | `--from edit` |
| Music | `music:` prompt | `tools/music.py <slug> --force`, then `--from mix` |
| Title, outro, brand, logo | tutorial.yaml / `brand/` | `--from compose` |

Run as `.venv/Scripts/python.exe tools/pipeline.py <slug> --from <stage> --quality draft`, then qa.py again. Bound: after 3 failed fix rounds on the same issue, stop and report it to the user.

## Output Contract

Report qa.py technical results, each snapshot verdict (pass/fail + reason), fixes applied, and final status.
