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
                "focus", "result", "highlight"}
VIDEO_TYPES = ("TUT", "RED", "PRO", "NOV")
FORMATS = ("16:9", "9:16")
DEFAULT_FORMAT = {"TUT": "16:9", "RED": "9:16", "PRO": "16:9", "NOV": "16:9"}
REMOVED_KEYS = {"intro": "videos[].opening", "outro": "videos[].closing"}
VIDEO_ID = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


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


def _validate_steps(steps) -> list[str]:
    if not isinstance(steps, list) or not steps:
        raise PipelineError("tutorial.yaml: 'steps' tiene que ser una lista con al menos un paso")
    ids = []
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
    return ids


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
    step_ids = _validate_steps(data["steps"])
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
            "closing": dict(video["closing"]),
            "music": dict(video.get("music") or {}),
            "omit": list(video.get("omit") or []),
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
