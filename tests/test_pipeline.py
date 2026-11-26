"""pipeline.select: lint always runs first, so a partial run never works from a tutorial.yaml with errors."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import pipeline  # noqa: E402
from common import PipelineError  # noqa: E402


class SelectTest(unittest.TestCase):
    def test_partial_runs_start_with_lint(self):
        self.assertEqual(pipeline.select("tts", "compose", None),
                         ["lint", "tts", "edit", "music", "mix", "compose"])
        self.assertEqual(pipeline.select(None, None, "render"), ["lint", "render"])

    def test_full_run_and_lint_alone_keep_one_lint(self):
        self.assertEqual(pipeline.select(None, None, None), pipeline.STAGES)
        self.assertEqual(pipeline.select("lint", "capture", None), ["lint", "capture"])
        self.assertEqual(pipeline.select(None, None, "lint"), ["lint"])

    def test_invalid_combinations_still_fail(self):
        with self.assertRaises(PipelineError):
            pipeline.select("tts", None, "render")
        with self.assertRaises(PipelineError):
            pipeline.select("render", "tts", None)


if __name__ == "__main__":
    unittest.main()
