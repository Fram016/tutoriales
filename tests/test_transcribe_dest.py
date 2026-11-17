"""transcribe.py output folder: replica/ (mode B) or referencias/<name>/ (reference videos)."""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import common  # noqa: E402
import transcribe  # noqa: E402


class TranscribeDestTest(unittest.TestCase):
    def test_default_is_replica(self):
        self.assertEqual(transcribe.output_dir("crm"), common.PROJECTS / "crm" / "replica")

    def test_reference_goes_to_its_own_folder(self):
        self.assertEqual(transcribe.output_dir("crm", "uso-facturas"),
                         common.PROJECTS / "crm" / "referencias" / "uso-facturas")

    def test_reference_name_cannot_escape_the_project(self):
        for bad in ("../x", "a/b", "", "a b", "..", "C:"):
            with self.subTest(name=bad), self.assertRaises(common.PipelineError):
                transcribe.output_dir("crm", bad)

    def test_reference_folders_are_git_ignored(self):
        res = subprocess.run(["git", "check-ignore", "-q", "proyectos/crm/referencias/uso/audio.wav"],
                             cwd=common.ROOT)
        self.assertEqual(res.returncode, 0)

    def test_cli_help_documents_ref(self):
        out = subprocess.run([sys.executable, str(common.ROOT / "tools" / "transcribe.py"), "--help"],
                             capture_output=True, text=True, encoding="utf-8").stdout
        self.assertIn("--ref", out)


if __name__ == "__main__":
    unittest.main()
