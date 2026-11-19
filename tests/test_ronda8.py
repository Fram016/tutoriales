"""Round eight (odd/tasks/perseo-resultado.md T1; reglas/reglas-video.md §Parte 10: F1-F3): a video of the user becomes
a take (F2: tools/import_video_take.py, frames blurred before they are written, steps and boxes by hand) that
merge_takes joins after the recorded takes, and the "computer" context badge of the final part.

Run: .venv/Scripts/python.exe -m unittest tests.test_ronda8 -v
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import yaml
from PIL import Image

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import common  # noqa: E402
import compose  # noqa: E402
import merge_takes  # noqa: E402

try:
    import import_video_take as ivt  # noqa: E402
except ImportError:   # RED: the tool does not exist yet
    ivt = None

PYTHON = sys.executable
CELL = 4   # checkerboard square (px): sharp detail everywhere, flat once blurred


def checker_video(path: Path, size=(320, 180), seconds=2.0) -> None:
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w]
    board = (((xx // CELL) + (yy // CELL)) % 2 * 255).astype(np.uint8)
    png = path.with_suffix(".png")
    Image.fromarray(board).convert("RGB").save(png)
    common.ffmpeg("-loop", "1", "-i", str(png), "-t", str(seconds), "-r", "30", "-pix_fmt", "yuv420p",
                  "-c:v", "libx264", "-crf", "12", str(path))
    png.unlink()


def detail(frame: Path, box) -> float:
    """Standard deviation of a region: ~127 on the checkerboard, near 0 once blurred."""
    x, y, w, h = box
    with Image.open(frame) as img:
        return float(np.asarray(img.convert("L").crop((x, y, x + w, y + h)), dtype=np.float32).std())


def spec(**over):
    data = {"fps": 10, "trim": [0.5, 1.5], "viewport": [320, 180],
            "blur": [{"box": [0, 0, 80, 60], "from": 0.75, "to": 1.25}, {"box": [240, 140, 80, 40]}],
            "steps": [{"id": "abrir", "t0": 0.5, "t1": 1.0,
                       "events": [{"type": "focus", "t": 0.6, "box": {"x": 100, "y": 50, "w": 40, "h": 20}},
                                  {"type": "click", "t": 0.9, "box": {"x": 100, "y": 80, "w": 60, "h": 20},
                                   "selector": "manual:fila", "target_text": "Perseo XML"}]},
                      {"id": "ver", "t0": 1.0, "t1": 1.5,
                       "events": [{"type": "press_visual", "t": 1.1, "box": {"x": 10, "y": 10, "w": 20, "h": 10}},
                                  {"type": "result", "t": 1.2, "box": {"x": 100, "y": 50, "w": 120, "h": 80},
                                   "target_ok": True}]}]}
    data.update(over)
    return data


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg")
class ImportVideoTakeTest(unittest.TestCase):
    """F2: the same take format as capture.py (frames/, frames.json, actions.json), censored before writing (F3)."""

    @classmethod
    def setUpClass(cls):
        cls.src_dir = Path(tempfile.mkdtemp())
        cls.video = cls.src_dir / "user.mp4"
        checker_video(cls.video)
        cls.big = cls.src_dir / "big.mp4"
        checker_video(cls.big, (640, 360))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.src_dir, ignore_errors=True)

    def setUp(self):
        self.assertIsNotNone(ivt, "falta tools/import_video_take.py")
        self.tmp = Path(tempfile.mkdtemp())
        self.out = self.tmp / "takes" / "resultado"
        self.scratch = self.tmp / "scratch"
        self.scratch.mkdir()
        patcher = mock.patch.object(tempfile, "tempdir", str(self.scratch))
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_import(self, data, video=None):
        return ivt.import_video(video or self.video, data, self.out)

    def test_frames_on_the_take_clock(self):
        self.run_import(spec())
        frames = json.loads((self.out / "frames.json").read_text(encoding="utf-8"))
        self.assertEqual(frames["errors"], 0)
        self.assertEqual([f["t"] for f in frames["frames"]], [round(k / 10, 4) for k in range(10)])
        self.assertEqual([f["file"] for f in frames["frames"]][:2], ["f000000.jpg", "f000001.jpg"])
        for f in frames["frames"]:
            with Image.open(self.out / "frames" / f["file"]) as img:
                self.assertEqual(img.size, (320, 180))

    def test_blur_only_inside_its_box_and_window(self):
        self.run_import(spec())
        files = sorted((self.out / "frames").glob("*.jpg"))
        # Source time of frame k = 0.5 + k/10: the window 0.75-1.25 covers frames 3..7.
        blurred = [k for k, f in enumerate(files) if detail(f, (8, 8, 64, 44)) < 20]
        self.assertEqual(blurred, [3, 4, 5, 6, 7])
        for f in files:
            self.assertLess(detail(f, (248, 148, 64, 24)), 20, f.name)      # no window: every frame
            self.assertGreater(detail(f, (120, 60, 80, 60)), 90, f.name)    # outside the boxes: untouched

    def test_actions_like_a_recorded_take(self):
        actions = self.run_import(spec())
        saved = json.loads((self.out / "actions.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, actions)
        self.assertEqual(saved["viewport"], [320, 180])
        self.assertIsNone(saved["failure"])
        self.assertNotIn("surfaces", saved)
        abrir, ver = saved["steps"]
        self.assertEqual((abrir["id"], abrir["t0"], abrir["t1"]), ("abrir", 0.0, 0.5))
        # The frames show the user's own pointer: compose must not draw a second one.
        self.assertEqual([s["cursor"] for s in saved["steps"]], ["recorded", "recorded"])
        goto, focus, click = abrir["events"]
        # A take of its own is a new screen: compose cuts to it after the previous take (C7, C10).
        self.assertEqual(goto, {"type": "goto", "t": 0.0})
        self.assertNotIn("goto", [e["type"] for e in ver["events"]])
        self.assertEqual(focus, {"type": "focus", "t": 0.1, "selector": "manual:abrir",
                                 "box": {"x": 100, "y": 50, "w": 40, "h": 20}, "point": {"x": 120, "y": 60},
                                 "target_ok": True})
        self.assertEqual(click["type"], "click")
        self.assertEqual(click["t"], 0.4)
        self.assertEqual(click["selector"], "manual:fila")
        self.assertEqual(click["target_text"], "Perseo XML")
        self.assertEqual(click["frame_box"], {"x": 100, "y": 80, "w": 60, "h": 20})
        self.assertNotIn("visual", click)
        press, result = ver["events"]
        # D4/I2 shape: press_visual is a click shown without dispatching it.
        self.assertEqual((press["type"], press.get("visual"), press["t"]), ("click", True, 0.6))
        self.assertEqual((result["type"], result["t"], result["point"]), ("result", 0.7, {"x": 160, "y": 90}))

    def test_scale_and_crop_map_frames_and_boxes(self):
        data = spec(blur=[{"box": [0, 0, 160, 120]}])
        data["steps"] = [{"id": "abrir", "t0": 0.5, "t1": 1.5,
                          "events": [{"type": "result", "t": 1.0, "box": {"x": 200, "y": 100, "w": 120, "h": 40}}]}]
        actions = self.run_import(data, self.big)        # 640x360 -> viewport 320x180: everything halves
        self.assertEqual(actions["steps"][0]["events"][1]["box"], {"x": 100, "y": 50, "w": 60, "h": 20})
        first = self.out / "frames" / "f000000.jpg"
        self.assertLess(detail(first, (4, 4, 72, 52)), 20)
        self.assertGreater(detail(first, (120, 70, 80, 60)), 90)
        # crop: the region of interest [0, 0, 160, 90] of the big video fills the viewport (2x).
        data["crop"] = [0, 0, 160, 90]
        actions = self.run_import(data, self.big)
        self.assertEqual(actions["steps"][0]["events"][1]["box"], {"x": 400, "y": 200, "w": 240, "h": 80})
        self.assertEqual(actions["viewport"], [320, 180])

    def test_no_unblurred_frame_stays_on_disk(self):
        self.run_import(spec())
        self.assertEqual(list(self.scratch.iterdir()), [])
        with mock.patch.object(ivt, "censor_frame", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                self.run_import(spec())
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_bad_specs_fail_before_writing(self):
        cases = [
            (spec(fps=0), "'fps' tiene que ser un número mayor que 0"),
            (spec(trim=[1.5, 0.5]), "'trim' tiene que ser [inicio, fin] con inicio < fin"),
            (spec(blur=[{"box": [0, 0, 10]}]), "blur[0]: 'box' tiene que ser [x, y, ancho, alto]"),
            (spec(steps=[{"id": "a", "t0": 0.2, "t1": 1.0, "events": []}]),
             "paso a: t0/t1 tienen que quedar dentro de trim (0.5-1.5 s)"),
            (spec(steps=[{"id": "a", "t0": 0.5, "t1": 1.0,
                          "events": [{"type": "type", "t": 0.6, "box": {"x": 0, "y": 0, "w": 1, "h": 1}}]}]),
             "paso a: evento 'type' desconocido (válidos: click, focus, highlight, hover, press_visual, result)"),
            (spec(steps=[{"id": "a", "t0": 0.5, "t1": 1.0,
                          "events": [{"type": "click", "t": 1.2, "box": {"x": 0, "y": 0, "w": 1, "h": 1}}]}]),
             "paso a: el evento click (1.2 s) queda fuera del paso (0.5-1 s)"),
            (spec(steps=[{"id": "a", "t0": 0.5, "t1": 1.0, "events": [{"type": "click", "t": 0.6}]}]),
             "paso a: el evento click necesita box {x, y, w, h}"),
            (spec(steps=[{"id": "a", "t0": 0.5, "t1": 0.8, "events": []},
                         {"id": "a", "t0": 0.8, "t1": 1.0, "events": []}]), "el paso 'a' está repetido"),
        ]
        for data, message in cases:
            with self.subTest(message=message), self.assertRaises(common.PipelineError) as ctx:
                self.run_import(data)
            self.assertIn(message, str(ctx.exception))
            self.assertFalse(self.out.exists())

    def test_trim_past_the_video_fails(self):
        with self.assertRaises(common.PipelineError) as ctx:
            self.run_import(spec(trim=[0.5, 9.0]))
        self.assertIn("'trim' termina en 9 s pero el video dura 2.0 s", str(ctx.exception))
        self.assertFalse(self.out.exists())

    def test_a_previous_take_is_moved_aside(self):
        self.run_import(spec())
        self.run_import(spec())
        prev = list(self.out.parent.glob("resultado.prev-*"))
        self.assertEqual(len(prev), 1)
        self.assertTrue((prev[0] / "actions.json").exists())

    def test_merge_takes_joins_it(self):
        self.run_import(spec())
        other = self.tmp / "takes" / "otra"
        (other / "frames").mkdir(parents=True)
        Image.new("RGB", (320, 180)).save(other / "frames" / "f000000.jpg")
        (other / "frames.json").write_text(json.dumps({"frames": [{"file": "f000000.jpg", "t": 0.0}], "errors": 0}))
        (other / "actions.json").write_text(json.dumps({"viewport": [320, 180], "failure": None,
                                                        "steps": [{"id": "antes", "t0": 0.0, "t1": 1.0, "events": []}]}))
        pdir = self.tmp / "proyecto"
        pdir.mkdir()
        actions = merge_takes.merge_takes(pdir, [other, self.out])
        self.assertEqual([s["id"] for s in actions["steps"]], ["antes", "abrir", "ver"])
        self.assertEqual(actions["steps"][1]["t0"], 1.2)          # end of the first take + GAP
        self.assertEqual(actions["steps"][1]["events"][2]["t"], 1.6)

    def test_cli(self):
        spec_file = self.tmp / "resultado.yaml"
        spec_file.write_text(yaml.safe_dump(spec()), encoding="utf-8")
        res = subprocess.run([PYTHON, str(TOOLS / "import_video_take.py"), str(self.video), "--spec", str(spec_file),
                              "--out", str(self.out)], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("[import] 10 cuadros (10 fps), 2 pasos, 2 zonas difuminadas", res.stdout)
        self.assertNotIn(str(self.src_dir), res.stdout)            # the source path may carry the user name
        bad = self.tmp / "bad.yaml"
        bad.write_text(yaml.safe_dump(spec(fps=-1)), encoding="utf-8")
        res = subprocess.run([PYTHON, str(TOOLS / "import_video_take.py"), str(self.video), "--spec", str(bad),
                              "--out", str(self.tmp / "otra")], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 1)
        self.assertIn("ERROR: ", res.stderr)
        self.assertIn("'fps' tiene que ser un número mayor que 0", res.stderr)
        self.assertFalse((self.tmp / "otra").exists())


def recorded_timeline(recorded=True):
    """Two steps: a recorded take (compose draws the cursor) and an imported one (the frames carry the pointer)."""
    def click(t, x):
        return {"type": "click", "t": t, "t_end": t, "selector": "manual:x", "box": {"x": x, "y": 300, "w": 200, "h": 40},
                "point": {"x": x + 100, "y": 320}, "frame_box": {"x": x, "y": 300, "w": 200, "h": 40}, "target_ok": True}
    imported = {"id": "carpeta", "number": 2, "title": "Carpeta", "narration": "En Perseo XML están las carpetas.",
                "start": 8.0, "duration": 4.0, "voice_start": 8.2, "voice_duration": 2.5, "events": [click(9.0, 900)]}
    if recorded:
        imported["cursor"] = "recorded"
    return {"video": "tutorial", "type": "TUT", "format": "16:9", "total": 12.0, "product": "Perseo XML",
            "title": "T", "opening": None, "requirements": None, "closing": None, "pace": "fast",
            "screen_start": 3.6, "screen_end": 12.0, "steps": [
                {"id": "consultar", "number": 1, "title": "Consulta", "narration": "Haz clic en Consultar.",
                 "start": 3.6, "duration": 4.4, "voice_start": 3.8, "voice_duration": 1.5, "events": [click(5.5, 300)]},
                imported]}


class RecordedCursorTest(unittest.TestCase):
    """F2: an imported video already shows the user's pointer; compose hides its own arrow there (one cursor, C5) and
    keeps the click halo on the target."""

    def brand(self):
        return json.loads((TOOLS.parent / "templates" / "fixtures" / "brand.json").read_text(encoding="utf-8"))

    def test_edit_carries_the_flag(self):
        import edit
        tut = {"title": "T", "product": "P", "viewport": [1920, 1080]}
        video = {"id": "tutorial", "type": "TUT", "format": "16:9", "requirements": None, "closing": None,
                 "opening": {"narration": "Aprendes algo."},
                 "steps": [{"id": "a", "number": 1, "narration": "Abre la carpeta."},
                           {"id": "b", "number": 2, "narration": "Abre la otra."}]}
        actions = {"steps": [{"id": "a", "t0": 0.0, "t1": 2.0, "events": []},
                             {"id": "b", "t0": 2.0, "t1": 4.0, "events": [], "cursor": "recorded"}]}
        tl = edit.plan_video(tut, video, actions, [], {"opening": 2.0, "a": 1.5, "b": 1.5})
        self.assertNotIn("cursor", tl["steps"][0])          # PRESERVE: recorded takes keep their timeline
        self.assertEqual(tl["steps"][1]["cursor"], "recorded")

    def plan_described(self, recorded):
        import edit
        tut = {"title": "T", "product": "Perseo XML", "viewport": [1920, 1080]}
        video = {"id": "tutorial", "type": "TUT", "format": "16:9", "requirements": None, "closing": None,
                 "pace": "fast", "opening": {"narration": "Aprendes algo."},
                 "steps": [{"id": "carpeta", "number": 1, "narration": "En Perseo XML están las carpetas."}]}
        step = {"id": "carpeta", "t0": 0.0, "t1": 2.0, "events": [
            {"type": "click", "t": 0.2, "selector": "manual:fila", "box": {"x": 248, "y": 187, "w": 600, "h": 25},
             "point": {"x": 548, "y": 200}},
            {"type": "result", "t": 0.8, "selector": "manual:carpetas", "box": {"x": 248, "y": 186, "w": 600, "h": 54},
             "point": {"x": 548, "y": 213}}]}
        if recorded:
            step["cursor"] = "recorded"
        tl = edit.plan_video(tut, video, {"steps": [step]}, [], {"opening": 1.5, "carpeta": 3.0})
        return tl["steps"][0]

    def test_a_description_over_the_users_video_does_not_hold_its_click(self):
        # F2/N14: the user opens the folder and the narration describes it while it is on screen; nothing asks for
        # the click, so N1 does not hold the frame before it until the sentence ends.
        step = self.plan_described(recorded=True)
        click = step["events"][0]
        self.assertIsNone(step["action_t"])
        self.assertLess(click["t"], step["voice_start"] + step["voice_duration"] - 1.0)   # C7/C3 lead only
        # PRESERVE: in a recorded take the same step still waits for its narration (N1).
        step = self.plan_described(recorded=False)
        self.assertIsNotNone(step["action_t"])
        self.assertGreaterEqual(step["events"][0]["t"], step["voice_start"] + step["voice_duration"] - 0.3 - 1e-6)

    def test_compose_hides_its_arrow_over_the_imported_steps(self):
        html, lay = compose.build(recorded_timeline(), self.brand())
        self.assertEqual(lay["cursor_recorded"], [[8.0, 12.0]])
        cursors = [i for i in lay["items"] if i["kind"] == "cursor"]
        self.assertEqual([c["t0"] for c in cursors], [5.5])
        self.assertIn('tl.set("#cursor-arrow", {opacity: 0}, 8);', html)
        self.assertIn('tl.set("#cursor-arrow", {opacity: 1}, 12);', html)
        self.assertIn('tl.set("#halo", {scale: 0.3, opacity: 0.9}, 9);', html)   # the click is still marked

    def test_consecutive_imported_steps_hide_it_once(self):
        # Step times are rounded apart (90.114 / 90.115): the arrow must not come back between two imported steps.
        tl = recorded_timeline()
        tl["total"] = tl["screen_end"] = 16.0
        tl["steps"][1]["duration"] = 4.001
        tl["steps"].append({**tl["steps"][1], "id": "recibidos", "number": 3, "start": 12.0, "duration": 4.0,
                            "events": []})
        html, lay = compose.build(tl, self.brand())
        self.assertEqual(lay["cursor_recorded"], [[8.0, 16.0]])
        self.assertEqual(html.count('"#cursor-arrow", {opacity: 0}'), 1)

    def test_without_imported_steps_nothing_changes(self):
        html, lay = compose.build(recorded_timeline(recorded=False), self.brand())
        self.assertEqual(lay["cursor_recorded"], [])
        self.assertEqual([c["t0"] for c in lay["items"] if c["kind"] == "cursor"], [5.5, 9.0])
        self.assertNotIn('"#cursor-arrow", {opacity', html)


class DescribedSyncTest(unittest.TestCase):
    """N1 in qa matches edit: a description over the user's own video (F2) asks for no action."""

    def run_check(self, recorded, narration="En Perseo XML están las carpetas."):
        import qa
        step = {"id": "carpeta", "narration": narration, "start": 10.0, "duration": 4.0, "voice_start": 10.2,
                "voice_duration": 3.5, "action_t": None, "instruction_duration": 3.5,
                "events": [{"type": "click", "t": 10.6, "selector": "manual:fila"}]}
        if recorded:
            step["cursor"] = "recorded"
        captions = [{"t0": 10.2, "t1": 13.7, "text": narration, "step": "carpeta"}]
        return qa.check_sync(captions, {"pace": "fast", "steps": [step]})

    def test_a_description_is_not_an_instruction(self):
        self.assertEqual(self.run_check(True)["status"], "PASS")

    def test_an_instruction_or_a_recorded_take_still_counts(self):
        # PRESERVE: a recorded take keeps N1, and an imperative over the user's video too.
        self.assertEqual(self.run_check(False)["status"], "FAIL")
        self.assertEqual(self.run_check(True, "Abre la carpeta Perseo XML.")["status"], "FAIL")


class EstablishingAtTheCutTest(unittest.TestCase):
    """C7 in qa: a screen starts where compose cut (edit's mark moved to the change seen in the pixels, CUT_KEEP)."""

    def run_check(self, cuts):
        import qa
        timeline = {"pace": "fast", "screen_end": 20.0, "steps": [
            {"id": "a", "start": 3.0, "duration": 5.0, "events": []},
            {"id": "b", "start": 8.0, "duration": 6.0, "events": [{"type": "click", "t": 9.504, "screen_at": 9.624}]}]}
        camera = [{"kind": "context", "t0": 3.0, "t1": 3.8, "x": 0, "y": 0, "scale": 1.0},
                  {"kind": "detail", "t0": 3.8, "t1": 9.6, "x": 0, "y": 0, "scale": 1.3},
                  {"kind": "form", "t0": 9.6, "t1": 14.0, "x": 0, "y": 0, "scale": 1.1}]
        return qa.check_establishing(camera, timeline, 1.0, "16:9", [], (), cuts)

    def test_the_form_shot_at_the_cut_establishes_the_screen(self):
        self.assertEqual(self.run_check([9.598])["status"], "PASS")

    def test_without_the_cut_the_mark_is_used(self):
        # PRESERVE: no layout cut (or one farther than CUT_KEEP) leaves edit's mark.
        self.assertEqual(self.run_check([])["status"], "FAIL")
        self.assertEqual(self.run_check([9.3])["status"], "FAIL")


class ComputerContextTest(unittest.TestCase):
    """F1: the final part happens in the user's computer (File Explorer): its own neutral badge."""

    def test_badge_and_schema(self):
        common.validate_tutorial({"title": "T", "steps": [{"id": "a", "narration": "x", "context": "computer"}],
                                  "videos": [{"id": "tutorial", "type": "TUT", "opening": {"narration": "Aprendes."}}]})
        self.assertEqual(compose.context_label({"product": "Perseo XML"}, "computer"), "En tu equipo")
        # PRESERVE: the existing labels are unchanged.
        self.assertEqual(compose.context_label({"product": "Perseo XML"}, "chrome"), "En Chrome")
        self.assertEqual(compose.context_label({"product": "Perseo XML"}, "extension"), "En Perseo XML")
        with self.assertRaises(common.PipelineError) as ctx:
            common.validate_tutorial({"title": "T", "steps": [{"id": "a", "narration": "x", "context": "pc"}],
                                      "videos": [{"id": "tutorial", "type": "TUT", "opening": {"narration": "A."}}]})
        self.assertIn("'context' tiene que ser sri, extension, page, chrome o computer (N17)", str(ctx.exception))

    def test_perseo_named_in_the_computer_needs_the_visual_review(self):
        import qa
        timeline = {"steps": [{"id": "carpetas", "context": "computer", "start": 10.0, "duration": 3.0, "events": []}],
                    "surfaces": {"popup": {"windows": [[30.0, 35.0]]}}}
        captions = [{"t0": 10.3, "t1": 12.0, "text": "En Perseo XML están las carpetas.", "step": "carpetas"}]
        res = qa.check_named(captions, {"surface": [{"t0": 30.0, "t1": 35.0}]}, timeline)
        self.assertEqual(res["status"], "WARN", res)
        self.assertIn("«En Perseo XML están las carpetas.» nombra Perseo en tu equipo", res["detail"])


if __name__ == "__main__":
    unittest.main()
