"""S9 (odd/tasks/perseo-xml-v5.md T7): correcting one narration line re-synthesizes only that line. Unchanged
lines reuse their cached clip; the changed lines are ONE batch request (D5) cut like the whole-video batch.
The Gemini call is mocked (synthesize + make_client) and whisper is skipped (batch_words), so no API is billed.

Run: .venv/Scripts/python.exe -m unittest tests.test_tts_cache -v
"""
import contextlib
import copy
import io
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import common  # noqa: E402
import tts  # noqa: E402

TUTORIAL = {
    "title": "T",
    "steps": [
        {"id": "nuevo", "narration": "Haz clic en Nuevo contacto.", "actions": [{"click": "#a"}]},
        {"id": "nombre", "narration": "Escribe el nombre completo.", "actions": [{"click": "#b"}]},
        {"id": "guardar", "narration": "Guarda y revisa la lista.", "actions": [{"result": "#t"}]},
    ],
    "videos": [
        {"id": "tutorial", "type": "TUT", "steps": "all",
         "opening": {"narration": "Aprende a crear un contacto.", "text": "x"},
         "closing": {"narration": "Mira el tutorial completo.", "text": "x"}},
    ],
}
NAMES = ["opening", "nuevo", "nombre", "guardar", "closing"]


def batch_audio(path: Path, text: str, tone=1.0, pause=0.6) -> bytes:
    """What the API returns for a batch: a 1 s tone per line (BATCH_SEP between lines) with a pause around each."""
    lines = text.split(tts.BATCH_SEP)
    args, order = [], "[0]"
    for i, _ in enumerate(lines):
        args += ["-f", "lavfi", "-i", f"sine=f={220 + 40 * i}:r=24000:d={tone}",
                 "-f", "lavfi", "-i", f"anullsrc=r=24000:cl=mono:d={pause}"]
        order += f"[{2 * i + 1}][{2 * i + 2}]"
    common.ffmpeg("-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono:d=0.3", *args,
                  "-filter_complex", f"{order}concat=n={2 * len(lines) + 1}:v=0:a=1",
                  "-ac", "1", "-c:a", "pcm_s16le", str(path))
    return path.read_bytes()


class LineCacheTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.addCleanup(setattr, common, "PROJECTS", common.PROJECTS)
        common.PROJECTS = self.dir
        self.pdir = self.dir / "crm"
        self.pdir.mkdir()
        self.vdir = self.pdir / "audio" / "voice" / "tutorial"
        self.calls = []

        def fake(client, model, text, voice, style):
            self.calls.append(text)
            return batch_audio(self.dir / f"api{len(self.calls)}.wav", text)

        for name, value in (("synthesize", fake), ("make_client", lambda: object()), ("batch_words", lambda raw: [])):
            self.addCleanup(setattr, tts, name, getattr(tts, name))
            setattr(tts, name, value)
        self.tut = copy.deepcopy(TUTORIAL)

    def run_tts(self) -> str:
        (self.pdir / "tutorial.yaml").write_text(yaml.safe_dump(self.tut, allow_unicode=True), encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.result = tts.tts("crm")
        return out.getvalue()

    def clip_bytes(self) -> dict:
        return {name: (self.vdir / f"{name}.wav").read_bytes() for name in NAMES}

    def step(self, sid: str) -> dict:
        return next(s for s in self.tut["steps"] if s["id"] == sid)

    def test_first_run_is_one_request_with_every_line(self):
        self.run_tts()
        texts = [self.tut["videos"][0]["opening"]["narration"]] + [s["narration"] for s in self.tut["steps"]] + \
                [self.tut["videos"][0]["closing"]["narration"]]
        self.assertEqual(self.calls, [tts.BATCH_SEP.join(texts)])
        self.assertEqual(list(self.result["tutorial"]), NAMES)

    def test_unchanged_rerun_synthesizes_nothing(self):
        self.run_tts()
        before = self.clip_bytes()
        log = self.run_tts()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.clip_bytes(), before)
        self.assertIn("5 frases reutilizadas, 0 a sintetizar", log)

    def test_one_changed_line_is_one_request_with_only_that_line(self):
        self.run_tts()
        before = self.clip_bytes()
        self.step("nombre")["narration"] = "Escribe el nombre y el correo."
        log = self.run_tts()
        self.assertEqual(self.calls[1:], ["Escribe el nombre y el correo."])
        self.assertIn("4 frases reutilizadas, 1 a sintetizar", log)
        after = self.clip_bytes()
        for name in NAMES:
            with self.subTest(clip=name):
                if name == "nombre":
                    self.assertNotEqual(after[name], before[name])
                else:
                    self.assertEqual(after[name], before[name])   # (e) unchanged clips byte-identical

    def test_two_changed_lines_are_one_request_with_both(self):
        self.run_tts()
        before = self.clip_bytes()
        self.step("nuevo")["narration"] = "Pulsa en Nuevo contacto."
        self.tut["videos"][0]["closing"]["narration"] = "Mira el video completo."
        log = self.run_tts()
        self.assertEqual(self.calls[1:], [tts.BATCH_SEP.join(["Pulsa en Nuevo contacto.", "Mira el video completo."])])
        self.assertIn("3 frases reutilizadas, 2 a sintetizar", log)
        after = self.clip_bytes()
        for name in ("opening", "nombre", "guardar"):
            with self.subTest(clip=name):
                self.assertEqual(after[name], before[name])
        for name in ("nuevo", "closing"):
            with self.subTest(clip=name):
                self.assertNotEqual(after[name], before[name])

    def test_pronunciation_change_resynthesizes_only_the_lines_it_changes(self):
        self.run_tts()
        self.tut["pronunciation"] = {"Nuevo": "nue vo"}
        self.run_tts()
        self.assertEqual(self.calls[1:], ["Haz clic en nue vo contacto."])


if __name__ == "__main__":
    unittest.main()
