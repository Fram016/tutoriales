"""Smoke test: the whole pipeline end to end on the demo app, without API keys.

Usage: python tools/smoke.py

Serves demo-app/ on http://127.0.0.1:8765 (in-process; reuses a server already listening
there if it serves DemoCRM) and mirrors the fast workflow on proyectos/_demo/tutorial.yaml:
  1. pipeline _demo --offline --to compose (lint first)
  2. qa.py --pre        layout + timeline + snapshots, no MP4
  3. pipeline --only render --quality draft (every video in one call)
  4. qa.py              full, with the MP4 checks
printing the time of each phase: out/_demo-<video>.mp4 and one QA report per video in
qa/<video>.json. Every phase runs even if a QA phase fails. Needs ego-lite for the capture stage.

Offline the voice is a silent placeholder, but the music pad keeps the mix measurable, so
A1 (loudness/true peak), A2 (silences, voice gaps from the timeline) and C4 still apply.
Prints PASS/FAIL and exits 0/1.
"""
from __future__ import annotations

import argparse
import functools
import sys
import threading
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from common import ROOT, PipelineError, main_guard
from pipeline import pipeline, select
from qa import qa

HOST, PORT = "127.0.0.1", 8765
SLUG = "_demo"
MARKER = "DemoCRM"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass


class ExclusiveServer(ThreadingHTTPServer):
    # On Windows SO_REUSEADDR lets two servers share a port; we want "address in use" instead.
    allow_reuse_address = False
    daemon_threads = True


def serves_demo() -> bool:
    try:
        with urllib.request.urlopen(f"http://{HOST}:{PORT}/", timeout=5) as resp:
            return MARKER in resp.read().decode("utf-8", "replace")
    except OSError:
        return False


def start_server() -> ThreadingHTTPServer | None:
    """Own server on PORT, or None when a compatible one is already listening."""
    if serves_demo():
        print(f"[smoke] reutilizo el servidor que ya escucha en {HOST}:{PORT}")
        return None
    handler = functools.partial(QuietHandler, directory=str(ROOT / "demo-app"))
    try:
        server = ExclusiveServer((HOST, PORT), handler)
    except OSError:
        raise PipelineError(f"El puerto {PORT} está ocupado por algo que no sirve demo-app/. Liberalo y repetí.")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    if not serves_demo():
        server.shutdown()
        server.server_close()
        raise PipelineError(f"El servidor de demo-app en {HOST}:{PORT} no responde con {MARKER}")
    print(f"[smoke] sirviendo demo-app/ en http://{HOST}:{PORT}/")
    return server


def smoke() -> bool:
    started = time.monotonic()
    times: list[tuple[str, float]] = []

    def phase(name, fn):
        t0 = time.monotonic()
        print(f"\n[smoke] === {name} ===")
        try:
            return fn()
        finally:
            times.append((name, time.monotonic() - t0))
            print(f"[smoke] {name}: {times[-1][1]:.1f} s")

    server = start_server()
    try:
        phase("pipeline --to compose", lambda: pipeline(SLUG, select(None, "compose", None), offline=True))
        pre = phase("qa --pre", lambda: qa(SLUG, pre=True))
        phase("pipeline --only render", lambda: pipeline(SLUG, select(None, None, "render"), quality="draft"))
        full = phase("qa", lambda: qa(SLUG))
        for out in sorted((ROOT / "proyectos" / SLUG / "out").glob(f"{SLUG}-*.mp4")):
            print(f"[smoke] video: {out.relative_to(ROOT)}")
    finally:
        if server:
            server.shutdown()
            server.server_close()
    passed = pre and full
    print()
    for name, seconds in times:
        print(f"[smoke] {name:<24} {seconds:7.1f} s")
    print(f"[smoke] {'PASS' if passed else 'FAIL'} en {time.monotonic() - started:.1f} s "
          f"(qa --pre {'PASS' if pre else 'FAIL'}, qa {'PASS' if full else 'FAIL'})")
    return passed


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        passed = smoke()
    except PipelineError:
        print("\n[smoke] FAIL", file=sys.stderr)
        raise
    if not passed:
        sys.exit(1)


if __name__ == "__main__":
    main_guard(main)
