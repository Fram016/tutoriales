"""Shared helpers for the tutorial pipeline: paths, env, tutorial.yaml, ffmpeg, JSON."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "proyectos"
load_dotenv(ROOT / ".env")
# Defaults for anything .env leaves out (never overrides .env).
load_dotenv(ROOT / "env.template")

# Windows consoles default to cp1252; tutorials are in Spanish.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")

WINGET_LINKS = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links"


class PipelineError(RuntimeError):
    """A user-facing pipeline failure with an actionable message."""


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def require_env(name: str) -> str:
    value = env(name)
    if not value:
        raise PipelineError(f"Falta la variable {name} en .env (ver env.template).")
    return value


def which(tool: str) -> str:
    """Resolve a CLI even when the current shell has not picked up the winget PATH yet."""
    found = shutil.which(tool)
    if not found and (WINGET_LINKS / f"{tool}.exe").exists():
        found = str(WINGET_LINKS / f"{tool}.exe")
    if not found:
        raise PipelineError(f"No se encontró '{tool}'. Corre: python tools/doctor.py")
    return found


def run(cmd: list[str], *, quiet: bool = False, **kwargs) -> subprocess.CompletedProcess:
    if not quiet:
        print("  $", " ".join(str(c) for c in cmd[:6]), "..." if len(cmd) > 6 else "")
    result = subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", **kwargs)
    if result.returncode != 0:
        tail = "\n".join((result.stderr or result.stdout).strip().splitlines()[-15:])
        raise PipelineError(f"Falló {Path(str(cmd[0])).name} (exit {result.returncode}):\n{tail}")
    return result


def ffmpeg(*args: str) -> subprocess.CompletedProcess:
    return run([which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", *args], quiet=True)


def media_duration(path: Path) -> float:
    out = run([which("ffprobe"), "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(path)], quiet=True).stdout
    return float(out.strip())


def project_dir(slug: str) -> Path:
    path = PROJECTS / slug
    if not (path / "tutorial.yaml").exists():
        raise PipelineError(f"No existe {path / 'tutorial.yaml'}")
    return path


ACCESS_FILE = "acceso.local.yaml"


def load_access(slug: str) -> None:
    """Load demo credentials from proyectos/<slug>/acceso.local.yaml (gitignored) into the env.

    A flat NAME: value map; tutorial.yaml references it as env:NAME. It overrides .env
    for this tutorial. Values are never printed.
    """
    path = PROJECTS / slug / ACCESS_FILE
    if not path.exists():
        return
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict) or not all(isinstance(k, str) for k in data):
        raise PipelineError(f"{path}: tiene que ser un mapa NOMBRE: valor")
    for name, value in data.items():
        os.environ[name] = "" if value is None else str(value)


ACTION_KINDS = {"goto", "click", "hover", "press", "scroll", "wait", "pause", "type", "select",
                "focus", "result", "highlight", "open", "close", "follow", "back",
                "manual_fallback"}
# Actions that may run inside an open surface: {in: SURFACE, sel: SELECTOR} ({in, px} for scroll).
SURFACE_ACTIONS = {"click", "hover", "scroll", "wait", "focus", "result", "highlight"}
ANCHORS = ("top-right", "top-left")
# The surface hangs under a toolbar strip: 16 px from the sides, 64 px of strip and gaps (compose).
SURFACE_EDGE, SURFACE_TOP = 16, 64
VIDEO_TYPES = ("TUT", "RED", "PRO", "NOV")
FORMATS = ("16:9", "9:16")
DEFAULT_FORMAT = {"TUT": "16:9", "RED": "9:16", "PRO": "16:9", "NOV": "16:9"}
REMOVED_KEYS = {"intro": "videos[].opening", "outro": "videos[].closing"}
VIDEO_ID = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
# N17: where a step happens (the context indicator of compose).
CONTEXTS = ("sri", "extension", "page")
# P2 (§Parte 7): videos[].pace. `fast` replaces TUT4 (short holds, waits cut, shorter cards, less zoom) and speeds
# the voice up by videos[].tempo (atempo, no pitch change), FAST_TEMPO by default.
PACES = ("normal", "fast")
FAST_TEMPO = 1.12
TEMPO_RANGE = (1.0, 1.25)
# N25: JS flags of the censor patterns (the recorder always adds g); default case-insensitive.
REGEX_FLAGS = "imsu"
PY_FLAGS = {"i": re.I, "m": re.M, "s": re.S, "u": 0}


def _fail(where: str, msg: str):
    raise PipelineError(f"tutorial.yaml: {where}: {msg}")


def _validate_card(where: str, card, text_optional: bool = False) -> None:
    if not isinstance(card, dict):
        _fail(where, "falta; necesita {narration: ..., text: ...} (E1)")
    for key in ("narration", "text"):
        value = card.get(key)
        if key == "text" and text_optional:
            if value is not None and not isinstance(value, str):
                _fail(where, "'text' tiene que ser texto")
            continue
        if not isinstance(value, str) or not value.strip():
            _fail(where, f"falta '{key}' (E1)")


def _validate_surface_action(where: str, kind: str, arg, surfaces, opened: set) -> None:
    """{in: SURFACE, sel: SELECTOR} (scroll: {in, px}) on a declared surface that is open."""
    key, shape = ("px", "{in: SUPERFICIE, px: PÍXELES}") if kind == "scroll" else ("sel", "{in: SUPERFICIE, sel: SELECTOR}")
    value = arg.get(key)
    good = isinstance(value, (int, float)) and not isinstance(value, bool) if key == "px" else \
        isinstance(value, str) and value.strip()
    if not isinstance(arg.get("in"), str) or not good:
        _fail(where, f"'{kind}' en una superficie necesita {shape}")
    name = arg["in"]
    if name not in surfaces:
        _fail(where, f"'{kind}' nombra una superficie que no existe en 'surfaces': {name}")
    if name not in opened:
        _fail(where, f"'{kind}' en '{name}' pero no está abierta (usa open: {name} antes)")


def _validate_parts(parts) -> list[int]:
    """N16: parts [{n, title}]; returns the part numbers."""
    if not isinstance(parts, list) or not parts:
        raise PipelineError("tutorial.yaml: 'parts' tiene que ser una lista de {n: NÚMERO, title: TÍTULO} (N16)")
    numbers = []
    for i, part in enumerate(parts):
        if not isinstance(part, dict):
            raise PipelineError("tutorial.yaml: 'parts' tiene que ser una lista de {n: NÚMERO, title: TÍTULO} (N16)")
        n = part.get("n")
        if not isinstance(n, int) or isinstance(n, bool) or n < 1:
            _fail(f"parts[{i}]", "'n' tiene que ser un número entero mayor que 0")
        if not isinstance(part.get("title"), str) or not part["title"].strip():
            _fail(f"parts[{i}]", "falta 'title'")
        if n in numbers:
            _fail("parts", f"la parte {n} está repetida")
        numbers.append(n)
    return numbers


def _validate_steps(steps, surfaces=(), parts=None) -> list[str]:
    if not isinstance(steps, list) or not steps:
        raise PipelineError("tutorial.yaml: 'steps' tiene que ser una lista con al menos un paso")
    ids = []
    opened: set[str] = set()   # surfaces open at this point of the take (open/close run in step order)
    followed = False           # a tab adopted with follow: tab, until back: main
    last_part = None
    for i, step in enumerate(steps):
        if not isinstance(step, dict) or not isinstance(step.get("id"), str) or not step["id"]:
            raise PipelineError("tutorial.yaml: cada paso necesita un 'id' único")
        sid = step["id"]
        if sid in ids:
            raise PipelineError("tutorial.yaml: cada paso necesita un 'id' único")
        ids.append(sid)
        if "summary" in step:
            _fail(f"paso {sid}", "'summary' ya no existe en v2; usa videos[].steps")
        if step.get("chapter") is not None and not isinstance(step["chapter"], int):
            _fail(f"paso {sid}", "'chapter' tiene que ser un número")
        # N16: with parts, every step names its part and parts never go back.
        if parts is not None or "part" in step:
            part = step.get("part")
            if isinstance(part, bool) or part not in (parts or []):
                _fail(f"paso {sid}", "'part' tiene que ser un número de 'parts' (N16)")
            if last_part is not None and part < last_part:
                _fail(f"paso {sid}", f"la parte {part} va después de la parte {last_part} (N16)")
            last_part = part
        if "context" in step and step["context"] not in CONTEXTS:
            _fail(f"paso {sid}", "'context' tiene que ser sri, extension o page (N17)")
        actions = step.get("actions", [])
        if not isinstance(actions, list):
            _fail(f"paso {sid}", "'actions' tiene que ser una lista")
        for action in actions:
            if not isinstance(action, dict) or len(action) != 1:
                _fail(f"paso {sid}", "cada acción es un mapa de una sola clave, p.ej. {click: '#btn'}")
            kind, arg = next(iter(action.items()))
            if kind not in ACTION_KINDS:
                _fail(f"paso {sid}", f"acción desconocida '{kind}' (válidas: {', '.join(sorted(ACTION_KINDS))})")
            if kind == "type" and not (isinstance(arg, dict) and arg.get("into") and "text" in arg):
                _fail(f"paso {sid}", "'type' necesita {into: SELECTOR, text: TEXTO}")
            if kind == "select" and not (isinstance(arg, dict) and arg.get("in") and "option" in arg):
                _fail(f"paso {sid}", "'select' necesita {in: SELECTOR, option: VALOR}")
            if kind == "manual_fallback" and not (isinstance(arg, dict) and isinstance(arg.get("until"), str)
                                                 and isinstance(arg.get("blocked"), str)):
                _fail(f"paso {sid}", "'manual_fallback' necesita {until: SELECTOR, blocked: TEXTO}")
            where = f"paso {sid}"
            if kind in SURFACE_ACTIONS and isinstance(arg, dict):
                _validate_surface_action(where, kind, arg, surfaces, opened)
            elif kind in ("open", "close"):
                if arg not in surfaces:
                    _fail(where, f"'{kind}' nombra una superficie que no existe en 'surfaces': {arg}")
                if kind == "open" and arg in opened:
                    _fail(where, f"'open: {arg}' pero ya está abierta")
                if kind == "close" and arg not in opened:
                    _fail(where, f"'close: {arg}' pero no está abierta")
                (opened.add if kind == "open" else opened.discard)(arg)
            elif kind == "follow":
                if arg != "tab":
                    _fail(where, "'follow' solo admite 'tab'")
                if followed:
                    _fail(where, "'follow: tab' con otra pestaña ya seguida (usa back: main antes)")
                followed = True
            elif kind == "back":
                if arg != "main":
                    _fail(where, "'back' solo admite 'main'")
                if not followed:
                    _fail(where, "'back: main' sin una pestaña seguida antes (follow: tab)")
                followed = False
    return ids


def _validate_censor(censor) -> None:
    """S3: censor {selectors: [CSS], text: [regex]}; the patterns (names, RUC) are never echoed."""
    if not isinstance(censor, dict):
        raise PipelineError("tutorial.yaml: 'censor' tiene que ser un mapa {selectors: [...], text: [...]}")
    if set(censor) - {"selectors", "text", "regex_flags"}:
        raise PipelineError("tutorial.yaml: 'censor' solo admite selectors, text y regex_flags")
    flags = censor.get("regex_flags", "i")
    if not isinstance(flags, str) or set(flags) - set(REGEX_FLAGS) or len(set(flags)) != len(flags):
        raise PipelineError("tutorial.yaml: 'censor.regex_flags' solo admite las letras i, m, s, u (sin repetir)")
    py_flags = 0
    for f in flags:
        py_flags |= PY_FLAGS[f]
    listed = lambda v: isinstance(v, list) and all(isinstance(s, str) and s.strip() for s in v)  # noqa: E731
    if not listed(censor.get("selectors", [])):
        raise PipelineError("tutorial.yaml: 'censor.selectors' tiene que ser una lista de selectores CSS")
    if not listed(censor.get("text", [])):
        raise PipelineError("tutorial.yaml: 'censor.text' tiene que ser una lista de expresiones regulares")
    for i, pattern in enumerate(censor.get("text", [])):
        if pattern.startswith("env:"):
            continue   # resolved by capture (the real name stays in acceso.local.yaml)
        try:
            re.compile(pattern, py_flags)
        except re.error:
            raise PipelineError(f"tutorial.yaml: 'censor.text[{i}]' no es una expresión regular válida") from None


def _validate_surfaces(surfaces, viewport) -> list[str]:
    """S5: extra pages recorded next to the main tab (an extension popup), composited by compose."""
    if not isinstance(surfaces, dict):
        raise PipelineError("tutorial.yaml: 'surfaces' tiene que ser un mapa {nombre: {url, size, ...}}")
    vw, vh = viewport
    max_w, max_h = vw - 2 * SURFACE_EDGE, vh - SURFACE_TOP
    for name, spec in surfaces.items():
        if name == "main":
            raise PipelineError("tutorial.yaml: surfaces: 'main' está reservado para la pestaña principal")
        if not isinstance(name, str) or not VIDEO_ID.match(name):
            raise PipelineError(f"tutorial.yaml: surfaces: el nombre '{name}' tiene que ir en minúsculas "
                                "(letras, números, - o _)")
        where = f"surfaces.{name}"
        if not isinstance(spec, dict) or not isinstance(spec.get("url"), str) or not spec["url"].strip():
            _fail(where, "falta 'url' (p.ej. chrome-extension://<id>/popup.html)")
        size = spec.get("size")
        if not (isinstance(size, list) and len(size) == 2
                and all(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in size)):
            _fail(where, "'size' tiene que ser [ancho, alto] en píxeles")
        if size[0] > max_w or size[1] > max_h:
            _fail(where, f"'size' no entra debajo de la barra (máximo {max_w}x{max_h})")
        dpr = spec.get("dpr", 1)
        if isinstance(dpr, bool) or not isinstance(dpr, (int, float)) or not 1 <= dpr <= 3:
            _fail(where, "'dpr' tiene que ser un número entre 1 y 3")
        if spec.get("anchor", "top-right") not in ANCHORS:
            _fail(where, "'anchor' tiene que ser top-right o top-left")
        if spec.get("target_tab") is not None and not isinstance(spec["target_tab"], str):
            _fail(where, "'target_tab' tiene que ser un patrón de URL (texto)")
        if spec.get("icon") is not None and not isinstance(spec["icon"], str):
            _fail(where, "'icon' tiene que ser una ruta (texto)")
        hide = spec.get("hide", [])
        if not isinstance(hide, list) or not all(isinstance(s, str) and s.strip() for s in hide):
            _fail(where, "'hide' tiene que ser una lista de selectores CSS (N23)")
    return list(surfaces)


def _validate_videos(videos, step_ids: list[str]) -> None:
    if not isinstance(videos, list) or not videos:
        raise PipelineError("tutorial.yaml: 'videos' tiene que ser una lista con al menos un video")
    seen = set()
    for i, video in enumerate(videos):
        if not isinstance(video, dict):
            _fail(f"videos[{i}]", "tiene que ser un mapa")
        vid = video.get("id")
        if not isinstance(vid, str) or not VIDEO_ID.match(vid):
            _fail(f"videos[{i}]", "necesita un 'id' en minúsculas (letras, números, - o _)")
        if vid in seen:
            _fail(f"video {vid}", "el 'id' está repetido")
        seen.add(vid)
        where = f"video {vid}"
        vtype = video.get("type")
        if vtype not in VIDEO_TYPES:
            _fail(where, f"'type' tiene que ser uno de {', '.join(VIDEO_TYPES)} (Parte 3)")
        if video.get("format", DEFAULT_FORMAT[vtype]) not in FORMATS:
            _fail(where, "'format' tiene que ser \"16:9\" o \"9:16\"")
        chosen = video.get("steps", "all")
        if chosen != "all":
            if not isinstance(chosen, list) or not chosen:
                _fail(where, "'steps' tiene que ser \"all\" o una lista de ids de pasos")
            unknown = [str(s) for s in chosen if s not in step_ids]
            if unknown:
                _fail(where, f"pasos que no existen en 'steps': {', '.join(unknown)}")
            if len(set(chosen)) != len(chosen):
                _fail(where, "un paso aparece dos veces en 'steps'")
            order = [step_ids.index(s) for s in chosen]
            if order != sorted(order):
                _fail(where, "los pasos tienen que seguir el orden de la lista principal (E2)")
        # N2: the opening card text is optional (it must not paraphrase the title).
        _validate_card(f"{where}: opening", video.get("opening"), text_optional=True)
        # N27: the closing card is optional in TUT (the video ends on the result).
        if vtype != "TUT" or video.get("closing") is not None:
            _validate_card(f"{where}: closing", video.get("closing"))
        if video.get("requirements") is not None:
            if vtype != "TUT":
                _fail(where, "'requirements' solo existe en videos TUT (TUT1)")
            _validate_card(f"{where}: requirements", video["requirements"])
        overrides = video.get("narration") or {}
        if not isinstance(overrides, dict):
            _fail(where, "'narration' tiene que ser un mapa {id_de_paso: texto}")
        allowed = step_ids if chosen == "all" else chosen
        stray = [str(k) for k in overrides if k not in allowed]
        if stray:
            _fail(where, f"'narration' nombra pasos que este video no usa: {', '.join(stray)}")
        if video.get("music") is not None and not isinstance(video["music"], dict):
            _fail(where, "'music' tiene que ser un mapa {prompt: ..., none: true|false}")
        omit = video.get("omit", [])
        if not isinstance(omit, list) or not all(isinstance(s, str) and s.strip() for s in omit):
            _fail(where, "'omit' tiene que ser una lista de selectores (los campos que este video no muestra)")
        if video.get("pace", "normal") not in PACES:
            _fail(where, "'pace' tiene que ser normal o fast (P2)")
        cap = video.get("max_seconds")
        if cap is not None and (isinstance(cap, bool) or not isinstance(cap, (int, float)) or cap <= 0):
            _fail(where, "'max_seconds' tiene que ser un número mayor que 0 (P1)")
        tempo = video.get("tempo")
        if tempo is not None and (isinstance(tempo, bool) or not isinstance(tempo, (int, float))
                                  or not TEMPO_RANGE[0] <= tempo <= TEMPO_RANGE[1]):
            _fail(where, f"'tempo' tiene que ser un número entre {TEMPO_RANGE[0]:g} y {TEMPO_RANGE[1]:g} (P2)")


BRAND_COLORS = ("primary", "accent", "background", "text", "surface", "on_surface")


def _validate_brand(brand) -> None:
    if not isinstance(brand, dict):
        raise PipelineError("tutorial.yaml: 'brand' tiene que ser un mapa {primary, accent, ...}")
    for key in BRAND_COLORS + ("dir", "font"):
        if brand.get(key) is not None and not isinstance(brand[key], str):
            raise PipelineError(f"tutorial.yaml: 'brand.{key}' tiene que ser texto")


def brand_defaults(brand: dict) -> dict:
    """N5: never an invented color. accent falls back to primary; text on the caption band to white.
    `surface` (caption band) has no default here: compose derives it from the dark brand color."""
    out = dict(brand)
    if not out.get("accent") and out.get("primary"):
        out["accent"] = out["primary"]
    out.setdefault("on_surface", "#ffffff")
    return out


def video_tempo(video: dict) -> float:
    """P2: voice tempo factor of a video (raw tutorial.yaml or videos() item): its `tempo`, else FAST_TEMPO when
    `pace: fast`, else 1.0 (the voice as synthesized)."""
    if video.get("tempo") is not None:
        return float(video["tempo"])
    return FAST_TEMPO if video.get("pace") == "fast" else 1.0


def validate_tutorial(data) -> None:
    """tutorial.yaml v2 (odd/tasks/reglas-video.md L2). Raises PipelineError in Spanish."""
    if not isinstance(data, dict):
        raise PipelineError("tutorial.yaml: tiene que ser un mapa de claves")
    for key in ("title", "steps"):
        if key not in data:
            raise PipelineError(f"tutorial.yaml: falta la clave '{key}'")
    for key, repl in REMOVED_KEYS.items():
        if key in data:
            raise PipelineError(f"tutorial.yaml: '{key}' ya no existe en v2; usa {repl}")
    if data.get("device", "desktop") not in ("desktop", "mobile"):
        raise PipelineError("tutorial.yaml: 'device' tiene que ser desktop o mobile (L2)")
    if data.get("glossary") is not None and not isinstance(data["glossary"], dict):
        raise PipelineError("tutorial.yaml: 'glossary' tiene que ser un mapa {término: [sinónimos prohibidos]}")
    if data.get("brand") is not None:
        _validate_brand(data["brand"])
    if data.get("censor") is not None:
        _validate_censor(data["censor"])
    surfaces = []
    if data.get("surfaces") is not None:
        surfaces = _validate_surfaces(data["surfaces"], data.get("viewport") or [1920, 1080])
    parts = _validate_parts(data["parts"]) if data.get("parts") is not None else None
    step_ids = _validate_steps(data["steps"], surfaces, parts)
    # Checked when present; a tutorial without it fails in videos(), where stages need it.
    if "videos" in data:
        _validate_videos(data["videos"], step_ids)


def load_tutorial(slug: str) -> dict:
    data = yaml.safe_load((project_dir(slug) / "tutorial.yaml").read_text(encoding="utf-8"))
    load_access(slug)
    validate_tutorial(data)
    if data.get("brand") is not None:
        data["brand"] = brand_defaults(data["brand"])
    data.setdefault("slug", slug)
    return data


def videos(tut: dict, only: str | None = None) -> list[dict]:
    """Normalized videos: steps resolved from "all", per-video narration, original numbering (E2)."""
    if not tut.get("videos"):
        raise PipelineError("tutorial.yaml: falta la clave 'videos' (cada video declara su tipo, Parte 3)")
    numbered = {s["id"]: (i + 1, s) for i, s in enumerate(tut["steps"])}
    out = []
    for video in tut["videos"]:
        if only and video["id"] != only:
            continue
        chosen = [s["id"] for s in tut["steps"]] if video.get("steps", "all") == "all" else video["steps"]
        overrides = video.get("narration") or {}
        steps = []
        for sid in chosen:
            number, step = numbered[sid]
            narration = overrides.get(sid, step.get("narration")) or ""
            steps.append({**step, "number": number, "chapter": step.get("chapter"),
                          "narration": narration.strip()})
        out.append({
            "id": video["id"],
            "type": video["type"],
            "format": video.get("format", DEFAULT_FORMAT[video["type"]]),
            "steps": steps,
            "opening": dict(video["opening"]),
            "requirements": dict(video["requirements"]) if video.get("requirements") else None,
            "closing": dict(video["closing"]) if video.get("closing") else None,
            "music": dict(video.get("music") or {}),
            "omit": list(video.get("omit") or []),
            "pace": video.get("pace", "normal"),          # P2
            "max_seconds": video.get("max_seconds"),      # P1
            "tempo": video_tempo(video),
        })
    if only and not out:
        known = ", ".join(v["id"] for v in tut["videos"])
        raise PipelineError(f"No existe el video '{only}' en tutorial.yaml (hay: {known})")
    return out


def resolve_env_ref(value):
    """'env:NAME' -> value of NAME in .env; anything else unchanged."""
    if isinstance(value, str) and value.startswith("env:"):
        return require_env(value[4:])
    return value


def is_secret_ref(value) -> bool:
    return isinstance(value, str) and value.startswith("env:") and any(
        k in value.upper() for k in ("PASS", "SECRET", "TOKEN", "KEY", "PIN"))


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main_guard(fn):
    """Run a CLI entry point, turning PipelineError into a clean exit code 1."""
    try:
        fn()
    except PipelineError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
