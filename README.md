# Tutoriales con IA

Pipeline local que convierte **una app + un flujo** (modo A, también a partir de un video de uso o del código fuente) o **un video existente** (modo B) en un tutorial editado:

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
.venv\Scripts\python.exe -m unittest discover -s tests -v   rem tests unitarios
```

## Estructura

```text
.agents/skills/        skills para el agente (tutorial = punto de entrada)
tools/                 una etapa por script + pipeline.py, transcribe.py, qa.py, doctor.py, smoke.py
templates/             composición HyperFrames
demo-app/              app de prueba (smoke)
proyectos/<slug>/
  brief.md             entrada única: objetivo, audiencia, enfoque, fuentes, flujo (ver templates/brief.md)
  acceso.local.yaml    credenciales demo NOMBRE: valor (gitignored, lo escribe el agente)
  tutorial.yaml        guion: pasos, narración, acciones, marca (ver proyectos/_demo)
  brand/               logo.svg|logo.png del tutorial
  replica/             modo B: transcripción y cuadros del video original
  referencias/<NAME>/  videos de uso: transcripción y cuadros (solo conocimiento, gitignored)
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
QA: `tools/qa.py <slug> [--variant V]`. Modo B: `tools/transcribe.py <video> --slug <slug>`. Video de referencia: `tools/transcribe.py <video> --slug <slug> --ref <NAME>` → `referencias/<NAME>/`.

## Formas de entrada

Todas terminan en un mismo brief (`proyectos/<slug>/brief.md`, plantilla en `templates/brief.md`) antes del guion: objetivo concreto, audiencia, enfoque, fuentes, acceso (solo nombres `env:NAME`), conocimiento de la app, flujo y datos de ejemplo.

| Entrada | Qué hace el agente |
| --- | --- |
| App en vivo + credenciales demo por chat | guarda las credenciales en `acceso.local.yaml` y verifica el login |
| Video de uso + instrucciones | transcribe con `--ref`; el video enseña la app, la toma se graba limpia en la app en vivo |
| Proyecto ya levantado + código fuente | solo accede a la app; lee el código sin ejecutarlo (funciones, reglas, selectores) |
| Video a replicar | modo B (`replica/`): reproduce flujo y narración con mejor calidad |

Regla de `acceso.local.yaml`: mapa plano `NOMBRE: valor` (p. ej. `CRM_CLIENTES_USER`, `CRM_CLIENTES_PASSWORD`), gitignored, se carga al cargar el tutorial y pisa a `.env`; `tutorial.yaml` lo usa como `env:NOMBRE`. Solo cuentas demo. Los valores nunca van al brief, al guion, a commits, a la memoria ni a los logs. Lo que pegues en el chat queda en el historial: rota la contraseña al terminar.

## Cómo pedirle un tutorial al agente

App en vivo + credenciales por chat:

> Haz un tutorial de cómo facturar con descuento. La app está en https://facturas.ejemplo.com. Cuenta demo: usuario demo@ejemplo.com, contraseña <la-contraseña-demo>. Es para cajeros nuevos, unos 2 minutos.

Video de uso + instrucciones:

> Te paso un video de cómo se usa la app: C:\videos\uso-inventario.mp4. Instrucciones: el stock se ajusta desde Inventario → Ajustes, nunca desde Productos. Haz un tutorial con enfoque en ajustar stock por merma, para bodegueros.

Proyecto ya levantado + código fuente:

> El proyecto está en C:\proyectos\erp y ya está levantado en http://localhost:3000, vos solo accedes. Lee el código para entender cómo se crean las órdenes de compra y haz el tutorial para compradores.

Modo A con flujo:

> Haz un tutorial de cómo crear un cliente en mi CRM. URL: https://crm.ejemplo.com. Las credenciales demo están en .env como CRM_DEMO_USER y CRM_DEMO_PASSWORD. Flujo: iniciar sesión, ir a Clientes, tocar Nuevo, completar nombre, correo y teléfono, guardar. Logo y colores en proyectos/crm-clientes/brand. Unos 2 minutos, y el resumen vertical de 1 minuto.

Video a replicar (modo B):

> Replica este video con mejor calidad: C:\videos\tutorial-viejo.mp4. La app está en https://app.ejemplo.com, usuario demo en .env como APP_DEMO_USER / APP_DEMO_PASSWORD.

El agente ensaya el flujo, graba, edita, revisa cada snapshot y entrega las rutas de los MP4.

## Limitaciones conocidas

- La grabación son capturas de pantalla a ~10-14 fps (ego-lite no permite screencast); el cursor es sintético.
- El agente no puede escribir `.env`: las claves de API las agregas tú. Las credenciales demo de cada tutorial sí las puede guardar en `acceso.local.yaml`.
- Con un proyecto ya levantado el agente no instala, compila, ejecuta ni migra nada: solo accede a la app y lee el código.
- La primera ejecución de HyperFrames descarga fuentes y componentes.
- Lyria no tiene capa gratuita (≈ USD 0.08 por pista); la voz TTS se cobra por carácter. Para iterar usa `--offline` y `--quality draft`.
- 2FA/CAPTCHA no se resuelven dentro de la toma: usa una cuenta demo sin 2FA o inicia sesión antes en el ensayo.
