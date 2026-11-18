"""tts.py per video (odd/tasks/reglas-video.md L3): audio/voice/<video>/... and a text-hash cache
shared across videos. Uses --offline (silent clips), so it needs ffmpeg but no API key.

Run: .venv/Scripts/python.exe -m unittest discover -s tests -v
"""
import json
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
        {"id": "guardar", "narration": "Guarda el contacto y revisa la lista.", "actions": [{"result": "#t"}]},
    ],
    "videos": [
        {"id": "tutorial", "type": "TUT", "steps": "all",
         "opening": {"narration": "En este video aprendes a crear un contacto.", "text": "x"},
         "requirements": {"narration": "Necesitas una cuenta.", "text": "x"},
         "closing": {"narration": "Mira el tutorial completo.", "text": "x"}},
        {"id": "redes", "type": "RED", "steps": ["guardar"],
         "opening": {"narration": "¿Conociste a alguien en una feria?", "text": "x"},
         "closing": {"narration": "Mira el tutorial completo.", "text": "x"},
         "narration": {"guardar": "Guárdalo en un clic."}},
    ],
}


class TtsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(setattr, common, "PROJECTS", common.PROJECTS)
        common.PROJECTS = Path(self.tmp.name)
        self.pdir = common.PROJECTS / "crm"
        self.pdir.mkdir()
        (self.pdir / "tutorial.yaml").write_text(yaml.safe_dump(TUTORIAL, allow_unicode=True), encoding="utf-8")
        self.result = tts.tts("crm", offline=True)
        self.voice = self.pdir / "audio" / "voice"

    def durations(self, video):
        return json.loads((self.voice / video / "durations.json").read_text(encoding="utf-8"))

    def test_clips_per_video(self):
        self.assertEqual(list(self.durations("tutorial")), ["opening", "requirements", "nuevo", "guardar", "closing"])
        self.assertEqual(list(self.durations("redes")), ["opening", "guardar", "closing"])
        for video, names in (("tutorial", self.durations("tutorial")), ("redes", self.durations("redes"))):
            for name in names:
                self.assertTrue((self.voice / video / f"{name}.wav").exists(), f"{video}/{name}.wav")
        self.assertEqual(set(self.result), {"tutorial", "redes"})

    def test_offline_lengths_follow_the_text(self):
        d = self.durations("tutorial")
        self.assertAlmostEqual(d["opening"], tts.estimate_seconds(TUTORIAL["videos"][0]["opening"]["narration"]), places=1)
        self.assertAlmostEqual(d["closing"], self.durations("redes")["closing"], places=3)

    def test_same_text_is_synthesized_once(self):
        # 7 distinct texts across both videos; "Mira el tutorial completo." is shared.
        self.assertEqual(len(list((self.voice / "_cache").glob("*.wav"))), 7)
        before = {p.name: p.stat().st_mtime_ns for p in (self.voice / "_cache").glob("*.wav")}
        tts.tts("crm", offline=True)
        after = {p.name: p.stat().st_mtime_ns for p in (self.voice / "_cache").glob("*.wav")}
        self.assertEqual(before, after)

    def test_per_video_override_is_used(self):
        redes = self.durations("redes")["guardar"]
        self.assertAlmostEqual(redes, tts.estimate_seconds("Guárdalo en un clic."), places=1)


if __name__ == "__main__":
    unittest.main()
