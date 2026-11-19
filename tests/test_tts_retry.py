"""A long D5 batch can be dropped by the Gemini server ("Server disconnected without sending a response"):
retry it, then split the reading into a few batches with the same voice, style and tempo."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import tts  # noqa: E402


class APIConnectionError(Exception):
    pass


class RetryTest(unittest.TestCase):
    def setUp(self):
        self.calls = 0
        self.waits = []
        self.addCleanup(setattr, tts, "synthesize", tts.synthesize)

    def fake(self, fails):
        def synth(client, model, text, voice, style):
            self.calls += 1
            if self.calls <= fails:
                raise APIConnectionError("Server disconnected without sending a response.")
            return b"audio"
        tts.synthesize = synth

    def test_connection_drop_is_retried(self):
        self.fake(fails=2)
        self.assertEqual(tts.synthesize_retry(None, "m", "t", "v", "s", sleep=self.waits.append), b"audio")
        self.assertEqual(self.waits, list(tts.BATCH_RETRIES))

    def test_drop_on_every_attempt_raises_batch_dropped(self):
        self.fake(fails=99)
        with self.assertRaises(tts.BatchDropped):
            tts.synthesize_retry(None, "m", "t", "v", "s", sleep=self.waits.append)
        self.assertEqual(self.calls, 1 + len(tts.BATCH_RETRIES))

    def test_other_errors_are_not_retried(self):
        def synth(*a):
            self.calls += 1
            raise ValueError("bad voice")
        tts.synthesize = synth
        with self.assertRaises(ValueError):
            tts.synthesize_retry(None, "m", "t", "v", "s", sleep=self.waits.append)
        self.assertEqual(self.calls, 1)


class GroupsTest(unittest.TestCase):
    def test_one_batch_by_default(self):
        voiced = [(str(i), "x") for i in range(26)]
        self.assertEqual(tts.batch_groups(voiced), [voiced])

    def test_split_keeps_order_in_few_batches(self):
        voiced = [(str(i), "x") for i in range(26)]
        groups = tts.batch_groups(voiced, split=True)
        self.assertEqual(len(groups), tts.BATCH_SPLIT)
        self.assertEqual([v for g in groups for v in g], voiced)


if __name__ == "__main__":
    unittest.main()
