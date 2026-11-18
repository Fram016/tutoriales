# Tutoriales con IA

Pipeline local que convierte **una app + un flujo** (modo A, también a partir de un video de uso o del código fuente) o **un video existente** (modo B) en videos editados, todos desde **una sola lista de pasos y una sola toma**. Cada entrada de `videos:` en `tutorial.yaml` sale como `out/<slug>-<id>.mp4`; por defecto:

- `out/<slug>-tutorial.mp4`: TUT, horizontal 16:9, todos los pasos.
- `out/<slug>-redes.mp4`: RED, vertical 9:16 real (reencuadre, no el horizontal recortado), 15–35 s, sin login.

Incluye voz comercial en español neutro de Ecuador con trato de tú (Gemini TTS), música por tipo de video (Lyria) que baja sola cuando habla la voz, audio a -14 LUFS con picos < -1 dBTP, cámara con zoom de detalle, cursor de tamaño constante, subtítulos y la marca de cada tutorial.

**Reglas normativas:** [`reglas/reglas-video.md`](reglas/reglas-video.md) (IDs E, C, O, R, T, L, A, V, TUT, RED, PRO, NOV; de la segunda prueba, C7–C10 y N1–N9; de la tercera, C1 revisada y N10–N12; del tutorial Perseo XML, N13–N27). Los skills, `tools/lint.py` y `tools/qa.py` las citan por ID.

**Zoom y formularios:** detalle 1,4–1,8× (C1). En un formulario la cámara no se mueve campo por campo: un solo plano ajustado al formulario completo (1,1–1,5×, nunca > 1,8×; N10), el campo activo con recuadro del color primario y un leve oscurecimiento del resto (N11) y, en 9:16, el formulario entero a lo ancho (N12).

**Ronda 4 (N13–N27):** cada resaltado se verifica visible y con el texto que nombra la narración (la toma falla si no); un paso = una acción del usuario; 2+ flujos se dividen en partes (`parts`, "Parte N · Paso M"); un indicador muestra si se trabaja en la página o en la extensión (`context`); un subtítulo = una oración; banda ≤ 135 px; sin bordes negros; la ventana de la extensión entera y sin anuncios (`surfaces.<name>.hide`); logo en variante clara; censura uniforme definida en el brief (también en páginas `chrome://`); el cierre del TUT es opcional.

## Tipos de video

| Tipo | Para qué | Formato | Duración | Apertura → cierre |
| --- | --- | --- | --- | --- |
| TUT | completar una tarea | 16:9 | libre (partes si hay 2+ flujos o > 5 min) | objetivo → resultado final (siguiente video solo si se pide) |
| RED | atraer y llevar al tutorial | 9:16 | 15–35 s | gancho → llamado a la acción |
| PRO | convencer de usar el producto | según canal | 20–60 s | problema → logo y llamado a la acción |
| NOV | anunciar un cambio | 16:9 o 9:16 | 15–30 s | qué cambió → enlace al tutorial |

Si no pides un tipo, el agente hace TUT 16:9 + RED 9:16 desde los mismos pasos.

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
reglas/reglas-video.md reglas normativas (errores, reglas por ID, tipos de video)
tools/                 una etapa por script + pipeline.py, lint.py, transcribe.py, qa.py, doctor.py, smoke.py
templates/             composición HyperFrames y plantilla del brief
demo-app/              app de prueba (smoke)
demo-apps/nexo-crm/    app demo Nexo CRM
proyectos/<slug>/
  brief.md             entrada única: objetivo, audiencia, enfoque, fuentes, flujo (ver templates/brief.md)
  acceso.local.yaml    credenciales demo NOMBRE: valor (gitignored, lo escribe el agente)
  tutorial.yaml        guion v2: pasos únicos + videos[] (tipo, formato, apertura, cierre); ver proyectos/_demo
  brand/               logo.svg|logo.png del tutorial
  replica/             modo B: transcripción y cuadros del video original
  referencias/<NAME>/  videos de uso: transcripción y cuadros (solo conocimiento, gitignored)
  capture/                       la toma (una para todos los videos)
  audio/voice/<id>/ audio/<id>/  locución, música y mezcla por video
  edit/<id>/ hf-<id>/            timeline, proyecto HyperFrames y layout.json por video
  qa/<id>.json                   resultado de los chequeos automáticos
  out/<slug>-<id>.mp4            videos finales
```

## Etapas

Todas se corren desde la raíz: `.venv/Scripts/python.exe tools/<etapa>.py <slug>`.

| Etapa | Hace | Sale |
| --- | --- | --- |
| `lint` | valida `tutorial.yaml` contra las reglas antes de grabar (esquema, E1, E2, L1–L4, T1, T3, duraciones) | errores / avisos |
| `capture` | ejecuta todos los pasos una vez en ego-lite y graba cuadros | `capture/` |
| `tts [--offline]` | apertura, requisitos, pasos y cierre de cada video (con caché) | `audio/voice/<id>/` |
| `edit` | reajusta el tiempo por video (tecleo C6, cargas C4, pausas TUT4/R2, silencios A2) | `edit/<id>/` |
| `music [--offline] [--force]` | pista Lyria por video según su tipo; se reutiliza salvo `--force` | `audio/<id>/music.*` |
| `mix` | voz + música con ducking, -14 LUFS, picos < -1 dBTP | `audio/<id>/mix.wav` |
| `compose` | cámara, cursor, subtítulos, etiquetas, reencuadre 9:16 + `hyperframes check` | `hf-<id>/`, `hf-<id>/layout.json` |
| `render [--quality draft\|looks\|delivery] [--video ID]` | MP4 finales en paralelo, un proceso por video (`--page-motion-blur off`) | `out/<slug>-<id>.mp4` |

Todo junto: `tools/pipeline.py <slug> [--from E] [--to E] [--only E] [--video ID] [--offline] [--quality Q]` (empieza por `lint`).
Lint: `tools/lint.py <slug>`. QA antes de renderizar: `tools/qa.py <slug> --pre [--video ID]` (solo `timeline.json` + `layout.json`, sin MP4, + snapshots para la revisión visual). QA del MP4: `tools/qa.py <slug> [--video ID]` (A1, píxeles C4, duración, resolución → `qa/<id>.json`). Modo B: `tools/transcribe.py <video> --slug <slug>`. Video de referencia: `tools/transcribe.py <video> --slug <slug> --ref <NAME>` → `referencias/<NAME>/`.

## Flujo rápido (objetivo: 10–12 min)

Para un TUT de ~1 min + un RED de ~20 s. Se corrige **antes** de renderizar y se renderiza **una sola vez**:

```bat
.venv\Scripts\python.exe tools\lint.py <slug>
.venv\Scripts\python.exe tools\pipeline.py <slug> --to compose          rem lint, capture, tts, edit, music, mix, compose
.venv\Scripts\python.exe tools\qa.py <slug> --pre                      rem chequeos sin MP4 + snapshots (máx. 3 rondas)
.venv\Scripts\python.exe tools\pipeline.py <slug> --only render --quality delivery   rem un render, ambos videos en paralelo
.venv\Scripts\python.exe tools\qa.py <slug>                            rem chequeos del MP4
.venv\Scripts\python.exe tools\pipeline.py <slug> --only render --quality delivery --video <id>   rem solo si falla ese video
```

| Etapa | Tiempo esperado (objetivo) |
| --- | --- |
| lint + capture (una toma) | ~2 min |
| tts + music (con caché: solo el texto o prompt que cambió) | ~1–2 min la primera vez, segundos después |
| edit + mix + compose | ~1–2 min |
| `qa.py --pre` + revisar snapshots, por ronda | ~1 min |
| render `delivery` (ambos en paralelo) | ~3–4 min |
| `qa.py` del MP4 | < 1 min |

Notas de operación:

- Los comandos largos (`capture`, `pipeline`, `render`: todo lo que pueda pasar de ~1 min) se corren en segundo plano o con un timeout ≥ 900 s, nunca con el timeout corto de la shell; al terminar se revisa el código de salida y el final del log. Un comando callado no significa que siga corriendo.
- Los prompts de música describen ánimo, instrumentos y tempo; nunca géneros comerciales (pop, reggaeton, rock…) ni artistas, porque Lyria los bloquea como "recitation". Si pasa, `music.py` reintenta una vez con un prompt neutro y lo registra.

`pipeline.py` imprime el tiempo de cada etapa. Solo se vuelve a grabar si la toma está mal (selector, `wait:`, pantalla equivocada); la voz y la música solo se regeneran si cambió su texto. La voz se mide sin silencios al inicio y al final, y `lint` estima la duración con 1,9 palabras/s + 0,5 s por clip.

## Formas de entrada

Todas terminan en un mismo brief (`proyectos/<slug>/brief.md`, plantilla en `templates/brief.md`) antes del guion: objetivo concreto, audiencia, tipo de video por salida, enfoque, dispositivo, glosario, paleta de la app (N5), historia o escenario (N4), destino del llamado a la acción (N8), fuentes, acceso (solo nombres `env:NAME`), conocimiento de la app, flujo y datos de la serie.

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

> El proyecto está en C:\proyectos\erp y ya está levantado en http://localhost:3000, tú solo accedes. Lee el código para entender cómo se crean las órdenes de compra y haz el tutorial para compradores.

Modo A con flujo:

> Haz un tutorial de cómo crear un cliente en mi CRM. URL: https://crm.ejemplo.com. Las credenciales demo están en .env como CRM_DEMO_USER y CRM_DEMO_PASSWORD. Flujo: iniciar sesión, ir a Clientes, hacer clic en Nuevo, completar nombre, correo y teléfono, guardar. Logo y colores en proyectos/crm-clientes/brand. Unos 2 minutos, y un video vertical para redes.

Video a replicar (modo B):

> Replica este video con mejor calidad: C:\videos\tutorial-viejo.mp4. La app está en https://app.ejemplo.com, usuario demo en .env como APP_DEMO_USER / APP_DEMO_PASSWORD.

Video para redes o promocional:

> Haz solo un reel de 30 s de cómo registrar un contacto en Nexo CRM, para Instagram.

> Haz un promocional de 45 s de la nueva búsqueda de contactos para LinkedIn, en 16:9.

Novedad:

> Anuncia a los usuarios que ahora se puede filtrar contactos por etapa, en vertical.

El agente decide el tipo de video, valida el guion con `lint`, ensaya el flujo, graba una sola toma, edita cada video, corre `qa.py --pre` y revisa cada snapshot antes de renderizar (máximo 3 rondas de corrección), renderiza una sola vez, corre los chequeos del MP4 y entrega las rutas de los MP4 por video.

## Limitaciones conocidas

- La grabación son capturas de pantalla a ~10-14 fps (ego-lite no permite screencast); el cursor es sintético.
- El agente no puede escribir `.env`: las claves de API las agregas tú. Las credenciales demo de cada tutorial sí las puede guardar en `acceso.local.yaml`.
- Con un proyecto ya levantado el agente no instala, compila, ejecuta ni migra nada: solo accede a la app y lee el código.
- La primera ejecución de HyperFrames descarga fuentes y componentes.
- Lyria no tiene capa gratuita (≈ USD 0.08 por pista); la voz TTS se cobra por carácter. Para iterar usa `--offline` y `qa.py --pre` (sin renderizar); `tts` y `music` reutilizan lo que no cambió.
- 2FA/CAPTCHA no se resuelven dentro de la toma: usa una cuenta demo sin 2FA o inicia sesión antes en el ensayo.
