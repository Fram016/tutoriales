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
        # D5: one batch per video, so "Mira el tutorial completo." of both videos is two clips (5 + 3).
        self.assertEqual(len(list((self.voice / "_cache").glob("*.wav"))), 8)
        before = {p.name: p.stat().st_mtime_ns for p in (self.voice / "_cache").glob("*.wav")}
        tts.tts("crm", offline=True)
        after = {p.name: p.stat().st_mtime_ns for p in (self.voice / "_cache").glob("*.wav")}
        self.assertEqual(before, after)

    def test_per_video_override_is_used(self):
        redes = self.durations("redes")["guardar"]
        self.assertAlmostEqual(redes, tts.estimate_seconds("Guárdalo en un clic."), places=1)


def padded_tone(path: Path, before=0.5, tone=1.0, after=0.7) -> bytes:
    """A clip like the API returns: silence, speech (a tone), silence."""
    common.ffmpeg("-f", "lavfi", "-i", f"anullsrc=r=24000:cl=mono:d={before}",
                  "-f", "lavfi", "-i", f"sine=f=440:r=24000:d={tone}",
                  "-f", "lavfi", "-i", f"anullsrc=r=24000:cl=mono:d={after}",
                  "-filter_complex", "[0][1][2]concat=n=3:v=0:a=1", "-c:a", "pcm_s16le", str(path))
    return path.read_bytes()


def batch_audio(path: Path, text: str, tone=1.0, pause=0.6, volume_db=lambda line: 0.0) -> bytes:
    """D5: what the API returns for a batch (one line per clip, blank line between): a 1 s tone per line with a
    pause after each; a single line is a padded tone."""
    lines = text.split("\n\n")
    if len(lines) == 1:
        return padded_tone(path, tone=tone)
    args, gains, order = [], "", "[0]"
    for i, line in enumerate(lines):
        # inputs: 0 lead silence, 2i+1 the tone of line i, 2i+2 the pause after it
        args += ["-f", "lavfi", "-i", f"sine=f=220:r=24000:d={tone}", "-f", "lavfi", "-i",
                 f"anullsrc=r=24000:cl=mono:d={pause}"]
        gains += f"[{2 * i + 1}]volume={volume_db(line)}dB[t{i}];"
        order += f"[t{i}][{2 * i + 2}]"
    common.ffmpeg("-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono:d=0.3", *args,
                  "-filter_complex", f"{gains}{order}concat=n={2 * len(lines) + 1}:v=0:a=1",
                  "-ac", "1", "-c:a", "pcm_s16le", str(path))
    return path.read_bytes()


class TrimTest(unittest.TestCase):
    """Voice durations are measured after trimming the clip's leading/trailing silence (S2 plan item 4)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_trim_keeps_the_speech_and_a_short_pad(self):
        raw, out = self.dir / "raw.wav", self.dir / "out.wav"
        padded_tone(raw)
        tts.trim_silence(raw, out)
        self.assertAlmostEqual(common.media_duration(raw), 2.2, delta=0.02)
        self.assertAlmostEqual(common.media_duration(out), 1.0 + 2 * tts.TRIM_PAD, delta=0.04)

    def test_api_clips_are_trimmed_and_retrimming_never_calls_the_api(self):
        self.addCleanup(setattr, common, "PROJECTS", common.PROJECTS)
        common.PROJECTS = self.dir
        pdir = self.dir / "crm"
        pdir.mkdir()
        (pdir / "tutorial.yaml").write_text(yaml.safe_dump(TUTORIAL, allow_unicode=True), encoding="utf-8")
        calls = []

        def fake(client, model, text, voice, style):
            calls.append(text)
            return batch_audio(self.dir / f"api{len(calls)}.wav", text)

        for name, value in (("synthesize", fake), ("make_client", lambda: object())):
            self.addCleanup(setattr, tts, name, getattr(tts, name))
            setattr(tts, name, value)
        first = tts.tts("crm")
        self.assertEqual(len(calls), 2)   # D5: one request per video, cut into its 5 + 3 clips
        for name, seconds in first["tutorial"].items():
            with self.subTest(clip=name):
                self.assertAlmostEqual(seconds, 1.0 + 2 * tts.TRIM_PAD, delta=0.04)
                wav = pdir / "audio" / "voice" / "tutorial" / f"{name}.wav"
                self.assertAlmostEqual(common.media_duration(wav), seconds, delta=0.01)
        self.addCleanup(setattr, tts, "TRIM_VERSION", tts.TRIM_VERSION)
        tts.TRIM_VERSION += 1
        tts.tts("crm")
        self.assertEqual(len(calls), 2)   # a new trim re-derives from the raw API audio in the cache
        self.assertTrue(list((pdir / "audio" / "voice" / "_cache").glob(f"trim-v{tts.TRIM_VERSION}/*.wav")))


if __name__ == "__main__":
    unittest.main()
