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


class SeparatorTest(unittest.TestCase):
    """An energetic read barely pauses between lines: the batch asks for an unspoken pause between them."""

    def test_batch_lines_are_joined_with_a_long_pause_tag(self):
        self.assertIn("<long pause>", tts.BATCH_SEP)
        self.assertGreaterEqual(tts.BATCH_VERSION, 2)   # old batches without the pause are never reused


class AlignCutsTest(unittest.TestCase):
    """perseo-xml-v4 energetic read: pause-based cuts shifted every clip by one sentence ("carpeta-recibidos" held
    "Transforma los ri-de en XML"). Cuts now follow the recognized words of each line."""

    TEXTS = ["Haz clic en XML desde el ri-de. Transforma los ri-de en XML.", "Ahora cambia la carpeta a Recibidos.",
             "Elige año, mes y día."]

    def words(self, lines, gap_inside=0.35, gap_between=0.6):
        out, t = [], 0.0
        for k, line in enumerate(lines):
            for w in line.split():
                out.append((w, t, t + 0.3))
                t += 0.3 + (gap_inside if w.endswith(",") or w.endswith(".") else 0.05)
            t += gap_between
        return out

    def test_cuts_follow_the_last_word_of_each_line(self):
        heard = ["Haz clic en XML desde el ride. Transforma los rides en XML.", "Ahora cambia la carpeta a recibidos.",
                 "Elige año, mes y día."]
        words = self.words(heard)
        # pauses inside lines (after the first sentence and after "año,") are as long as the ones between lines
        cuts = tts.align_cuts(self.TEXTS, words, [])
        self.assertEqual(len(cuts), 2)
        end_first = [w for w in words if w[0] == "XML."][-1][2]
        start_second = [w for w in words if w[0] == "Ahora"][0][1]
        self.assertTrue(end_first <= cuts[0] <= start_second)
        end_second = [w for w in words if w[0] == "recibidos."][0][2]
        self.assertTrue(end_second <= cuts[1] <= [w for w in words if w[0] == "Elige"][0][1])

    def test_unrecognized_line_is_not_trusted(self):
        words = self.words(["Haz clic en XML desde el ride. Transforma los rides en XML.", "algo distinto totalmente",
                            "Elige año, mes y día."])
        self.assertIsNone(tts.align_cuts(self.TEXTS, words, []))

    def test_recognized_share(self):
        heard = [("Haz", 0, 0.3), ("clic", 0.3, 0.6)]
        self.assertLess(tts.recognized_share(self.TEXTS, heard), tts.ALIGN_USEFUL)
        self.assertGreater(tts.recognized_share(self.TEXTS, self.words(
            ["Haz clic en XML desde el ride. Transforma los rides en XML.", "Ahora cambia la carpeta a recibidos.",
             "Elige año, mes y día."])), tts.ALIGN_USEFUL)

    def test_unrecognized_last_word_stays_in_its_line(self):
        # "Luego abre Perseo XML." -> whisper heard "Luego abre Perseo" ... and "XML" glued to the next segment start.
        texts = ["Luego abre Perseo XML.", "Haz clic en Carpeta de descargas."]
        words = [("Luego", 0.0, 0.3), ("abre", 0.35, 0.6), ("Perseo", 0.65, 1.0), ("XMLhaz", 1.1, 1.5),
                 ("clic", 1.9, 2.1), ("en", 2.15, 2.25), ("Carpeta", 2.3, 2.7), ("de", 2.75, 2.85),
                 ("descargas.", 2.9, 3.4)]
        cuts = tts.align_cuts(texts, words, [(1.55, 1.85)])
        self.assertEqual(len(cuts), 1)
        self.assertGreaterEqual(cuts[0], 1.5)          # the spoken "XML" (1.1-1.5 s) stays in the first clip
        self.assertLess(cuts[0], 1.9)                  # and the cut is before "clic"
