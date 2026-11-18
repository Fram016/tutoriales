"""tools/qa.py v2: automatic checks of reglas/reglas-video.md on timeline.json, layout.json and the MP4.

Run: .venv/Scripts/python.exe -m unittest discover -s tests -v
"""
import copy
import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1] / "tools"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "qa"
sys.path.insert(0, str(TOOLS))
import common  # noqa: E402
import qa  # noqa: E402

import yaml  # noqa: E402

TUTORIAL = yaml.safe_load((FIXTURES / "tutorial.yaml").read_text(encoding="utf-8"))


def fixture(video, name):
    return json.loads((FIXTURES / video / name).read_text(encoding="utf-8"))


def status(checks, check_id):
    found = [c for c in checks if c["id"] == check_id]
    if not found:
        raise AssertionError(f"no check {check_id} in {[c['id'] for c in checks]}")
    return found[0]["status"]


def failing(checks):
    return [c for c in checks if c["status"] == "FAIL"]


def item(layout, kind, step=None, index=0):
    found = [i for i in layout["items"] if i["kind"] == kind and (step is None or i.get("step") == step)]
    return found[index]


class LayoutChecksTest(unittest.TestCase):
    def setUp(self):
        self.tl = {v: fixture(v, "timeline.json") for v in ("tutorial", "redes")}
        self.lay = {v: fixture(v, "layout.json") for v in ("tutorial", "redes")}

    def checks(self, video="tutorial"):
        return qa.check_layout(self.lay[video], self.tl[video], TUTORIAL)

    def test_fixtures_pass_every_layout_check(self):
        for video in ("tutorial", "redes"):
            checks = self.checks(video)
            self.assertEqual(failing(checks), [], video)
            for check in checks:
                self.assertEqual(set(check), {"id", "rule", "status", "detail"})

    def test_O1_chip_over_active_element_fails(self):
        item(self.lay["tutorial"], "chip", "nuevo")["rect"] = [850, 310, 200, 60]
        self.assertEqual(status(self.checks(), "O1.chip_overlap"), "FAIL")

    def test_O1_semitransparent_or_low_contrast_chip_fails(self):
        item(self.lay["tutorial"], "chip", "nuevo")["opacity"] = 0.6
        self.assertEqual(status(self.checks(), "O1.chip_style"), "FAIL")
        item(self.lay["tutorial"], "chip", "nuevo")["opacity"] = 1.0
        item(self.lay["tutorial"], "chip", "guardar")["contrast"] = 2.1
        self.assertEqual(status(self.checks(), "O1.chip_style"), "FAIL")

    def test_O2_caption_over_toast_fails(self):
        item(self.lay["tutorial"], "result")["rect"] = [700, 920, 500, 80]
        checks = self.checks()
        self.assertEqual(status(checks, "O2.caption_overlap"), "FAIL")
        self.assertEqual(status(checks, "R2.result_clear"), "FAIL")

    def test_O2_caption_over_active_field_at_other_time_passes(self):
        active = item(self.lay["tutorial"], "active", "nuevo")
        active["rect"] = [700, 920, 300, 80]
        active["t0"], active["t1"] = 5.2, 5.5  # closing time: no caption then
        self.assertEqual(status(self.checks(), "O2.caption_overlap"), "PASS")

    def test_R2_cursor_over_toast_fails(self):
        cursor = item(self.lay["tutorial"], "cursor", "guardar")
        cursor["rect"], cursor["t0"], cursor["t1"] = [900, 120, 48, 48], 3.9, 4.5
        self.assertEqual(status(self.checks(), "R2.result_clear"), "FAIL")

    def test_R2_short_toast_fails(self):
        item(self.lay["tutorial"], "result")["t1"] = 4.3
        self.assertEqual(status(self.checks(), "R2.result_clear"), "FAIL")

    def test_R1_result_in_wide_shot_fails(self):
        self.lay["tutorial"]["camera"][3]["scale"] = 1.2
        self.assertEqual(status(self.checks(), "R1.detail"), "FAIL")

    def test_T1_line_ending_in_preposition_or_article_fails(self):
        caption = item(self.lay["tutorial"], "caption", "nuevo")
        caption["lines"] = ["Escribe el nombre con el", "correo"]
        self.assertEqual(status(self.checks(), "T1.last_word"), "FAIL")
        caption["lines"] = ["Escribe el nombre y", "después el correo"]
        self.assertEqual(status(self.checks(), "T1.last_word"), "FAIL")

    def test_T1_orphan_word_fails(self):
        item(self.lay["tutorial"], "caption", "guardar")["lines"] = ["Sale el aviso", "verde"]
        self.assertEqual(status(self.checks(), "T1.last_word"), "FAIL")

    def test_T1_long_line_or_three_lines_fails(self):
        caption = item(self.lay["tutorial"], "caption", "nuevo")
        caption["lines"] = ["x" * 43]
        self.assertEqual(status(self.checks(), "T1.lines"), "FAIL")
        caption["lines"] = ["Haz clic", "en Nuevo", "contacto ahora"]
        self.assertEqual(status(self.checks(), "T1.lines"), "FAIL")

    def test_T1_short_caption_fails(self):
        item(self.lay["tutorial"], "caption", "nuevo")["t1"] = 2.0
        self.assertEqual(status(self.checks(), "T1.duration"), "FAIL")

    def test_T1_caption_crossing_a_step_change_fails(self):
        item(self.lay["tutorial"], "caption", "nuevo")["t1"] = 3.6
        self.assertEqual(status(self.checks(), "T1.step"), "FAIL")

    def test_T2_small_font_fails_in_both_formats(self):
        self.lay["tutorial"]["font_px"] = 36
        self.assertEqual(status(self.checks(), "T2.font"), "FAIL")
        item(self.lay["redes"], "caption", "nuevo")["font_px"] = 32
        self.assertEqual(status(self.checks("redes"), "T2.font"), "FAIL")

    def test_C1_long_wide_shot_fails_but_not_in_opening_or_closing(self):
        self.lay["tutorial"]["camera"][0]["t1"] = 1.0  # opening wide: allowed
        self.assertEqual(status(self.checks(), "C1.context"), "PASS")
        self.lay["tutorial"]["camera"][1]["t1"] = 2.6
        self.lay["tutorial"]["camera"][2]["t0"] = 2.6
        self.lay["tutorial"]["camera"][2]["t1"] = 3.0
        self.lay["tutorial"]["camera"][3]["t0"] = 3.0
        self.assertEqual(status(self.checks(), "C1.context"), "FAIL")

    def test_C5_cursor_size_changes_fail(self):
        item(self.lay["tutorial"], "cursor", "guardar")["rect"] = [1550, 710, 96, 96]
        self.assertEqual(status(self.checks(), "C5.cursor"), "FAIL")

    def test_V1_shrunken_horizontal_in_vertical_fails(self):
        self.lay["redes"]["viewport"] = [0, 432, 1080, 1056]
        self.assertEqual(status(self.checks("redes"), "V1.viewport"), "FAIL")

    def test_V3_title_after_three_seconds_fails(self):
        item(self.lay["redes"], "title")["t1"] = 16.0
        self.assertEqual(status(self.checks("redes"), "V3.title"), "FAIL")

    def test_V4_overlays_in_unsafe_zones_fail(self):
        item(self.lay["redes"], "chip", "nuevo")["rect"] = [90, 100, 200, 70]
        self.assertEqual(status(self.checks("redes"), "V4.safe_zones"), "FAIL")
        item(self.lay["redes"], "chip", "nuevo")["rect"] = [90, 1180, 200, 70]
        item(self.lay["redes"], "caption", "guardar")["rect"] = [60, 1600, 960, 200]
        self.assertEqual(status(self.checks("redes"), "V4.safe_zones"), "FAIL")

    def test_V_checks_only_apply_to_vertical(self):
        ids = {c["id"] for c in self.checks("tutorial")}
        self.assertFalse({"V1.viewport", "V3.title", "V4.safe_zones"} & ids)

    def test_L1_L4_language_in_captions_fails(self):
        caption = item(self.lay["tutorial"], "caption", "nuevo")
        caption["text"] = "Tocamos Nuevo contacto acá"
        caption["lines"] = ["Tocamos Nuevo contacto acá"]
        checks = self.checks()
        self.assertEqual(status(checks, "L.captions"), "FAIL")
        detail = next(c["detail"] for c in checks if c["id"] == "L.captions")
        self.assertIn("L2", detail)
        self.assertIn("L4", detail)
        caption["text"] = caption["lines"][0] = "Ingresá tus datos"
        self.assertIn("L1", next(c["detail"] for c in self.checks() if c["id"] == "L.captions"))


class TimelineChecksTest(unittest.TestCase):
    def setUp(self):
        self.tl = {v: fixture(v, "timeline.json") for v in ("tutorial", "redes")}

    def test_fixtures_pass(self):
        for video in ("tutorial", "redes"):
            self.assertEqual(failing(qa.check_timeline(self.tl[video])), [], video)

    def test_A2_voice_gap_over_one_second_fails(self):
        self.tl["tutorial"]["steps"][1]["voice_start"] = 4.0
        self.tl["tutorial"]["steps"][1]["voice_duration"] = 0.9
        self.assertEqual(status(qa.check_timeline(self.tl["tutorial"]), "A2.voice_gaps"), "FAIL")

    def test_A2_long_closing_card_fails(self):
        self.tl["tutorial"]["closing"]["duration"] = 4.7
        self.tl["tutorial"]["total"] = 9.7
        self.assertEqual(status(qa.check_timeline(self.tl["tutorial"]), "A2.closing_card"), "FAIL")

    def test_RED2_duration_out_of_range_fails(self):
        self.tl["redes"]["total"] = 41.0
        self.assertEqual(status(qa.check_timeline(self.tl["redes"]), "S3.duration"), "FAIL")

    def test_PRO_and_NOV_ranges(self):
        for vtype, total, expected in (("PRO", 15.0, "FAIL"), ("PRO", 30.0, "PASS"),
                                       ("NOV", 31.0, "FAIL"), ("NOV", 16.0, "PASS")):
            tl = copy.deepcopy(self.tl["redes"])
            tl["type"], tl["total"] = vtype, total
            self.assertEqual(status(qa.check_timeline(tl), "S3.duration"), expected, (vtype, total))

    def test_E3_long_tutorial_without_chapters_fails(self):
        self.tl["tutorial"]["total"] = 400.0
        self.assertEqual(status(qa.check_timeline(self.tl["tutorial"]), "E3.chapters"), "FAIL")
        for i, step in enumerate(self.tl["tutorial"]["steps"]):
            step["chapter"] = i + 1
        self.assertEqual(status(qa.check_timeline(self.tl["tutorial"]), "E3.chapters"), "PASS")

    def test_snapshot_times_cover_opening_steps_results_and_closing(self):
        times = qa.snapshot_times(self.tl["tutorial"])
        self.assertEqual(times, sorted(times))
        self.assertIn(0.5, times)   # opening middle
        self.assertIn(2.0, times)   # step nuevo middle
        self.assertIn(4.0, times)   # step guardar middle
        self.assertIn(4.3, times)   # result (toast) visible
        self.assertIn(4.45, times)  # highlight visible
        self.assertIn(5.5, times)   # closing middle


class MediaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def make(self, name, *args):
        path = self.dir / name
        if not path.exists():
            common.ffmpeg(*args, str(path))
        return path

    def tone(self, name, gain_db):
        return self.make(name, "-f", "lavfi", "-i", "sine=f=440:d=3", "-af", f"volume={gain_db}dB", "-ac", "2")

    def test_A1_tone_at_minus_14_passes_and_loud_tone_fails(self):
        probe = self.tone("probe.wav", 0)
        lufs, _ = qa.loudness(probe)
        good = self.tone("good.wav", round(-14 - lufs, 2))
        checks = qa.check_loudness(good)
        self.assertEqual(status(checks, "A1.loudness"), "PASS", checks)
        self.assertEqual(status(checks, "A1.true_peak"), "PASS", checks)
        loud = self.make("loud.wav", "-f", "lavfi", "-i", "aevalsrc='0.99*sin(2*PI*440*t)|0.99*sin(2*PI*440*t)':d=3:s=48000")
        checks = qa.check_loudness(loud)
        self.assertEqual(status(checks, "A1.loudness"), "FAIL")
        self.assertEqual(status(checks, "A1.true_peak"), "FAIL")

    def test_A1_silence_is_measurable_and_fails(self):
        silent = self.make("silent.wav", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "2")
        checks = qa.check_loudness(silent)
        self.assertEqual(status(checks, "A1.loudness"), "FAIL")

    def test_A2_mix_with_a_gap_fails_and_continuous_passes(self):
        gap = self.make("gap.wav", "-f", "lavfi", "-i",
                        "aevalsrc='if(between(t,1,2.5),0,0.3*sin(2*PI*440*t))':d=3.5:s=48000")
        self.assertEqual(status(qa.check_silence(gap), "A2.silence"), "FAIL")
        tone = self.tone("tone.wav", 0)
        self.assertEqual(status(qa.check_silence(tone), "A2.silence"), "PASS")

    def test_C4_solid_color_fails_and_testsrc_passes(self):
        solid = self.make("solid.mp4", "-f", "lavfi", "-i", "color=c=white:s=1920x1080:d=2:r=30",
                          "-pix_fmt", "yuv420p")
        busy = self.make("busy.mp4", "-f", "lavfi", "-i", "testsrc=s=1920x1080:d=2:r=30", "-pix_fmt", "yuv420p")
        self.assertEqual(status(qa.check_empty_frames(solid, [(0.0, 2.0)], (1920, 1080)), "C4.empty_frames"), "FAIL")
        self.assertEqual(status(qa.check_empty_frames(busy, [(0.0, 2.0)], (1920, 1080)), "C4.empty_frames"), "PASS")

    def test_C4_ignores_opening_and_closing(self):
        solid = self.make("solid.mp4", "-f", "lavfi", "-i", "color=c=white:s=1920x1080:d=2:r=30",
                          "-pix_fmt", "yuv420p")
        self.assertEqual(status(qa.check_empty_frames(solid, [], (1920, 1080)), "C4.empty_frames"), "PASS")


class QaEndToEndTest(unittest.TestCase):
    """qa(slug) over a project on disk: fixtures + a generated 6 s testsrc MP4 at -14 LUFS."""

    @classmethod
    def setUpClass(cls):
        cls.media = tempfile.TemporaryDirectory()
        media = Path(cls.media.name)
        common.ffmpeg("-f", "lavfi", "-i", "sine=f=440:d=6", "-ac", "2", str(media / "probe.wav"))
        lufs, _ = qa.loudness(media / "probe.wav")
        cls.mp4 = media / "video.mp4"
        common.ffmpeg("-f", "lavfi", "-i", "testsrc=s=1920x1080:d=6:r=30", "-f", "lavfi", "-i", "sine=f=440:d=6",
                      "-af", f"volume={-14 - lufs:.2f}dB", "-ac", "2", "-c:v", "libx264", "-preset", "ultrafast",
                      "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", str(cls.mp4))

    @classmethod
    def tearDownClass(cls):
        cls.media.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(setattr, common, "PROJECTS", common.PROJECTS)
        common.PROJECTS = Path(self.tmp.name)
        self.pdir = common.PROJECTS / "crm"
        (self.pdir / "edit" / "tutorial").mkdir(parents=True)
        (self.pdir / "hf-tutorial").mkdir()
        (self.pdir / "out").mkdir()
        shutil.copy(FIXTURES / "tutorial.yaml", self.pdir / "tutorial.yaml")
        shutil.copy(FIXTURES / "tutorial" / "timeline.json", self.pdir / "edit" / "tutorial" / "timeline.json")
        shutil.copy(FIXTURES / "tutorial" / "layout.json", self.pdir / "hf-tutorial" / "layout.json")
        shutil.copy(self.mp4, self.pdir / "out" / "crm-tutorial.mp4")
        self.shots = mock.patch.object(qa, "take_snapshots", side_effect=lambda slug, video, times:
                                       [Path(f"at-{t:g}s.png") for t in times])
        self.snap = self.shots.start()
        self.addCleanup(self.shots.stop)

    def run_qa(self, video="tutorial"):
        out = io.StringIO()
        with redirect_stdout(out):
            ok = qa.qa("crm", video)
        return ok, out.getvalue()

    def test_passing_video_writes_report_and_lists_snapshots(self):
        ok, out = self.run_qa()
        report = json.loads((self.pdir / "qa" / "tutorial.json").read_text(encoding="utf-8"))
        self.assertTrue(ok, out)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(failing(report["checks"]), [])
        for check_id in ("tech.resolution", "tech.duration", "tech.audio", "A1.loudness", "A1.true_peak",
                         "A2.silence", "A2.voice_gaps", "A2.closing_card", "C4.empty_frames", "O1.chip_overlap",
                         "O2.caption_overlap", "R2.result_clear", "T1.lines", "T2.font", "C1.context", "C5.cursor",
                         "L.captions", "snapshots"):
            self.assertEqual(status(report["checks"], check_id), "PASS", check_id)
        self.snap.assert_called_once_with("crm", "tutorial", qa.snapshot_times(
            json.loads((FIXTURES / "tutorial" / "timeline.json").read_text(encoding="utf-8"))))
        self.assertIn("at-4.3s.png", out)
        self.assertIn("A1", out)
        self.assertIn("PASS", out)

    def test_missing_layout_fails_with_a_clear_message(self):
        (self.pdir / "hf-tutorial" / "layout.json").unlink()
        ok, out = self.run_qa()
        self.assertFalse(ok)
        report = json.loads((self.pdir / "qa" / "tutorial.json").read_text(encoding="utf-8"))
        layout = next(c for c in report["checks"] if c["id"] == "layout")
        self.assertEqual(layout["status"], "FAIL")
        self.assertIn("layout.json", layout["detail"])
        self.assertIn("FAIL", out)

    def test_missing_video_file_fails(self):
        (self.pdir / "out" / "crm-tutorial.mp4").unlink()
        ok, _ = self.run_qa()
        self.assertFalse(ok)
        report = json.loads((self.pdir / "qa" / "tutorial.json").read_text(encoding="utf-8"))
        self.assertEqual(status(report["checks"], "tech.file"), "FAIL")

    def test_wrong_resolution_for_format_fails(self):
        timeline = json.loads((FIXTURES / "tutorial" / "timeline.json").read_text(encoding="utf-8"))
        timeline["format"] = "9:16"
        (self.pdir / "edit" / "tutorial" / "timeline.json").write_text(json.dumps(timeline), encoding="utf-8")
        ok, _ = self.run_qa()
        self.assertFalse(ok)
        report = json.loads((self.pdir / "qa" / "tutorial.json").read_text(encoding="utf-8"))
        self.assertEqual(status(report["checks"], "tech.resolution"), "FAIL")

    def test_all_videos_are_checked_without_video_filter(self):
        ok, out = self.run_qa(video=None)
        self.assertFalse(ok)  # redes has no outputs in this project
        self.assertTrue((self.pdir / "qa" / "tutorial.json").exists())
        self.assertTrue((self.pdir / "qa" / "redes.json").exists())
        self.assertIn("redes", out)


if __name__ == "__main__":
    unittest.main()
