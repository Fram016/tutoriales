"""Per-project demo credentials: proyectos/<slug>/acceso.local.yaml.

Run: .venv/Scripts/python.exe -m unittest discover -s tests -v
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import common  # noqa: E402

TUTORIAL = "title: T\nsteps:\n  - id: a\n    narration: hola\n"


class AccessFileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(setattr, common, "PROJECTS", common.PROJECTS)
        common.PROJECTS = Path(self.tmp.name)
        self.pdir = common.PROJECTS / "crm"
        self.pdir.mkdir()
        (self.pdir / "tutorial.yaml").write_text(TUTORIAL, encoding="utf-8")
        for name in ("ACC_TEST_USER", "ACC_TEST_PASSWORD"):
            self.addCleanup(os.environ.pop, name, None)

    def test_access_file_resolves_env_refs(self):
        (self.pdir / "acceso.local.yaml").write_text(
            "ACC_TEST_USER: demo@crm.com\nACC_TEST_PASSWORD: 's3cr3t:x'\n", encoding="utf-8")
        common.load_tutorial("crm")
        self.assertEqual(common.resolve_env_ref("env:ACC_TEST_USER"), "demo@crm.com")
        self.assertEqual(common.resolve_env_ref("env:ACC_TEST_PASSWORD"), "s3cr3t:x")

    def test_access_file_overrides_dotenv_value(self):
        os.environ["ACC_TEST_USER"] = "from-dotenv"
        (self.pdir / "acceso.local.yaml").write_text("ACC_TEST_USER: from-project\n", encoding="utf-8")
        common.load_tutorial("crm")
        self.assertEqual(common.resolve_env_ref("env:ACC_TEST_USER"), "from-project")

    def test_missing_access_file_is_fine(self):
        data = common.load_tutorial("crm")
        self.assertEqual(data["title"], "T")

    def test_invalid_access_file_names_the_file(self):
        (self.pdir / "acceso.local.yaml").write_text("- not\n- a map\n", encoding="utf-8")
        with self.assertRaises(common.PipelineError) as ctx:
            common.load_tutorial("crm")
        self.assertIn("acceso.local.yaml", str(ctx.exception))

    def test_access_file_is_git_ignored(self):
        res = subprocess.run(["git", "check-ignore", "-q", "proyectos/cualquiera/acceso.local.yaml"],
                             cwd=common.ROOT)
        self.assertEqual(res.returncode, 0)


if __name__ == "__main__":
    unittest.main()
