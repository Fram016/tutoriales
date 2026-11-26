"""S7 (odd/tasks/perseo-xml-v5.md T6): one take per part, so a failed part is re-recorded alone and merged again."""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import capture  # noqa: E402
from common import PipelineError  # noqa: E402

SLUG = "demo-partes"


def tutorial():
    steps = [("abrir", 1), ("entrar", 1), ("cliente", 2), ("emitidos", 3), ("recibidos", 3)]
    return {"title": "Demo", "slug": SLUG, "app_url": "https://app.test/",
            "parts": [{"n": 1, "title": "Uno"}, {"n": 2, "title": "Dos"}, {"n": 3, "title": "Tres"}],
            "steps": [{"id": sid, "part": n, "actions": [{"click": f"#{sid}"}]} for sid, n in steps]}


class CapturePartsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.pdir = Path(tmp.name)
        self.tut = tutorial()
        self.recorded = []
        self.fail_on = None
        for name, value in (("load_tutorial", lambda slug, file="tutorial.yaml": self.tut),
                            ("project_dir", lambda slug: self.pdir),
                            ("capture", self.fake_capture)):
            patcher = mock.patch.object(capture, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_take(self, out: str, n: int, label: str = "nueva"):
        """A minimal recorded take of part n (the recorder is never launched)."""
        take = self.pdir / out
        (take / "frames").mkdir(parents=True, exist_ok=True)
        for f in ("f0.png", "f1.png"):
            (take / "frames" / f).write_bytes(b"png")
        ids = [s["id"] for s in self.tut["steps"] if s["part"] == n]
        steps = [{"id": sid, "t0": i, "t1": i + 1, "events": []} for i, sid in enumerate(ids)]
        (take / "actions.json").write_text(json.dumps({"viewport": [1920, 1080], "steps": steps, "failure": None,
                                                       "label": label}), encoding="utf-8")
        (take / "frames.json").write_text(json.dumps({"frames": [{"file": "f0.png", "t": 0.0},
                                                                 {"file": "f1.png", "t": 1.0}], "errors": 0}),
                                          encoding="utf-8")

    def fake_capture(self, slug, file="tutorial.yaml", out=None, part=None):
        self.recorded.append((out, part))
        if part is None:
            return {}
        if part == self.fail_on:
            raise PipelineError("La toma se cortó: No encontré el elemento: #cliente. "
                                "Revisa el selector en tutorial.yaml y repite.")
        self.write_take(out, part)
        return {}

    def merged(self):
        return json.loads((self.pdir / "capture" / "merged.json").read_text(encoding="utf-8"))

    def run_quiet(self, fn, *args, **kwargs):
        with redirect_stdout(io.StringIO()):
            return fn(*args, **kwargs)

    # pure parts

    def test_part_steps_selects_only_that_part_in_order(self):
        self.assertEqual([s["id"] for s in capture.part_steps(self.tut, 3)], ["emitidos", "recibidos"])
        self.assertEqual([s["id"] for s in capture.part_steps(self.tut, 1)], ["abrir", "entrar"])

    def test_part_take_dir_is_takes_part_n(self):
        self.assertEqual(capture.part_take_dir(2), "takes/part-2")
        self.assertEqual(capture.part_take_dir(10), "takes/part-10")

    def test_take_config_of_a_part_records_only_its_steps_into_its_take_dir(self):
        _, out_dir, config = capture.take_config(SLUG, out=capture.part_take_dir(2), part=2)
        self.assertEqual(out_dir, self.pdir / "takes" / "part-2")
        self.assertEqual(config["outDir"], (self.pdir / "takes" / "part-2").as_posix())
        self.assertEqual([s["id"] for s in config["steps"]], ["cliente"])
        self.assertEqual(config["startUrl"], "https://app.test/")

    def test_rerecord_command(self):
        self.assertEqual(capture.rerecord_command(SLUG, 2),
                         ".venv/Scripts/python.exe tools/capture.py demo-partes --part 2")

    def test_invalid_part_number_names_the_parts(self):
        for n in (9, 0):
            with self.subTest(n=n):
                with self.assertRaises(PipelineError) as err:
                    self.run_quiet(capture.capture_parts, SLUG, part=n)
                self.assertEqual(str(err.exception),
                                 f"la parte {n} no tiene pasos en tutorial.yaml (partes: 1, 2, 3)")
        self.assertEqual(self.recorded, [])
        self.assertEqual(list(self.pdir.iterdir()), [])

    def test_tutorial_without_parts_cannot_record_by_part(self):
        del self.tut["parts"]
        for step in self.tut["steps"]:
            del step["part"]
        with self.assertRaises(PipelineError) as err:
            self.run_quiet(capture.capture_parts, SLUG)
        self.assertEqual(str(err.exception), "tutorial.yaml no tiene 'parts' (N16): graba la toma entera con "
                                             ".venv/Scripts/python.exe tools/capture.py demo-partes")
        self.assertEqual(self.recorded, [])

    # orchestration (fake recorder, real merge_takes)

    def test_by_part_records_each_part_and_merges_in_part_order(self):
        self.run_quiet(capture.capture_parts, SLUG)
        self.assertEqual(self.recorded, [("takes/part-1", 1), ("takes/part-2", 2), ("takes/part-3", 3)])
        takes = [Path(t["take"]).name for t in self.merged()["takes"]]
        self.assertEqual(takes, ["part-1", "part-2", "part-3"])
        actions = json.loads((self.pdir / "capture" / "actions.json").read_text(encoding="utf-8"))
        self.assertEqual([s["id"] for s in actions["steps"]], ["abrir", "entrar", "cliente", "emitidos", "recibidos"])

    def test_failed_part_keeps_earlier_takes_and_names_the_rerecord_command(self):
        self.fail_on = 2
        with self.assertRaises(PipelineError) as err:
            self.run_quiet(capture.capture_parts, SLUG)
        self.assertEqual(str(err.exception),
                         "La parte 2 falló: La toma se cortó: No encontré el elemento: #cliente. Revisa el selector "
                         "en tutorial.yaml y repite. Las tomas de las otras partes quedan intactas y capture/ no "
                         "cambió. Regrábala sola con: .venv/Scripts/python.exe tools/capture.py demo-partes --part 2"
                         " y después graba las partes que faltan: 3 (--part N).")
        self.assertEqual(self.recorded, [("takes/part-1", 1), ("takes/part-2", 2)])
        self.assertTrue((self.pdir / "takes" / "part-1" / "actions.json").is_file())
        self.assertFalse((self.pdir / "takes" / "part-3").exists())
        self.assertFalse((self.pdir / "capture").exists())

    def test_part_rerecords_only_that_part_then_merges(self):
        for n in (1, 2, 3):
            self.write_take(capture.part_take_dir(n), n, label="vieja")
        self.run_quiet(capture.capture_parts, SLUG, part=2)
        self.assertEqual(self.recorded, [("takes/part-2", 2)])
        self.assertEqual([Path(t["take"]).name for t in self.merged()["takes"]], ["part-1", "part-2", "part-3"])
        label = lambda n: json.loads((self.pdir / "takes" / f"part-{n}" / "actions.json")  # noqa: E731
                                     .read_text(encoding="utf-8"))["label"]
        self.assertEqual([label(1), label(2), label(3)], ["vieja", "nueva", "vieja"])

    def test_failed_single_part_names_only_its_command(self):
        for n in (1, 2, 3):
            self.write_take(capture.part_take_dir(n), n, label="vieja")
        self.fail_on = 3
        with self.assertRaises(PipelineError) as err:
            self.run_quiet(capture.capture_parts, SLUG, part=3)
        self.assertTrue(str(err.exception).startswith("La parte 3 falló: "))
        self.assertTrue(str(err.exception).endswith(
            "Regrábala sola con: .venv/Scripts/python.exe tools/capture.py demo-partes --part 3"))
        self.assertFalse((self.pdir / "capture").exists())

    def test_part_with_other_takes_missing_is_not_merged(self):
        self.write_take(capture.part_take_dir(1), 1)
        with self.assertRaises(PipelineError) as err:
            self.run_quiet(capture.capture_parts, SLUG, part=2)
        self.assertEqual(str(err.exception),
                         "La toma de la parte 2 quedó en takes/part-2, pero capture/ no se unió: faltan las tomas de "
                         "las partes 3. Grábalas con: .venv/Scripts/python.exe tools/capture.py demo-partes --part 3")
        self.assertTrue((self.pdir / "takes" / "part-2" / "actions.json").is_file())
        self.assertFalse((self.pdir / "capture").exists())

    # CLI

    def main(self, *argv):
        with mock.patch.object(sys, "argv", ["capture.py", *argv]):
            capture.main()

    def test_cli_part_and_by_part_call_capture_parts(self):
        with mock.patch.object(capture, "capture_parts") as parts:
            self.main(SLUG, "--by-part")
            self.main(SLUG, "--part", "4")
        self.assertEqual(parts.call_args_list, [mock.call(SLUG, None), mock.call(SLUG, 4)])

    def test_cli_whole_take_is_unchanged(self):
        self.main(SLUG)
        self.main(SLUG, "--config", "install.yaml", "--out", "takes/install")
        self.assertEqual(self.recorded, [(None, None), ("takes/install", None)])

    def test_cli_rejects_mixing_part_options(self):
        for argv in ((SLUG, "--by-part", "--part", "2"), (SLUG, "--part", "2", "--out", "takes/x"),
                     (SLUG, "--by-part", "--config", "uso.yaml")):
            with self.subTest(argv=argv):
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exit_:
                    self.main(*argv)
                self.assertEqual(exit_.exception.code, 2)
        self.assertEqual(self.recorded, [])


if __name__ == "__main__":
    unittest.main()
