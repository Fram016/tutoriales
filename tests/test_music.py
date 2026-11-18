"""music.py Lyria call (odd/tasks/reglas-ronda3.md L3, S1e): a "recitation" block is retried once with a
neutral instrument-only prompt; nothing else is retried. Uses a fake client: no API key, no billing.

Run: .venv/Scripts/python.exe -m unittest discover -s tests -v
"""
import base64
import contextlib
import io
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import common  # noqa: E402
import music  # noqa: E402

AUDIO = b"ID3fake-mp3"
RECITATION = "400 INVALID_ARGUMENT. {'error': {'message': 'Output blocked: recitation', 'status': 'INVALID_ARGUMENT'}}"
GENRES = re.compile(r"\b(pop|rock|jazz|hip.?hop|edm|lo.?fi|electronic|corporate|ambient|techno|house|trap|"
                    r"funk|reggaeton|cumbia|classical|cinematic|disco|style of|like)\b", re.I)


class FakeClient:
    """client.interactions.create(model=, input=): raises or answers from `replies`, in order."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts = []
        self.interactions = SimpleNamespace(create=self.create)

    def create(self, model, input):
        self.prompts.append(input)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def audio(data=AUDIO):
    return SimpleNamespace(output_audio=SimpleNamespace(data=base64.b64encode(data).decode()))


def generate(client, vtype="RED"):
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        try:
            return music.generate(client, "lyria-3.5", "Rhythmic upbeat electronic pop. Instrumental only.",
                                  vtype, 26, "redes"), log.getvalue()
        except common.PipelineError as err:
            return err, log.getvalue()


class RecitationRetryTest(unittest.TestCase):
    def test_recitation_is_retried_once_with_a_neutral_prompt(self):
        client = FakeClient(Exception(RECITATION), audio())
        data, log = generate(client)
        self.assertEqual(data, AUDIO)
        self.assertEqual(len(client.prompts), 2)
        self.assertEqual(client.prompts[1], music.neutral_prompt("RED", 26))
        self.assertIn("recitation", log)
        self.assertIn("reintento", log)

    def test_neutral_prompts_name_no_genre_or_artist(self):
        for vtype in music.DEFAULT_PROMPTS:
            prompt = music.neutral_prompt(vtype, 26)
            with self.subTest(vtype=vtype):
                self.assertIsNone(GENRES.search(prompt), prompt)
                self.assertIn("Instrumental only", prompt)
                self.assertIn("26 seconds", prompt)

    def test_a_second_recitation_stops_without_looping(self):
        client = FakeClient(Exception(RECITATION), Exception(RECITATION), audio())
        err, _ = generate(client)
        self.assertIsInstance(err, common.PipelineError)
        self.assertIn("recitation", str(err))
        self.assertEqual(len(client.prompts), 2)

    def test_other_errors_are_not_retried(self):
        client = FakeClient(Exception("429 RESOURCE_EXHAUSTED"), audio())
        with self.assertRaisesRegex(Exception, "429"):
            music.generate(client, "lyria-3.5", "x", "TUT", 26, "tutorial")
        self.assertEqual(len(client.prompts), 1)

    def test_first_prompt_is_used_when_it_works(self):
        # PRESERVE: a normal call sends the prompt once and returns its audio.
        client = FakeClient(audio())
        data, log = generate(client)
        self.assertEqual(data, AUDIO)
        self.assertEqual(client.prompts, ["Rhythmic upbeat electronic pop. Instrumental only."])
        self.assertNotIn("reintento", log)

    def test_no_audio_is_an_error(self):
        client = FakeClient(SimpleNamespace(output_audio=None))
        err, _ = generate(client)
        self.assertIsInstance(err, common.PipelineError)
        self.assertEqual(len(client.prompts), 1)


if __name__ == "__main__":
    unittest.main()
