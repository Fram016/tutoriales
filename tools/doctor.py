"""Environment check: every tool the pipeline needs, with a fix hint for each failure.

Usage: python tools/doctor.py [--online]

Prints ✓ (ok), ! (warning) or ✗ (failure) per check. Exits 1 when a required check fails.
GEMINI_API_KEY missing is only a warning (offline smoke tests still work) unless --online,
which makes one tiny real Gemini TTS call ("Hola") and writes nothing to the repo.
Secret values are never printed.
"""
from __future__ import annotations

import argparse
import importlib
import json
import re
import subprocess
import sys

from common import ROOT, PipelineError, env, main_guard, which
from compose import HYPERFRAMES, hf_env

OK, WARN, FAIL = "✓", "!", "✗"
MODULES = ["google.genai", "faster_whisper", "yaml", "dotenv", "numpy", "PIL"]


class Report:
    def __init__(self) -> None:
        self.failures = 0
        self.warnings = 0

    def line(self, mark: str, name: str, detail: str = "", hint: str = "") -> None:
        if mark == FAIL:
            self.failures += 1
        elif mark == WARN:
            self.warnings += 1
        print(f" {mark} {name:<22} {detail}")
        if hint and mark != OK:
            print(f"   → {hint}")


def probe(cmd: list[str], timeout: int = 60, **kwargs) -> subprocess.CompletedProcess | None:
    """Run a version-style command; None when it cannot start or times out."""
    try:
        return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout, **kwargs)
    except (OSError, subprocess.TimeoutExpired):
        return None


def first_line(result: subprocess.CompletedProcess | None) -> str:
    if result is None:
        return ""
    return next((l.strip() for l in (result.stdout or result.stderr).splitlines() if l.strip()), "")


def check_python(r: Report) -> None:
    v = sys.version_info
    detail = f"{v.major}.{v.minor}.{v.micro} ({sys.executable})"
    if (v.major, v.minor) == (3, 12):
        r.line(OK, "Python", detail)
    else:
        r.line(FAIL, "Python", detail, "Usá el venv del proyecto: .venv\\Scripts\\python.exe tools/doctor.py "
               "(faster-whisper necesita Python 3.12)")


def check_imports(r: Report) -> None:
    for name in MODULES:
        try:
            module = importlib.import_module(name)
            r.line(OK, f"import {name}", getattr(module, "__version__", ""))
        except Exception as exc:  # any import-time error means the stage cannot run
            r.line(FAIL, f"import {name}", f"{type(exc).__name__}: {exc}",
                   "Instalá dependencias: .venv\\Scripts\\python.exe -m pip install -r requirements.txt")


def check_ffmpeg(r: Report) -> None:
    for tool in ("ffmpeg", "ffprobe"):
        try:
            path = which(tool)
        except PipelineError:
            r.line(FAIL, tool, "no encontrado",
                   "winget install -e --id Gyan.FFmpeg y abrí una terminal nueva")
            continue
        line = first_line(probe([path, "-version"]))
        r.line(OK if line else FAIL, tool, line or "no responde", "Reinstalá FFmpeg: winget install -e --id Gyan.FFmpeg")


def check_node(r: Report) -> bool:
    try:
        node = which("node")
    except PipelineError:
        r.line(FAIL, "node", "no encontrado", "Instalá Node.js 22 o superior: winget install OpenJS.NodeJS.LTS")
        return False
    line = first_line(probe([node, "--version"]))
    match = re.match(r"v(\d+)", line)
    if match and int(match.group(1)) >= 22:
        r.line(OK, "node", line)
        return True
    r.line(FAIL, "node", line or "no responde", "HyperFrames necesita Node.js >= 22: winget install OpenJS.NodeJS.LTS")
    return False


def check_hyperframes(r: Report) -> None:
    if not HYPERFRAMES.exists():
        r.line(FAIL, "HyperFrames", "no instalado", "Corré: npm install")
        return
    node = which("node")
    version = probe([node, HYPERFRAMES, "--version"], env=hf_env(), cwd=ROOT)
    if version is None or version.returncode != 0:
        r.line(FAIL, "HyperFrames", first_line(version) or "no responde", "Corré: npm install")
        return
    r.line(OK, "HyperFrames", first_line(version))
    doctor = probe([node, HYPERFRAMES, "doctor", "--json"], timeout=120, env=hf_env(), cwd=ROOT)
    chrome = None
    try:
        checks = json.loads(doctor.stdout)["checks"] if doctor else []
        chrome = next((c for c in checks if c.get("name") == "Chrome"), None)
    except (ValueError, KeyError, TypeError):
        pass
    fix = "node node_modules/hyperframes/bin/hyperframes.mjs browser ensure"
    if chrome is None:
        r.line(WARN, "Chrome headless", "no pude verificarlo (hyperframes doctor --json)", f"Si falla el render: {fix}")
    elif chrome.get("ok"):
        r.line(OK, "Chrome headless", "instalado")
    else:
        r.line(FAIL, "Chrome headless", chrome.get("detail", "no encontrado"), fix)


def check_ego(r: Report) -> None:
    try:
        ego = which("ego-browser")
    except PipelineError:
        r.line(FAIL, "ego-browser", "no está en el PATH",
               "Instalá ego-lite y abrí una terminal nueva (la captura lo necesita)")
        return
    result = probe([ego, "--version"])
    line = first_line(result)
    if result is not None and result.returncode == 0 and line:
        r.line(OK, "ego-browser", line)
    else:
        r.line(FAIL, "ego-browser", line or "no responde", "Reinstalá ego-lite")


def check_env(r: Report, online: bool) -> bool:
    if (ROOT / ".env").exists():
        r.line(OK, ".env", "existe")
    else:
        r.line(WARN, ".env", "no existe (se usan los valores de env.template)", "copy env.template .env")
    if env("GEMINI_API_KEY"):
        r.line(OK, "GEMINI_API_KEY", "definida")
        return True
    r.line(FAIL if online else WARN, "GEMINI_API_KEY", "vacía: voz y música solo en --offline",
           "Creá una clave en https://aistudio.google.com/apikey y pegala en .env")
    return False


def check_gemini_tts(r: Report) -> None:
    from tts import synthesize
    model = env("TTS_MODEL", "gemini-3.8-flash-tts")
    voice = env("TTS_VOICE", "Kore")
    style = env("TTS_STYLE", "voz comercial cálida, español latinoamericano neutro")
    try:
        from google import genai
        client = genai.Client(api_key=env("GEMINI_API_KEY"), http_options={"api_version": "v1beta"})
        audio = synthesize(client, model, "Hola", voice, style)
        r.line(OK, "Gemini TTS", f"{model} / {voice}: {len(audio)} bytes de audio")
    except Exception as exc:  # report the API message, whatever the SDK raises
        message = str(exc).replace(env("GEMINI_API_KEY") or "\0", "***")
        r.line(FAIL, "Gemini TTS", f"{model} / {voice}: {type(exc).__name__}: {message[:300]}",
               "Revisá la clave, el modelo TTS_MODEL y la facturación en AI Studio")


def doctor(online: bool = False) -> Report:
    r = Report()
    print("[doctor] verificando el entorno del pipeline")
    check_python(r)
    check_imports(r)
    check_ffmpeg(r)
    if check_node(r):
        check_hyperframes(r)
    check_ego(r)
    has_key = check_env(r, online)
    if online and has_key:
        check_gemini_tts(r)
    elif not online:
        print("   (Gemini TTS sin verificar: corré con --online cuando tengas la clave)")
    status = "FALLA" if r.failures else "OK"
    print(f"[doctor] {status}: {r.failures} fallas, {r.warnings} advertencias")
    return r


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--online", action="store_true", help="hace una llamada real y mínima a Gemini TTS")
    if doctor(ap.parse_args().online).failures:
        sys.exit(1)


if __name__ == "__main__":
    main_guard(main)
