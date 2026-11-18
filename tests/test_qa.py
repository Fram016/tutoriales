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
        item(self.lay["redes"], "caption", "nuevo")["rect"] = [90, 100, 200, 70]
        self.assertEqual(status(self.checks("redes"), "V4.safe_zones"), "FAIL")
        item(self.lay["redes"], "caption", "nuevo")["rect"] = [60, 1380, 960, 140]
        item(self.lay["redes"], "caption", "guardar")["rect"] = [60, 1400, 960, 200]
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


class RoundTwoChecksTest(unittest.TestCase):
    """C7-C10 and N1-N9 (reglas/reglas-video.md Parte 4)."""

    def setUp(self):
        self.tl = {v: fixture(v, "timeline.json") for v in ("tutorial", "redes")}
        self.lay = {v: fixture(v, "layout.json") for v in ("tutorial", "redes")}
        self.tut = copy.deepcopy(TUTORIAL)

    def checks(self, video="tutorial"):
        return qa.check_layout(self.lay[video], self.tl[video], self.tut)

    def detail(self, checks, check_id):
        return next(c["detail"] for c in checks if c["id"] == check_id)

    def test_fixtures_pass_round_two_checks(self):
        for video in ("tutorial", "redes"):
            checks = self.checks(video)
            for check_id in ("C7.establishing", "C8.static", "C9.in_frame", "C10.click", "C10.cut", "N1.sync",
                             "N2.opening", "N2.caption_title", "N3.band", "N5.palette", "N6.result"):
                self.assertEqual(status(checks, check_id), "PASS", (video, check_id, self.detail(checks, check_id)))
        self.assertEqual(status(self.checks("tutorial"), "N2.chip"), "PASS")
        self.assertEqual(status(self.checks("redes"), "N7.no_chip"), "PASS")
        self.assertEqual(status(self.checks("redes"), "N9.vertical"), "PASS")
        self.assertNotIn("N9.vertical", {c["id"] for c in self.checks("tutorial")})

    # C7
    def screen_change_at(self, t=3.4):
        self.tl["tutorial"]["steps"][1]["events"][0]["screen_at"] = t

    def test_C7_new_screen_without_establishing_shot_fails(self):
        self.screen_change_at()
        checks = self.checks()
        self.assertEqual(status(checks, "C7.establishing"), "FAIL")
        self.assertIn("3.40s", self.detail(checks, "C7.establishing"))

    def test_C7_cut_to_establishing_shot_passes_and_long_one_fails(self):
        self.screen_change_at()
        cam = self.lay["tutorial"]["camera"]
        cam[3:4] = [{"t0": 1.9, "t1": 3.4, "scale": 2.0, "kind": "detail"},
                    {"t0": 3.4, "t1": 4.0, "scale": 1.0, "kind": "context", "reason": "establishing"},
                    {"t0": 4.0, "t1": 5.0, "scale": 2.0, "kind": "detail"}]
        checks = self.checks()
        self.assertEqual(status(checks, "C7.establishing"), "PASS", self.detail(checks, "C7.establishing"))
        self.assertEqual(status(checks, "C10.cut"), "PASS")
        cam[4]["t1"], cam[5]["t0"] = 4.6, 4.6
        self.assertEqual(status(self.checks(), "C7.establishing"), "FAIL")

    def test_C7_whole_video_zoomed_fails_from_the_first_step(self):
        cam = self.lay["tutorial"]["camera"]
        cam[1]["scale"], cam[1]["kind"] = 2.0, "detail"
        self.assertEqual(status(self.checks(), "C7.establishing"), "FAIL")

    # C8
    def test_C8_twelve_seconds_static_framing_fails(self):
        cam = self.lay["redes"]["camera"]
        cam[3:11] = [{"t0": 2.4, "t1": 8.0, "scale": 2.2, "kind": "detail", "x": -1590, "y": -300},
                     {"t0": 8.0, "t1": 14.0, "scale": 2.2, "kind": "detail", "x": -1590, "y": -300}]
        checks = self.checks("redes")
        self.assertEqual(status(checks, "C8.static"), "FAIL")
        self.assertIn("2.40s–14.00s", self.detail(checks, "C8.static"))

    def test_C8_limit_is_four_seconds_in_TUT_and_three_in_RED(self):
        # detail 1.9-5.0 = 3.1 s with the same framing
        self.assertEqual(status(self.checks(), "C8.static"), "PASS")
        self.tl["tutorial"]["type"] = "RED"
        self.assertEqual(status(self.checks(), "C8.static"), "FAIL")

    def test_C8_same_scale_other_center_is_not_static(self):
        cam = self.lay["redes"]["camera"]
        cam[3:11] = [{"t0": 2.4, "t1": 5.0, "scale": 2.2, "kind": "detail", "x": -1590, "y": -300},
                     {"t0": 5.0, "t1": 8.0, "scale": 2.2, "kind": "detail", "x": -1500, "y": -300},
                     {"t0": 8.0, "t1": 11.0, "scale": 2.2, "kind": "detail", "x": -1590, "y": -300},
                     {"t0": 11.0, "t1": 14.0, "scale": 2.2, "kind": "detail", "x": -1590, "y": -330}]
        self.assertEqual(status(self.checks("redes"), "C8.static"), "PASS")

    # C9
    def add_typing(self, rect, frame_box=None):
        ev = {"type": "type", "t": 4.0, "t_end": 4.6, "selector": "#c-apellido", "chars": 4, "secret": False,
              "box": {"x": 1300, "y": 400, "w": 200, "h": 60}, "point": {"x": 1400, "y": 430}}
        if frame_box:
            ev["frame_box"] = frame_box
        self.tl["redes"]["steps"][0]["events"].append(ev)
        self.lay["redes"]["items"].append({"kind": "active", "t0": 3.8, "t1": 4.8, "t": 4.0, "rect": rect,
                                           "step": "nuevo", "event": "type", "selector": "#c-apellido"})

    def test_C9_typing_Vera_in_a_field_outside_the_viewport_fails(self):
        self.add_typing([900, 600, 400, 100])  # cut at the right edge (1080)
        checks = self.checks("redes")
        self.assertEqual(status(checks, "C9.in_frame"), "FAIL")
        self.assertIn("#c-apellido", self.detail(checks, "C9.in_frame"))

    def test_C9_frame_box_with_label_must_be_in_frame(self):
        self.add_typing([200, 600, 400, 100], frame_box={"x": 1300, "y": 380, "w": 200, "h": 80})
        self.assertEqual(status(self.checks("redes"), "C9.in_frame"), "FAIL")
        self.tl["redes"]["steps"][0]["events"][-1]["frame_box"] = {"x": 800, "y": 380, "w": 150, "h": 80}
        self.assertEqual(status(self.checks("redes"), "C9.in_frame"), "PASS")

    def test_C9_label_cut_at_the_top_fails_in_16_9(self):
        item(self.lay["tutorial"], "active", "nuevo")["rect"] = [800, -20, 300, 80]
        self.assertEqual(status(self.checks(), "C9.in_frame"), "FAIL")

    # C10
    def test_C10_click_on_nothing_fails(self):
        self.lay["redes"]["camera"][7]["x"] = -1590  # click point (1600, 730) lands at x=1930
        checks = self.checks("redes")
        self.assertEqual(status(checks, "C10.click"), "FAIL")
        self.assertIn("#btn-guardar", self.detail(checks, "C10.click"))

    def test_C10_pan_right_after_a_screen_change_fails(self):
        self.tl["tutorial"]["steps"][0]["events"][0]["screen_at"] = 1.6  # move 1.4-1.9 crosses it
        self.assertEqual(status(self.checks(), "C10.cut"), "FAIL")

    # N1
    def test_N1_narration_ending_after_the_click_fails(self):
        step = self.tl["tutorial"]["steps"][0]
        step["narration"] = "Haz clic en Nuevo contacto para abrir el formulario."
        checks = self.checks()
        self.assertEqual(status(checks, "N1.sync"), "FAIL")
        self.assertIn("nuevo", self.detail(checks, "N1.sync"))

    def test_N1_caption_appearing_after_the_action_fails(self):
        item(self.lay["tutorial"], "caption", "nuevo")["t0"] = 1.6  # the form is already open
        self.assertEqual(status(self.checks(), "N1.sync"), "FAIL")

    def test_N1_explicit_instruction_end_is_used(self):
        self.tl["tutorial"]["steps"][0]["instruction_end"] = 2.5
        self.assertEqual(status(self.checks(), "N1.sync"), "FAIL")
        self.tl["tutorial"]["steps"][0]["instruction_end"] = 1.7
        self.assertEqual(status(self.checks(), "N1.sync"), "PASS")

    # N2 / N7
    def test_N2_chip_with_step_title_and_repeated_caption_fails(self):
        self.tl["tutorial"]["steps"][1]["title"] = "Guarda el contacto"
        chip = item(self.lay["tutorial"], "chip", "guardar")
        chip["text"] = "Paso 5 · Guarda el contacto"
        caption = item(self.lay["tutorial"], "caption", "guardar")
        caption["text"], caption["lines"] = "Haz clic en Guardar contacto", ["Haz clic en Guardar contacto"]
        checks = self.checks()
        self.assertEqual(status(checks, "N2.chip"), "FAIL")
        self.assertEqual(status(checks, "N2.caption_title"), "FAIL")
        chip["text"] = "Paso 5"  # title no longer shown: the caption repeats nothing
        checks = self.checks()
        self.assertEqual(status(checks, "N2.chip"), "PASS")
        self.assertEqual(status(checks, "N2.caption_title"), "PASS")

    def test_N2_chapter_chip_passes(self):
        item(self.lay["tutorial"], "chip", "guardar")["text"] = "Parte 2 · Paso 1"
        self.assertEqual(status(self.checks(), "N2.chip"), "PASS")

    def test_N2_opening_card_repeating_the_title_fails(self):
        self.lay["tutorial"]["items"][1]["text"] = "Aprende a crear un contacto"
        checks = self.checks()
        self.assertEqual(status(checks, "N2.opening"), "FAIL")
        self.assertIn("%", self.detail(checks, "N2.opening"))

    def test_N7_chip_in_RED_PRO_NOV_fails(self):
        self.lay["redes"]["items"].append({"kind": "chip", "t0": 1.5, "t1": 8.5, "rect": [60, 1300, 200, 60],
                                           "text": "Paso 3", "step": "nuevo", "opacity": 1.0})
        self.assertEqual(status(self.checks("redes"), "N7.no_chip"), "FAIL")
        self.tl["redes"]["type"] = "PRO"
        self.assertEqual(status(self.checks("redes"), "N7.no_chip"), "FAIL")
        self.assertNotIn("N2.chip", {c["id"] for c in self.checks("redes")})

    # N3
    def test_N3_caption_over_the_ui_viewport_fails(self):
        self.lay["tutorial"]["viewport"] = [0, 0, 1920, 1080]
        checks = self.checks()
        self.assertEqual(status(checks, "N3.band"), "FAIL")
        self.assertIn("interfaz", self.detail(checks, "N3.band"))

    def test_N3_caption_outside_the_band_fails_and_missing_band_warns(self):
        item(self.lay["tutorial"], "band")["rect"] = [0, 1000, 1920, 80]
        self.assertEqual(status(self.checks(), "N3.band"), "FAIL")
        self.lay["tutorial"]["items"] = [i for i in self.lay["tutorial"]["items"] if i["kind"] != "band"]
        self.assertEqual(status(self.checks(), "N3.band"), "WARN")

    # N5
    def test_N5_orange_chip_on_a_purple_brand_fails(self):
        item(self.lay["tutorial"], "chip", "nuevo")["color"] = "#f97316"
        checks = self.checks()
        self.assertEqual(status(checks, "N5.palette"), "FAIL")
        self.assertIn("#f97316", self.detail(checks, "N5.palette"))

    def test_N5_black_caption_boxes_fail(self):
        for black in ("#000000", "#0b0b12"):
            item(self.lay["tutorial"], "caption", "nuevo")["background"] = black
            self.assertEqual(status(self.checks(), "N5.palette"), "FAIL", black)

    def test_N5_colors_in_style_strings_are_checked(self):
        item(self.lay["tutorial"], "chip", "nuevo")["style"] = "bold|#ea580c|#ffffff|r18"
        self.assertEqual(status(self.checks(), "N5.palette"), "FAIL")

    def test_N5_brand_shades_and_neutrals_pass(self):
        for color in ("#4c1d95", "#a78bfa", "#ede9fe", "#ffffff", "#f3f4f6", "#6b7280"):
            item(self.lay["tutorial"], "highlight")["color"] = color
            self.assertEqual(status(self.checks(), "N5.palette"), "PASS", color)

    def test_N5_without_brand_warns(self):
        self.tut.pop("brand")
        self.assertEqual(status(self.checks(), "N5.palette"), "WARN")

    # N6
    def test_N6_missing_result_window_fails(self):
        self.lay["tutorial"]["items"] = [i for i in self.lay["tutorial"]["items"] if i["kind"] != "result"]
        self.assertEqual(status(self.checks(), "N6.result"), "FAIL")

    def test_N6_result_windows_are_exempt_from_C4(self):
        self.assertEqual(qa.c4_ranges(self.tl["tutorial"], self.lay["tutorial"]), [(1.0, 3.8), (4.8, 5.0)])
        self.assertEqual(qa.c4_ranges(self.tl["tutorial"], None), [(1.0, 3.8), (4.8, 5.0)])

    # N9
    def test_N9_vertical_frame_with_empty_bands_fails(self):
        self.lay["redes"]["camera"][3]["y"] = 288  # the source starts at y=288: band above the UI
        checks = self.checks("redes")
        self.assertEqual(status(checks, "N9.vertical"), "FAIL")
        self.assertIn("franja", self.detail(checks, "N9.vertical"))

    def test_N9_without_camera_offsets_warns(self):
        for seg in self.lay["redes"]["camera"]:
            seg.pop("x"), seg.pop("y")
        self.assertEqual(status(self.checks("redes"), "N9.vertical"), "WARN")


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
        layout = fixture("tutorial", "layout.json")
        times = qa.snapshot_times(self.tl["tutorial"], layout)
        self.assertEqual(times, sorted(times))
        self.assertIn(0.5, times)   # opening middle
        self.assertIn(1.2, times)   # establishing shot (context 1.0-1.4)
        self.assertIn(1.3, times)   # click nuevo - 0.2 s
        self.assertIn(3.1, times)   # click guardar - 0.2 s
        self.assertIn(4.3, times)   # result (toast) visible
        self.assertIn(4.45, times)  # highlight visible
        self.assertIn(5.5, times)   # closing middle
        self.assertNotIn(2.0, times)  # step middles only for steps without key events

    def test_snapshot_times_mid_typing_and_step_without_events(self):
        tl = self.tl["tutorial"]
        tl["steps"][0]["events"] = [{"type": "type", "t": 1.2, "t_end": 2.2, "selector": "#c-nombre", "box": None}]
        tl["steps"][1]["events"] = []
        times = qa.snapshot_times(tl)
        self.assertIn(1.7, times)   # mid-typing
        self.assertIn(4.0, times)   # middle of a step without key events

    def test_N8_red_closing_without_destination_fails(self):
        self.tl["redes"]["closing"].update(text="Mira el tutorial completo", narration="Mira el tutorial completo.")
        self.assertEqual(status(qa.check_timeline(self.tl["redes"]), "N8.destination"), "FAIL")
        self.tl["redes"]["closing"]["narration"] = "Míralo en nuestro canal de YouTube."
        self.assertEqual(status(qa.check_timeline(self.tl["redes"]), "N8.destination"), "PASS")
        self.assertNotIn("N8.destination", {c["id"] for c in qa.check_timeline(self.tl["tutorial"])})


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
        (self.pdir / "edit" / "redes").mkdir()
        (self.pdir / "hf-redes").mkdir()
        shutil.copy(FIXTURES / "redes" / "timeline.json", self.pdir / "edit" / "redes" / "timeline.json")
        shutil.copy(FIXTURES / "redes" / "layout.json", self.pdir / "hf-redes" / "layout.json")
        self.shots = mock.patch.object(qa, "take_snapshots", side_effect=lambda slug, video, times:
                                       [Path(f"at-{t:g}s.png") for t in times])
        self.snap = self.shots.start()
        self.addCleanup(self.shots.stop)

    def run_qa(self, video="tutorial", pre=False):
        out = io.StringIO()
        with redirect_stdout(out):
            ok = qa.qa("crm", video, pre=pre)
        return ok, out.getvalue()

    def test_passing_video_writes_report_and_lists_snapshots(self):
        ok, out = self.run_qa()
        report = json.loads((self.pdir / "qa" / "tutorial.json").read_text(encoding="utf-8"))
        self.assertTrue(ok, out)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["mode"], "full")
        self.assertEqual(failing(report["checks"]), [])
        for check_id in ("tech.resolution", "tech.duration", "tech.audio", "A1.loudness", "A1.true_peak",
                         "A2.silence", "A2.voice_gaps", "A2.closing_card", "C4.empty_frames", "O1.chip_overlap",
                         "O2.caption_overlap", "R2.result_clear", "T1.lines", "T2.font", "C1.context", "C5.cursor",
                         "L.captions", "snapshots", "C7.establishing", "C8.static", "C9.in_frame",
                         "C10.click", "C10.cut", "N1.sync", "N2.chip", "N2.opening", "N3.band", "N5.palette",
                         "N6.result"):
            self.assertEqual(status(report["checks"], check_id), "PASS", check_id)
        self.snap.assert_called_once_with("crm", "tutorial", qa.snapshot_times(
            fixture("tutorial", "timeline.json"), fixture("tutorial", "layout.json")))
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

    def test_pre_mode_needs_no_mp4_and_skips_media_checks(self):
        (self.pdir / "out" / "crm-tutorial.mp4").unlink()
        ok, out = self.run_qa(video=None, pre=True)
        self.assertTrue(ok, out)
        for vid in ("tutorial", "redes"):
            report = json.loads((self.pdir / "qa" / f"{vid}.json").read_text(encoding="utf-8"))
            self.assertEqual(report["mode"], "pre", vid)
            self.assertEqual(report["status"], "PASS", failing(report["checks"]))
            ids = {c["id"] for c in report["checks"]}
            media = {i for i in ids if i.startswith(("tech.", "A1.", "C4.")) or i == "A2.silence"}
            self.assertEqual(media, set(), vid)
            self.assertIn("C7.establishing", ids)
            self.assertEqual(status(report["checks"], "snapshots"), "PASS")
        self.assertEqual(self.snap.call_count, 2)
        self.assertIn("pre", out)

    def test_pre_mode_fails_on_layout_problems(self):
        layout = fixture("tutorial", "layout.json")
        layout["viewport"] = [0, 0, 1920, 1080]  # captions float over the UI (N3)
        (self.pdir / "hf-tutorial" / "layout.json").write_text(json.dumps(layout), encoding="utf-8")
        ok, _ = self.run_qa(pre=True)
        self.assertFalse(ok)
        report = json.loads((self.pdir / "qa" / "tutorial.json").read_text(encoding="utf-8"))
        self.assertEqual(status(report["checks"], "N3.band"), "FAIL")

    def test_all_videos_are_checked_without_video_filter(self):
        ok, out = self.run_qa(video=None)
        self.assertFalse(ok)  # redes has no outputs in this project
        self.assertTrue((self.pdir / "qa" / "tutorial.json").exists())
        self.assertTrue((self.pdir / "qa" / "redes.json").exists())
        self.assertIn("redes", out)


def ui(x, y, w=340, h=44):
    return {"box": {"x": x, "y": y, "w": w, "h": h}, "point": {"x": x + w / 2, "y": y + h / 2}}


class ProducerCheckerContractTest(unittest.TestCase):
    """edit.plan_video -> compose.plan -> qa on a synthetic capture shaped like the demo: producer and
    checker share one definition of N1 (instruction_end), N6 (result window and its C4 exemption) and C7."""

    # Capture times as the recorder logs them; screen_c = when the click showed the new screen.
    ACTIONS = {"viewport": [1920, 1080], "steps": [
        {"id": "login", "t0": 0.0, "t1": 4.6, "events": [
            {"type": "type", "t": 0.5, "t_end": 1.9, "chars": 16, "selector": "#email", **ui(790, 486)},
            {"type": "type", "t": 2.3, "t_end": 3.4, "chars": 10, "selector": "#password", **ui(790, 569)},
            {"type": "click", "t": 4.0, "selector": "#btn-login", "screen_c": 4.0, **ui(790, 637, 340, 42)}]},
        {"id": "nuevo", "t0": 4.6, "t1": 6.2, "events": [
            {"type": "click", "t": 5.4, "selector": "#btn-new", "screen_c": 5.4, **ui(1377, 109, 150, 42)}]},
        {"id": "datos", "t0": 6.2, "t1": 11.0, "events": [
            {"type": "type", "t": 6.5, "t_end": 7.9, "chars": 14, "selector": "#c-name", **ui(790, 445)},
            {"type": "type", "t": 8.3, "t_end": 9.9, "chars": 17, "selector": "#c-email", **ui(790, 528)}]},
        {"id": "guardar", "t0": 11.0, "t1": 14.5, "events": [
            {"type": "click", "t": 11.7, "selector": "#btn-save", "screen_c": 11.7, **ui(790, 678, 340, 42)},
            {"type": "result", "t": 12.0, "selector": "#toast", **ui(1722, 998, 166, 50)},
            {"type": "highlight", "t": 12.1, "selector": "#rows tr:first-child", **ui(392, 236, 1136, 50)}]}]}
    NARRATION = {"login": "Primero ingresa a DemoCRM con tu correo y tu contraseña.",
                 "nuevo": "Haz clic en Nuevo cliente. Se abre el formulario.",
                 "datos": "Completa el nombre y el correo de tu cliente nuevo.",
                 "guardar": "Haz clic en Guardar cliente. Aparece el aviso y tu cliente queda primero."}
    BRAND = {"primary": "#2563eb", "accent": "#2563eb", "background": "#1e3a8a", "surface": "#1e3a8a",
             "on_surface": "#ffffff", "text": "#ffffff"}

    def run_chain(self, vtype, fmt, ids):
        import compose
        import edit
        steps = [{"id": s, "number": i + 1, "title": s, "narration": self.NARRATION[s]} for i, s in enumerate(ids)]
        tut = {"title": "Cómo crear un cliente en DemoCRM", "product": "DemoCRM", "viewport": [1920, 1080],
               "brand": self.BRAND}
        video = {"id": vtype.lower(), "type": vtype, "format": fmt, "steps": steps,
                 "opening": {"narration": "¿Cliente nuevo?" if vtype == "RED" else "Aprendes a registrar clientes."},
                 "closing": {"narration": "Mira nuestro perfil.", "text": "Tutorial en el enlace del perfil"}}
        # Voice lengths as tts --offline estimates them (words / 2.6 s).
        durations = {s: max(1.5, len(self.NARRATION[s].split()) / 2.6) for s in ids}
        durations.update(opening=1.5, closing=1.5)
        timeline = edit.plan_video(tut, video, self.ACTIONS, [], durations)
        layout = compose.plan(timeline, self.BRAND)
        return timeline, layout, qa.check_layout(layout, timeline, tut)

    def assert_contract(self, timeline, layout, checks):
        for check_id in ("N1.sync", "N6.result", "C7.establishing"):
            self.assertEqual(status(checks, check_id), "PASS", [c for c in checks if c["id"] == check_id])
        # N1: edit writes the exact end it planned; qa reads that same number.
        for step in timeline["steps"]:
            self.assertAlmostEqual(step["instruction_end"], step["voice_start"] + step["instruction_duration"],
                                   places=2)
            self.assertEqual(qa.instruction_end(step), step["instruction_end"])
            if step["action_t"] is not None:
                self.assertLessEqual(step["instruction_end"], step["action_t"] + 0.3 + 1e-3)
        # N6: the toast is framed >= 0.8 s while edit keeps it on screen, and C4 skips its zoom in and out.
        toast = next(e for s in timeline["steps"] for e in s["events"] if e["type"] == "result")
        res = next(i for i in layout["items"] if i["kind"] == "result")
        self.assertGreaterEqual(min(res["t1"], toast["t_end"]) - max(res["t0"], toast["t"]), 0.8 - 1e-3)
        zoom_in = next(c for c in layout["camera"] if c["kind"] == "move" and abs(c["t1"] - res["t0"]) < 1e-3)
        self.assertLessEqual(res["exempt"][0], zoom_in["t0"])
        for a, b in qa.c4_ranges(timeline, layout):
            self.assertFalse(a < res["exempt"][1] and b > res["exempt"][0], (a, b, res["exempt"]))
        # C7: every screen (screen_start and each screen_at) opens with an establishing shot.
        starts = [timeline["screen_start"]] + [e["screen_at"] for s in timeline["steps"] for e in s["events"]
                                                if e.get("screen_at") and e["screen_at"] < timeline["screen_end"]]
        for ts in starts:
            shot = next((c for c in layout["camera"] if abs(c["t0"] - ts) < 1e-3), None)
            self.assertIsNotNone(shot, ts)
            self.assertEqual(shot.get("reason"), "establishing", (ts, shot))

    def test_tutorial_16_9(self):
        self.assert_contract(*self.run_chain("TUT", "16:9", ["login", "nuevo", "datos", "guardar"]))

    def test_redes_9_16(self):
        self.assert_contract(*self.run_chain("RED", "9:16", ["nuevo", "datos", "guardar"]))


if __name__ == "__main__":
    unittest.main()
