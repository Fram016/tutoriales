"""A new take never wipes the previous one (a captcha-failed take left the Perseo XML project empty)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import capture  # noqa: E402


class KeepPreviousTakeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pdir = Path(self.tmp.name)

    def take(self, label):
        d = self.pdir / "capture"
        (d / "frames").mkdir(parents=True)
        (d / "actions.json").write_text(label, encoding="utf-8")

    def test_previous_take_is_moved_aside(self):
        self.take("toma 3")
        dest = capture.keep_previous_take(self.pdir, now=0)
        self.assertFalse((self.pdir / "capture").exists())
        self.assertEqual((dest / "actions.json").read_text(encoding="utf-8"), "toma 3")

    def test_nothing_to_keep_without_a_take(self):
        (self.pdir / "capture" / "frames").mkdir(parents=True)
        self.assertIsNone(capture.keep_previous_take(self.pdir))

    def test_only_the_newest_previous_takes_are_kept(self):
        for i in range(4):
            self.take(f"toma {i}")
            capture.keep_previous_take(self.pdir, now=1000 + i * 60)
        prev = sorted(self.pdir.glob("capture.prev-*"))
        self.assertEqual(len(prev), capture.KEEP_PREVIOUS)
        self.assertEqual((prev[-1] / "actions.json").read_text(encoding="utf-8"), "toma 3")


if __name__ == "__main__":
    unittest.main()
