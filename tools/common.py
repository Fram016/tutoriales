"""Shared helpers for the tutorial pipeline: paths, env, tutorial.yaml, ffmpeg, JSON."""
from __future__ import annotations

import json
import os
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
        raise PipelineError(f"No se encontró '{tool}'. Corré: python tools/doctor.py")
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


def load_tutorial(slug: str) -> dict:
    data = yaml.safe_load((project_dir(slug) / "tutorial.yaml").read_text(encoding="utf-8"))
    for key in ("title", "steps"):
        if key not in data:
            raise PipelineError(f"tutorial.yaml: falta la clave '{key}'")
    ids = [s.get("id") for s in data["steps"]]
    if None in ids or len(set(ids)) != len(ids):
        raise PipelineError("tutorial.yaml: cada paso necesita un 'id' único")
    data.setdefault("slug", slug)
    return data


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
