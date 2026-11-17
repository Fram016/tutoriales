# Tutoriales con IA

Pipeline local que convierte **una app + un flujo** (modo A) o **un video existente** (modo B) en un tutorial editado:

- `out/<slug>-16x9.mp4`: horizontal, video completo.
- `out/<slug>-9x16.mp4`: vertical, resumen para Reels/TikTok/Stories.

Incluye voz comercial en español latino (Gemini TTS), música de fondo (Lyria) que baja sola cuando habla la voz, audio a -14 LUFS, cursor sintético, zoom automático, subtítulos y la marca de cada tutorial.

## Requisitos (ya instalados en esta máquina)

| Herramienta | Cómo |
| --- | --- |
| FFmpeg | winget |
| Python 3.12 en `.venv` | uv (3.13+ no tiene wheels de faster-whisper en Windows) |
| Node + HyperFrames 0.9.64 + Chrome headless | `npm install`, `npx hyperframes browser ensure` |
| ego-lite (`ego-browser`) | navegador para grabar la app |

## Primera vez

```bat
copy env.template .env
rem Completar GEMINI_API_KEY (https://aistudio.google.com/apikey) y las credenciales demo
uv venv --python 3.12 .venv && uv pip install --python .venv/Scripts/python.exe -r requirements.txt
npm install
npx hyperframes browser ensure
```

## Verificar

```bat
.venv\Scripts\python.exe tools\doctor.py           rem herramientas locales
.venv\Scripts\python.exe tools\doctor.py --online  rem además prueba la API de Gemini
.venv\Scripts\python.exe tools\smoke.py            rem pipeline completo offline sobre _demo + QA
```

## Estructura

```text
.agents/skills/        skills para el agente (tutorial = punto de entrada)
tools/                 una etapa por script + pipeline.py, transcribe.py, qa.py, doctor.py, smoke.py
templates/             composición HyperFrames
demo-app/              app de prueba (smoke)
proyectos/<slug>/
  tutorial.yaml        guion: pasos, narración, acciones, marca (ver proyectos/_demo)
  brand/               logo.svg|logo.png del tutorial
  replica/             modo B: transcripción y cuadros del video original
  capture/ audio/ edit/ hf-full/ hf-short/   intermedios
  out/                 videos finales
```

## Etapas

Todas se corren desde la raíz: `.venv/Scripts/python.exe tools/<etapa>.py <slug>`.

| Etapa | Hace | Sale |
| --- | --- | --- |
| `capture` | ejecuta los pasos en ego-lite y graba cuadros | `capture/` |
| `tts [--offline]` | una locución por paso (con caché) | `audio/voice/` |
| `edit` | corta cada paso a la medida de la voz (acelera ≤3x, congela) | `edit/{full,short}/` |
| `music [--offline] [--force]` | pista Lyria; se reutiliza salvo `--force` | `audio/music.*` |
| `mix` | voz + música con ducking, -14 LUFS | `audio/{full,short}/mix.wav` |
| `compose` | proyectos HyperFrames + `hyperframes check` | `hf-full/`, `hf-short/` |
| `render [--quality draft\|looks\|delivery] [--variant full\|short]` | MP4 finales | `out/` |

Todo junto: `tools/pipeline.py <slug> [--from E] [--to E] [--only E] [--offline] [--quality Q]`.
QA: `tools/qa.py <slug> [--variant V]`. Modo B: `tools/transcribe.py <video> --slug <slug>`.

## Cómo pedirle un tutorial al agente

Modo A:

> Haz un tutorial de cómo crear un cliente en mi CRM. URL: https://crm.ejemplo.com. Las credenciales demo están en .env como CRM_DEMO_USER y CRM_DEMO_PASSWORD. Flujo: iniciar sesión, ir a Clientes, tocar Nuevo, completar nombre, correo y teléfono, guardar. Logo y colores en proyectos/crm-clientes/brand. Unos 2 minutos, y el resumen vertical de 1 minuto.

Modo B:

> Replica este video con mejor calidad: C:\videos\tutorial-viejo.mp4. La app está en https://app.ejemplo.com, usuario demo en .env como APP_DEMO_USER / APP_DEMO_PASSWORD.

El agente ensaya el flujo, graba, edita, revisa cada snapshot y entrega las rutas de los MP4.

## Limitaciones conocidas

- La grabación son capturas de pantalla a ~10-14 fps (ego-lite no permite screencast); el cursor es sintético.
- El agente no puede escribir `.env`: las claves y credenciales las agregas tú.
- La primera ejecución de HyperFrames descarga fuentes y componentes.
- Lyria no tiene capa gratuita (≈ USD 0.08 por pista); la voz TTS se cobra por carácter. Para iterar usa `--offline` y `--quality draft`.
- 2FA/CAPTCHA no se resuelven dentro de la toma: usa una cuenta demo sin 2FA o inicia sesión antes en el ensayo.
