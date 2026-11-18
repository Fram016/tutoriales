"""compose.py: caption segmentation (T1/T3), camera plan (C1-C3), overlays (O1-O3, R2, R3, V1-V4) and layout.json.

Run: .venv/Scripts/python.exe -m unittest tests.test_compose -v
"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import compose  # noqa: E402

FIXTURES = ROOT / "templates" / "fixtures"
NBSP = "\u00a0"
STOP = {"el", "la", "los", "las", "un", "una", "unos", "unas", "lo", "al", "del", "de", "a", "en", "con",
        "por", "para", "sin", "sobre", "entre", "hacia", "hasta", "desde", "y", "e", "o", "u", "ni", "que",
        "pero", "si", "como"}


def fixture(video):
    return json.loads((FIXTURES / f"{video}.timeline.json").read_text(encoding="utf-8"))


BRAND = json.loads((FIXTURES / "brand.json").read_text(encoding="utf-8"))


def last_word(line):
    return line.replace(NBSP, " ").split()[-1].strip(".,;:!?¿¡\"'()…").lower()


def inside(rect, frame):
    x, y, w, h = rect
    fx, fy, fw, fh = frame
    return x >= fx - 0.5 and y >= fy - 0.5 and x + w <= fx + fw + 0.5 and y + h <= fy + fh + 0.5


def overlap(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def during(item, t0, t1):
    return item["t0"] < t1 and t0 < item["t1"]


class CaptionSegmentationTest(unittest.TestCase):
    def check_lines(self, captions, max_chars=42):
        for lines in captions:
            self.assertLessEqual(len(lines), 2, lines)
            for line in lines:
                self.assertLessEqual(len(line), max_chars, line)
                self.assertNotIn(last_word(line), STOP, f"línea termina en palabra funcional: {line!r}")

    def test_failing_example_con_el_correo(self):
        text = "Primero ingresamos a Nexo CRM con el correo y la contraseña de nuestra cuenta."
        caps = compose.segment_captions(text, "Nexo CRM")
        self.check_lines(caps)
        flat = [line for lines in caps for line in lines]
        self.assertFalse(any(line.endswith("con el") for line in flat), flat)
        self.assertEqual(" ".join(flat).replace(NBSP, " "), text)

    def test_failing_example_aviso_verde(self):
        text = ("Tocamos Guardar contacto. Sale el aviso verde y nuestro prospecto aparece primero "
                "en la lista, resaltado.")
        caps = compose.segment_captions(text, "Nexo CRM")
        self.check_lines(caps)
        flat = [line for lines in caps for line in lines]
        for a, b in zip(flat, flat[1:]):
            self.assertFalse(a.endswith("aviso") and b.startswith("verde"), flat)
        self.assertEqual(" ".join(flat), text)

    def test_sentence_end_starts_a_new_caption(self):
        caps = compose.segment_captions("Haz clic en Guardar contacto. Sale el aviso verde.", "Nexo CRM")
        self.assertEqual(caps, [["Haz clic en Guardar contacto."], ["Sale el aviso verde."]])

    def test_narrow_format_respects_its_line_width(self):
        text = "Escribe el nombre, el apellido y el correo con el que vas a contactar a la persona."
        caps = compose.segment_captions(text, "Nexo CRM", max_chars=28)
        self.check_lines(caps, 28)
        self.assertEqual(" ".join(line for lines in caps for line in lines), text)

    def test_product_is_never_split(self):
        text = "Para empezar abre la aplicación web de Nexo CRM desde el navegador de tu equipo."
        for width in (20, 28, 42):
            caps = compose.segment_captions(text, "Nexo CRM", max_chars=width)
            flat = [line for lines in caps for line in lines]
            self.assertTrue(any(f"Nexo{NBSP}CRM" in line for line in flat), (width, flat))
            self.assertFalse(any(line.endswith("Nexo") for line in flat), (width, flat))

    def test_protect_product_uses_non_breaking_spaces(self):
        self.assertEqual(compose.protect_product("Abre Nexo CRM hoy", "Nexo CRM"), f"Abre Nexo{NBSP}CRM hoy")
        self.assertEqual(compose.protect_product("Sin marca", None), "Sin marca")


class LayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layouts = {v: compose.plan(fixture(v), BRAND) for v in ("tutorial", "redes")}
        cls.htmls = {v: compose.build(fixture(v), BRAND)[0] for v in ("tutorial", "redes")}

    def items(self, video, kind):
        return [i for i in self.layouts[video]["items"] if i["kind"] == kind]

    def frame(self, video):
        w, h = self.layouts[video]["output"]
        return [0, 0, w, h]

    def test_schema(self):
        for video, lay in self.layouts.items():
            for key in ("output", "viewport", "cursor_px", "font_px", "camera", "items"):
                self.assertIn(key, lay)
            self.assertEqual(lay["cursor_px"], 48)
            self.assertGreaterEqual(lay["font_px"], 44)
            self.assertEqual(len(lay["viewport"]), 4)
            for seg in lay["camera"]:
                self.assertIn(seg["kind"], {"context", "detail", "move", "form"})
                self.assertLess(seg["t0"], seg["t1"])
            kinds = {"caption", "chip", "title", "card", "cursor", "active", "result", "highlight", "band",
                     "spotlight"}
            for item in lay["items"]:
                self.assertIn(item["kind"], kinds)
                self.assertEqual(len(item["rect"]), 4)
                self.assertLessEqual(item["t0"], item["t1"])
            json.dumps(lay)
        self.assertEqual(self.layouts["tutorial"]["output"], [1920, 1080])
        self.assertEqual(self.layouts["redes"]["output"], [1080, 1920])

    def test_camera_segments_are_contiguous_and_never_overlap(self):
        for video, lay in self.layouts.items():
            tl = fixture(video)
            cam = lay["camera"]
            self.assertAlmostEqual(cam[0]["t0"], tl["screen_start"], places=2)
            self.assertAlmostEqual(cam[-1]["t1"], tl["screen_end"], places=2)
            for a, b in zip(cam, cam[1:]):
                self.assertAlmostEqual(a["t1"], b["t0"], places=3, msg=video)
            for seg in cam:
                if seg["kind"] == "move":
                    self.assertGreaterEqual(seg["t1"] - seg["t0"], 0.399, (video, seg))
                    self.assertLessEqual(seg["t1"] - seg["t0"], 0.601, (video, seg))

    def test_camera_scale_ranges(self):
        # C1 revised (§Parte 5): detail 1.4-1.8x; N10 form shots 1.0 (base in 9:16) to 1.8x.
        for video, lay in self.layouts.items():
            base = lay["base_scale"]
            for seg in lay["camera"]:
                if seg["kind"] == "detail":
                    self.assertGreaterEqual(seg["scale"], 1.4 - 1e-6, (video, seg))
                    self.assertLessEqual(seg["scale"], 1.8 + 1e-6, (video, seg))
                if seg["kind"] == "form":
                    self.assertGreaterEqual(seg["scale"], max(1.0, base) - 1e-6, (video, seg))
                    self.assertLessEqual(seg["scale"], 1.8 + 1e-6, (video, seg))
                if seg["kind"] == "context":
                    self.assertAlmostEqual(seg["scale"], base, places=3)
                    self.assertLessEqual(seg["t1"] - seg["t0"], 1.0 + 1e-6, (video, seg))

    def test_targets_framed_500ms_before_and_never_left_behind(self):
        for video, lay in self.layouts.items():
            frame = self.frame(video)
            actives = self.items(video, "active")
            self.assertTrue(actives)
            for item in actives:
                self.assertTrue(inside(item["rect"], frame), (video, item))
                if item["event"] == "click":
                    start = item["t"] - 0.5
                    hold = [s for s in lay["camera"] if s["t0"] <= start + 1e-6 and s["t1"] >= item["t"] - 1e-6]
                    self.assertTrue(hold and hold[0]["kind"] != "move", (video, item))
            # The click on "Guardar" changes the screen: the next framing goes to the toast (result).
            result = self.items(video, "result")[0]
            self.assertTrue(inside(result["rect"], frame), result)

    def test_result_is_clean_and_in_detail(self):
        for video, lay in self.layouts.items():
            for item in self.items(video, "result"):
                t0, t1 = item["t0"], item["t0"] + 0.8
                self.assertGreaterEqual(item["t1"] - item["t0"], 0.8)
                seg = next(s for s in lay["camera"] if s["t0"] <= item["t0"] + 0.01 < s["t1"])
                self.assertEqual(seg["kind"], "detail", (video, seg))
                for other in self.items(video, "caption") + self.items(video, "cursor") + self.items(video, "chip"):
                    if during(other, t0, t1):
                        self.assertFalse(overlap(other["rect"], item["rect"]), (video, other, item))

    def test_cursor_is_hidden_over_or_beside_a_result(self):
        # The cursor stays on "Guardar", which is off-frame (or at its edge) once the camera is on the toast.
        for video, lay in self.layouts.items():
            result = self.items(video, "result")[0]
            self.assertTrue(any(a <= result["t0"] and b >= result["t0"] + 0.8 for a, b in lay["cursor_hidden"]),
                            (video, lay["cursor_hidden"]))
            self.assertFalse([c for c in self.items(video, "cursor") if during(c, result["t0"], result["t1"])])

    def test_captions_never_cover_the_active_element(self):
        for video in self.layouts:
            caps = self.items(video, "caption")
            for act in self.items(video, "active") + self.items(video, "highlight"):
                for cap in caps:
                    if during(cap, act["t0"], act["t1"]):
                        self.assertFalse(overlap(cap["rect"], act["rect"]), (video, cap["text"], act))

    def test_caption_rules(self):
        for video, lay in self.layouts.items():
            tl = fixture(video)
            steps = {s["id"]: s for s in tl["steps"]}
            caps = self.items(video, "caption")
            self.assertTrue(caps)
            spoken = {}
            for cap in caps:
                self.assertGreaterEqual(round(cap["t1"] - cap["t0"], 3), 1.2, cap)
                step = steps[cap["step"]]
                self.assertGreaterEqual(cap["t0"], step["start"] - 1e-6)
                self.assertLessEqual(cap["t1"], step["start"] + step["duration"] + 1e-6)
                self.assertLessEqual(len(cap["lines"]), 2)
                for line in cap["lines"]:
                    self.assertLessEqual(len(line), 42)
                    self.assertNotIn(last_word(line), STOP, line)
                spoken.setdefault(cap["step"], []).extend(cap["lines"])
            for sid, lines in spoken.items():
                self.assertEqual(" ".join(lines).replace(NBSP, " "), steps[sid]["narration"])
            for a, b in zip(caps, caps[1:]):
                self.assertLessEqual(a["t1"], b["t0"] + 1e-6)

    def test_one_style_and_size_for_chip_and_captions(self):
        for video, lay in self.layouts.items():
            self.assertGreaterEqual(lay["font_px"], 44)
            chips = self.items(video, "chip")
            self.assertEqual(bool(chips), lay["type"] == "TUT")      # N7: no step chip in RED
            for chip in chips:
                self.assertEqual(chip["opacity"], 1)
                self.assertGreaterEqual(chip["contrast"], 4.5)
            caps = self.items(video, "caption")
            self.assertEqual(len({c["style"] for c in caps + chips}), 1)
        styles = {i["style"] for lay in self.layouts.values() for i in lay["items"] if i["kind"] in ("caption", "chip")}
        self.assertEqual(len(styles), 1)

    def test_chip_sits_on_the_caption_block_not_on_the_app_header(self):
        for video, lay in self.layouts.items():
            for chip in self.items(video, "chip"):
                self.assertGreater(chip["rect"][1], lay["output"][1] * 0.5, chip)
        self.assertEqual(self.items("tutorial", "chip")[0]["text"], "Paso 3")     # N2: no step title

    def test_vertical_safe_zones_and_title(self):
        lay = self.layouts["redes"]
        top, bottom = 1920 * 0.15, 1920 * 0.80
        for item in self.items("redes", "caption") + self.items("redes", "chip") + self.items("redes", "title"):
            self.assertGreaterEqual(item["rect"][1], top - 0.5, item)
            self.assertLessEqual(item["rect"][1] + item["rect"][3], bottom + 0.5, item)
        for item in self.items("redes", "active") + self.items("redes", "result"):
            self.assertTrue(inside(item["rect"], lay["viewport"]), item)
            # V4 unless the target is at the very top of the app: N9 never shows bars above the source.
            if compose.frame_at(lay["camera"], item["t"])["y"] < 0:
                self.assertGreaterEqual(item["rect"][1], top - 0.5, item)
            self.assertLessEqual(item["rect"][1] + item["rect"][3], bottom + 0.5, item)
        for item in self.items("redes", "title") + self.items("tutorial", "title"):
            self.assertLessEqual(item["t1"], 3.0 + 1e-6)
        for seg in lay["camera"]:
            # Real reframe: the 1920x1080 source covers at least 70 % of the 1920 px height.
            self.assertGreaterEqual(1080 * seg["scale"], 0.7 * 1920, seg)

    def test_cursor_has_constant_output_size(self):
        for video in self.layouts:
            cursors = self.items(video, "cursor")
            self.assertTrue(cursors)
            self.assertEqual({c["rect"][3] for c in cursors}, {48})
            self.assertIn("calc(1 / var(--s))", self.htmls[video])

    def test_highlight_contrast(self):
        for video in self.layouts:
            hl = self.items(video, "highlight")
            self.assertEqual(len(hl), 1)
            self.assertGreaterEqual(hl[0]["contrast"], 3.0)

    def test_cards_open_and_close_with_unbreakable_product(self):
        for video in self.layouts:
            cards = [i for i in self.layouts[video]["items"] if i["kind"] in ("card", "title")]
            tl = fixture(video)
            self.assertEqual(cards[0]["t0"], 0)
            self.assertEqual(cards[0]["card"], "opening")
            self.assertAlmostEqual(cards[0]["t1"], tl["opening"]["duration"])
            self.assertAlmostEqual(cards[-1]["t1"], tl["total"])
            self.assertLessEqual(cards[-1]["t1"] - cards[-1]["t0"], 2.5 + 1e-6)
            for card in cards:
                for line in card["lines"]:
                    self.assertFalse(line.endswith("Nexo"), card)
                    self.assertNotIn(last_word(line), STOP, card)

    def test_promo_has_no_step_chip_and_long_tutorial_shows_part(self):
        promo = copy.deepcopy(fixture("tutorial"))
        promo["type"] = "PRO"
        self.assertFalse([i for i in compose.plan(promo, BRAND)["items"] if i["kind"] == "chip"])
        long = copy.deepcopy(fixture("tutorial"))
        for step in long["steps"]:
            step["chapter"] = 2
        chips = [i for i in compose.plan(long, BRAND)["items"] if i["kind"] == "chip"]
        self.assertTrue(chips[0]["text"].startswith("Parte 2 · Paso 1"), chips[0]["text"])

    def test_html_has_no_cross_fades_on_the_camera(self):
        html = self.htmls["tutorial"]
        self.assertNotIn('"#screen", {opacity', html)
        self.assertIn('ease: "power2.inOut"', html)


def navigation_timeline():
    """DemoCRM smoke: "+ Nuevo cliente" opens the form; the next step types into it ~4.5 s later."""
    def ev(kind, t, t_end, x, y, w=340, h=44):
        return {"type": kind, "t": t, "t_end": t_end, "selector": "#x", "box": {"x": x, "y": y, "w": w, "h": h},
                "point": {"x": x + w / 2, "y": y + h / 2}, "chars": 14, "secret": False}
    return {"video": "tutorial", "type": "TUT", "format": "16:9", "total": 20.0, "product": "DemoCRM",
            "title": "Crear un cliente", "opening": None, "requirements": None, "closing": None,
            "screen_start": 7.64, "screen_end": 18.195, "steps": [
                {"id": "nuevo", "number": 2, "title": "Abre el formulario", "narration": "Haz clic en Nuevo cliente.",
                 "start": 7.64, "duration": 4.55, "voice_start": 7.94, "voice_duration": 3.85,
                 "events": [ev("click", 8.24, 8.24, 1377.3, 109.1, 150.7, 42.4)]},
                {"id": "datos", "number": 3, "title": "Completa los datos", "narration": "Completa el nombre.",
                 "start": 12.19, "duration": 6.005, "voice_start": 13.07, "voice_duration": 3.85,
                 "events": [ev("type", 12.79, 14.077, 790, 445.4), ev("type", 14.677, 16.186, 790, 527.8)]}]}


class NavigationCameraTest(unittest.TestCase):
    def test_wide_shots_after_navigation_stay_within_1_s(self):
        # C1: consecutive camera time at the full-screen (base) scale, zoom-out move included; N10 form
        # shots (>= 1.0x, >= base in 9:16) are not wide shots.
        tl = navigation_timeline()
        for fmt in ("16:9", "9:16"):
            tl["format"] = fmt
            lay = compose.plan(tl, BRAND)
            cam, wide = lay["camera"], lay["base_scale"] + 0.05
            runs, start = [], None
            for seg in cam:
                if seg["scale"] < wide and start is None:
                    start = seg["t0"]
                elif seg["scale"] >= wide and start is not None:
                    runs.append(seg["t0"] - start)
                    start = None
            if start is not None:
                runs.append(cam[-1]["t1"] - start)
            with self.subTest(fmt=fmt):
                self.assertFalse([r for r in runs if r > 1.0 + 1e-6], cam)

    def test_detail_follows_the_click_to_the_new_screen(self):
        # After the click opens the form, the camera goes to the form (N10: two fields of one step, no
        # form_box in older captures) without a 1.0x look at a half-empty dimmed screen (C4), and it is
        # there 0.3 s before typing starts (C3).
        tl = navigation_timeline()
        cam = compose.plan(tl, BRAND)["camera"]
        after = [s for s in cam if s["t1"] > 8.24 + 1e-6 and s["t0"] < 12.79]
        self.assertFalse([s for s in after if s["kind"] == "context"], after)
        framed = next(s for s in cam if s["t0"] <= 12.79 - 0.3 + 1e-6 < s["t1"])
        self.assertEqual(framed["kind"], "form", cam)
        self.assertGreaterEqual(framed["scale"], 1.0)
        self.assertLessEqual(framed["scale"], 1.8)

    def test_camera_cuts_to_the_next_target_when_the_screen_changes(self):
        # edit marks when the click changed the screen (screen_at). Panning there crossed the empty part
        # of the new screen (C4: 75-95 % empty); a cut is no cross-fade (C2). C7: the cut lands on the
        # whole new screen for <= 1.0 s, then an ease-in-out zoom reaches the next target in detail.
        tl = navigation_timeline()
        tl["steps"][0]["events"][0]["screen_at"] = 8.35
        layout = compose.plan(tl, BRAND)
        cam = layout["camera"]
        before = next(s for s in cam if s["t0"] <= 8.24 < s["t1"])
        after = next(s for s in cam if s["t0"] <= 8.35 < s["t1"])
        self.assertEqual(before["kind"], "detail")
        self.assertEqual(after["kind"], "context", cam)
        self.assertEqual(after.get("reason"), "establishing")
        self.assertAlmostEqual(after["t0"], 8.35, places=3)
        self.assertLessEqual(after["t1"] - after["t0"], 1.0 + 1e-6)
        self.assertNotEqual((before["x"], before["y"]), (after["x"], after["y"]))
        self.assertEqual(cam[cam.index(after) + 1]["kind"], "move")
        self.assertFalse([s for s in cam if s["kind"] == "context" and s["t1"] > 8.24 and s is not after], cam)
        html = compose.build(tl, BRAND)[0]
        self.assertIn(f'tl.set("#cam", {{"--cx": {compose.num(after["x"])}, "--cy": {compose.num(after["y"])}, '
                      f'"--s": {compose.num(after["scale"])}}}, 8.35);', html)

    def test_cut_also_when_the_new_target_follows_the_click_closely(self):
        # "Guardar" closes the form 0.02 s after the click and the new row is highlighted 0.4 s later:
        # its 0.5 s lead starts before the change, but there is nothing to frame before the new screen.
        tl = navigation_timeline()
        click = tl["steps"][0]["events"][0]
        click["screen_at"] = 8.26
        row = dict(click, type="highlight", t=8.66, t_end=10.16, screen_at=None,
                   box={"x": 392, "y": 236, "w": 1136, "h": 50}, point=None)
        tl["steps"][0]["events"].append(row)
        cam = compose.plan(tl, BRAND)["camera"]
        self.assertFalse([s for s in cam if s["kind"] == "move" and s["t0"] < 8.66 < s["t1"] + 0.5], cam)
        after = next(s for s in cam if s["t0"] <= 8.26 < s["t1"])
        self.assertAlmostEqual(after["t0"], 8.26, places=3)
        self.assertAlmostEqual(after["scale"], next(s for s in cam if s["t0"] <= 8.66 < s["t1"])["scale"])


def toast_timeline(row_box):
    """v3 TUT 0:18: Guardar changes the screen, the toast (bottom right) opens it, then the new row is highlighted."""
    def ev(kind, t, t_end, box, sel):
        return {"type": kind, "t": t, "t_end": t_end, "selector": sel, "box": box,
                "point": {"x": box["x"] + box["w"] / 2, "y": box["y"] + box["h"] / 2}, "chars": 0, "secret": False}
    click = ev("click", 18.32, 18.32, {"x": 1300, "y": 900, "w": 150, "h": 44}, "#btn-save")
    click["screen_at"] = 18.423
    return {"video": "tutorial", "type": "TUT", "format": "16:9", "total": 26.0, "product": "DemoCRM",
            "title": "Crear un cliente", "opening": None, "requirements": None, "closing": None,
            "screen_start": 16.0, "screen_end": 23.0, "steps": [
                {"id": "guardar", "number": 4, "title": "Guarda", "narration": "Haz clic en Guardar.",
                 "start": 16.0, "duration": 7.0, "voice_start": 16.3, "voice_duration": 2.0, "events": [
                     click, ev("result", 18.423, 20.423, {"x": 1594, "y": 999, "w": 294, "h": 49}, "#toast"),
                     ev("highlight", 20.423, 21.923, row_box, "tr.new")]}]}


class LeaveToastTest(unittest.TestCase):
    """C10/C4: never pan from a toast across an empty screen to a distant target."""

    def test_cut_from_the_toast_to_a_distant_row(self):
        # v3 TUT 19.72-20.22: the pan from the toast (bottom right) to the new row (top) crossed the empty list.
        for fmt in ("16:9", "9:16"):
            tl = toast_timeline({"x": 392, "y": 236, "w": 1136, "h": 50})
            tl["format"] = fmt
            lay = compose.plan(tl, BRAND)
            cam, res = lay["camera"], next(i for i in lay["items"] if i["kind"] == "result")
            with self.subTest(fmt=fmt):
                self.assertFalse([s for s in cam if s["kind"] == "move" and s["t1"] > 18.423 + 1e-6], cam)
                toast = compose.frame_at(cam, 18.423)
                row = compose.frame_at(cam, 20.423 - 0.3)
                self.assertTrue(inside(mapped({"x": 1594, "y": 999, "w": 294, "h": 49}, toast), lay["viewport"]))
                self.assertTrue(inside(mapped({"x": 392, "y": 236, "w": 1136, "h": 50}, row), lay["viewport"])
                                or fmt == "9:16")
                self.assertNotEqual(toast, row)
                self.assertGreaterEqual(res["t1"] - res["t0"], compose.R2_CLEAN)   # R2/N6 untouched
                html = compose.build(tl, BRAND)[0]
                cut = next(s for s in cam if s["t0"] > 18.423 + 1e-6)
                self.assertIn(f'"--s": {compose.num(cut["scale"])}}}, {compose.num(cut["t0"])});', html)

    def test_pan_kept_to_a_target_next_to_the_toast(self):
        # A target already partly in the toast framing is in the same populated area: the ease-in-out pan stays.
        tl = toast_timeline({"x": 1500, "y": 930, "w": 380, "h": 50})
        cam = compose.plan(tl, BRAND)["camera"]
        self.assertTrue([s for s in cam if s["kind"] == "move" and s["t0"] > 18.423], cam)


def field(t, t_end, x, y, w=400, h=45, selector="#f", frame=True):
    ev = {"type": "type", "t": t, "t_end": t_end, "chars": 8, "selector": selector,
          "box": {"x": x, "y": y, "w": w, "h": h}, "point": {"x": x + w / 2, "y": y + h / 2}}
    if frame:
        ev["frame_box"] = {"x": x, "y": y - 22, "w": w, "h": h + 22}
    return ev


def viewport_rect(layout):
    return layout["viewport"]


def mapped(box, fr):
    return [box["x"] * fr["s"] + fr["x"], box["y"] * fr["s"] + fr["y"], box["w"] * fr["s"], box["h"] * fr["s"]]


def label_box(ev):
    """frame_box, or the box grown 32 px upward (older captures without frame_box)."""
    if ev.get("frame_box"):
        return ev["frame_box"]
    b = ev["box"]
    return {"x": b["x"], "y": b["y"] - 32, "w": b["w"], "h": b["h"] + 32}


def screen_changes(tl):
    return sorted(e["screen_at"] for s in tl["steps"] for e in s["events"] if e.get("screen_at") is not None)


class RoundTwoTest(unittest.TestCase):
    """reglas/reglas-video.md §Parte 4: C7-C10, N1-N3, N5-N7."""

    @classmethod
    def setUpClass(cls):
        cls.tls = {v: fixture(v) for v in ("tutorial", "redes")}
        cls.layouts = {v: compose.plan(cls.tls[v], BRAND) for v in cls.tls}
        cls.htmls = {v: compose.build(cls.tls[v], BRAND)[0] for v in cls.tls}

    def items(self, video, kind):
        return [i for i in self.layouts[video]["items"] if i["kind"] == kind]

    # C7: establishing shot on every new screen (but the one that opens on a toast: S1(a), cut to it).
    def test_establishing_shot_at_each_new_screen(self):
        for video, lay in self.layouts.items():
            tl = self.tls[video]
            cam = lay["camera"]
            starts = [tl["screen_start"]] + screen_changes(tl)
            self.assertEqual(len(starts), 3, starts)
            for t in starts[:2]:
                seg = next(s for s in cam if abs(s["t0"] - t) < 1e-3)
                with self.subTest(video=video, t=t):
                    self.assertEqual(seg["kind"], "context", cam)
                    self.assertEqual(seg.get("reason"), "establishing", seg)
                    self.assertAlmostEqual(seg["scale"], lay["base_scale"], places=3)
                    self.assertLessEqual(seg["t1"] - seg["t0"], 1.0 + 1e-6)
                    nxt = cam[cam.index(seg) + 1]
                    self.assertEqual(nxt["kind"], "move", nxt)
                    self.assertGreaterEqual(nxt["t1"] - nxt["t0"], 0.4 - 1e-6)
                    self.assertLessEqual(nxt["t1"] - nxt["t0"], 0.6 + 1e-6)
                    self.assertGreaterEqual(nxt["scale"], max(1.0, lay["base_scale"]) - 1e-6)
        # 16:9: the establishing shot shows the whole 1920x1080 screen inside the UI viewport.
        lay = self.layouts["tutorial"]
        seg = lay["camera"][0]
        vx, vy, vw, vh = lay["viewport"]
        self.assertTrue(inside(mapped({"x": 0, "y": 0, "w": 1920, "h": 1080},
                                      {"x": seg["x"], "y": seg["y"], "s": seg["scale"]}), lay["viewport"]))
        self.assertGreaterEqual(1080 * seg["scale"], vh - 1)

    # C8: no identical framing longer than 4 s (TUT) / 3 s (RED); N11 spotlight moves count as changes.
    def test_no_identical_framing_longer_than_the_type_limit(self):
        for video, lay in self.layouts.items():
            limit = 3.0 if lay["type"] == "RED" else 4.0
            for seg in lay["camera"]:
                if seg["kind"] in ("move", "form"):
                    continue      # form shots: RoundThreeTest.test_c8_counts_spotlight_moves
                if seg.get("from") and (seg["from"]["x"], seg["from"]["y"], seg["from"]["s"]) != (seg["x"], seg["y"], seg["scale"]):
                    self.assertLessEqual(abs(seg["scale"] - seg["from"]["s"]), 0.1 + 1e-6, seg)
                    continue      # a slow push-in: the framing keeps changing
                with self.subTest(video=video, seg=seg):
                    self.assertLessEqual(seg["t1"] - seg["t0"], limit + 1e-6)

    # C9: the whole frame_box (control + label) stays inside the UI viewport while typing.
    def assert_typing_framed(self, tl, msg):
        lay = compose.plan(tl, BRAND)
        for step in tl["steps"]:
            for ev in step["events"]:
                if ev["type"] not in ("type", "select"):
                    continue
                for t in (ev["t"] + 0.05, (ev["t"] + ev["t_end"]) / 2, ev["t_end"]):
                    fr = compose.frame_at(lay["camera"], t)
                    self.assertTrue(inside(mapped(label_box(ev), fr), lay["viewport"]),
                                    (msg, ev["selector"], t, fr, lay["viewport"]))
        return lay

    def test_frame_box_inside_framing_in_both_formats(self):
        for video in self.tls:
            self.assert_typing_framed(self.tls[video], video)

    def test_right_column_fields_are_not_cut(self):
        # RED: "Se cortan campos a la derecha (Ape, Carg, Telé), y se escribe Vera en un campo que no se ve".
        for fmt in ("16:9", "9:16"):
            tl = navigation_timeline()
            tl["format"] = fmt
            tl["steps"][1]["events"] = [
                field(12.79, 13.6, 301, 203, selector="#c-nombre"),
                field(14.05, 14.8, 723, 203, selector="#c-apellido", frame=False),
                field(15.25, 16.0, 723, 289, selector="#c-cargo"),
                field(16.45, 17.2, 1480, 375, selector="#c-telefono", frame=False)]
            self.assert_typing_framed(tl, fmt)

    def test_label_is_inside_the_framing_with_margin(self):
        # TUT: "la etiqueta Nombre queda cortada arriba".
        for video, lay in self.layouts.items():
            for act in self.items(video, "active"):
                if act["event"] != "type":
                    continue
                x, y, w, h = act["frame_rect"]
                vx, vy, vw, vh = lay["viewport"]
                self.assertGreaterEqual(y, vy + 8, act)
                self.assertLessEqual(y + h, vy + vh - 8, act)

    # C10: hard cut at screen_at, never a pan across the new screen.
    def test_hard_cut_at_screen_at(self):
        for video, lay in self.layouts.items():
            cam = lay["camera"]
            for t in screen_changes(self.tls[video]):
                with self.subTest(video=video, t=t):
                    self.assertFalse([s for s in cam if s["kind"] == "move" and s["t0"] < t < s["t1"]], cam)
                    before = compose.frame_at(cam, t - 0.01)
                    after = next(s for s in cam if abs(s["t0"] - t) < 1e-3)
                    self.assertNotEqual((round(before["x"]), round(before["y"]), round(before["s"], 3)),
                                        (round(after["x"]), round(after["y"]), round(after["scale"], 3)))
                    self.assertIn(f'"--s": {compose.num(after["scale"])}}}, {compose.num(t)});', self.htmls[video])

    def test_click_target_on_screen_when_clicking(self):
        for video, lay in self.layouts.items():
            for act in self.items(video, "active"):
                if act["event"] == "click":
                    self.assertTrue(inside(act["full_rect"], lay["viewport"]), act)

    # N2 / N7: chip text.
    def test_chip_shows_only_the_step_number_and_none_in_red(self):
        chips = self.items("tutorial", "chip")
        self.assertEqual([c["text"] for c in chips], ["Paso 3", "Paso 4", "Paso 5"])
        self.assertNotIn("Abre el formulario", self.htmls["tutorial"])
        self.assertFalse(self.items("redes", "chip"))
        self.assertNotIn('class="ov chip"', self.htmls["redes"])

    def test_opening_drops_a_paraphrase_of_the_title(self):
        lay = self.layouts["tutorial"]
        opening = [i for i in lay["items"] if i.get("card") == "opening"]
        self.assertEqual([i["kind"] for i in opening], ["title"], opening)
        self.assertEqual(opening[0]["text"].replace(NBSP, " "), "Cómo crear un contacto en Nexo CRM")
        self.assertNotIn("Aprende a crear", self.htmls["tutorial"])
        tl = copy.deepcopy(self.tls["tutorial"])
        tl["opening"]["text"] = "Para vendedores que registran su primer posible cliente"
        kept = [i for i in compose.plan(tl, BRAND)["items"] if i.get("card") == "opening"]
        self.assertEqual(sorted(i["kind"] for i in kept), ["card", "title"])
        self.assertTrue(compose.paraphrase("Aprende a crear un contacto", "Cómo crear un contacto en Nexo CRM"))
        self.assertFalse(compose.paraphrase("Para vendedores nuevos", "Cómo crear un contacto en Nexo CRM"))
        # RED keeps its hook as the opening ("El gancho del vertical funciona como apertura").
        hook = [i for i in self.layouts["redes"]["items"] if i.get("card") == "opening"]
        self.assertEqual([i["text"] for i in hook], ["¿Conociste a alguien en una feria?"])

    # N3 / N9: captions in a fixed band outside the UI.
    def test_caption_band_outside_the_ui_viewport(self):
        for video, lay in self.layouts.items():
            W, H = lay["output"]
            band = [b for b in self.items(video, "band")]
            self.assertEqual(len(band), 1, band)
            rect = band[0]["rect"]
            vp = lay["viewport"]
            self.assertFalse(overlap(rect, vp), (rect, vp))
            self.assertAlmostEqual(rect[1], vp[1] + vp[3], places=1)
            self.assertEqual(lay["band"], rect)
            self.assertGreaterEqual(rect[3], 150)
            for item in self.items(video, "caption") + self.items(video, "chip"):
                self.assertTrue(inside(item["rect"], rect), (video, item))
            if lay["format"] == "16:9":
                self.assertEqual(rect[1] + rect[3], H)
                self.assertGreaterEqual(rect[3], 170)
                self.assertLessEqual(rect[3], 200)
                chip = self.items(video, "chip")[0]["rect"]
                cap = self.items(video, "caption")[0]["rect"]
                self.assertLess(chip[0] + chip[2], cap[0] + 1)
            else:
                self.assertEqual(vp[1], 0)
                self.assertGreaterEqual(vp[3], 0.70 * H)
                self.assertLessEqual(vp[3], 0.72 * H)
                self.assertLessEqual(rect[1] + rect[3], 0.80 * H + 0.5)
        self.assertIn('id="band"', self.htmls["tutorial"])

    def test_vertical_layout_is_stable_without_bands_inside_the_ui(self):
        # N9: the 1920x1080 source always covers the whole UI viewport (no moving bars).
        lay = self.layouts["redes"]
        vx, vy, vw, vh = lay["viewport"]
        for seg in lay["camera"]:
            for fr in ([seg.get("from")] if seg.get("from") else []) + [{"x": seg["x"], "y": seg["y"], "s": seg["scale"]}]:
                src = mapped({"x": 0, "y": 0, "w": 1920, "h": 1080}, fr)
                self.assertLessEqual(src[0], vx + 0.5, seg)
                self.assertLessEqual(src[1], vy + 0.5, seg)
                self.assertGreaterEqual(src[0] + src[2], vx + vw - 0.5, seg)
                self.assertGreaterEqual(src[1] + src[3], vy + vh - 0.5, seg)

    # N1: captions follow the voice; they never start after the action they describe.
    def test_captions_start_with_the_voice(self):
        for video, lay in self.layouts.items():
            for step in self.tls[video]["steps"]:
                caps = [c for c in self.items(video, "caption") if c["step"] == step["id"]]
                self.assertAlmostEqual(caps[0]["t0"], max(step["voice_start"], step["start"]), places=2)
                first = min(e["t"] for e in step["events"])
                self.assertLessEqual(caps[0]["t0"], first, (video, step["id"]))

    # N5: brand palette only.
    def test_overlays_use_only_the_brand_palette(self):
        brand_colors = {compose._hex(compose._rgb(c)) for c in (BRAND["primary"], BRAND["background"], BRAND["text"])}
        for video, lay in self.layouts.items():
            pal = lay["palette"]
            self.assertEqual(pal["accent"], pal["primary"])
            self.assertEqual(pal["surface"], compose._hex(compose._rgb(BRAND["background"])))
            allowed = set(pal.values())
            self.assertTrue(brand_colors <= allowed | {"#ffffff"})
            self.assertNotIn("#000000", allowed)
            for item in lay["items"]:
                if item["kind"] in ("active", "result"):
                    continue
                self.assertIn("color", item, item)
                self.assertIn(item["color"], allowed, item)
            # Every palette color is the brand primary/background/text, white, or the primary within its hue.
            hue = lambda c: __import__("colorsys").rgb_to_hls(*compose._rgb(c))[0]
            for name, color in pal.items():
                if color in brand_colors | {"#ffffff"}:
                    continue
                self.assertAlmostEqual(hue(color), hue(BRAND["primary"]), places=2, msg=(name, color))
            self.assertGreaterEqual(compose.contrast(pal["chip"], pal["chip_text"]), 4.5)
            self.assertGreaterEqual(compose.contrast(pal["on_surface"], pal["surface"]), 4.5)
            self.assertGreaterEqual(compose.contrast(pal["highlight"], "#ffffff"), 3.0)
            for bad in ("#0b0b12", "#facc15", "#000000", "#000;"):
                self.assertNotIn(bad, self.htmls[video].lower())

    # N6: after the save click the toast is framed, clean, then the highlighted row.
    def test_toast_then_highlighted_row(self):
        for video, lay in self.layouts.items():
            res = self.items(video, "result")[0]
            hl = self.items(video, "highlight")[0]
            self.assertGreaterEqual(res["t1"] - res["t0"], 0.8)
            self.assertLessEqual(res["t1"], hl["t0"] + 1e-6)
            self.assertTrue(inside(res["rect"], lay["viewport"]), res)
            for t in (res["t0"], res["t0"] + 0.8):
                fr = compose.frame_at(lay["camera"], t)
                self.assertTrue(inside(mapped({"x": 1594, "y": 999, "w": 294, "h": 49}, fr), lay["viewport"]), (video, t))
            self.assertTrue(any(a <= res["t0"] and b >= res["t0"] + 0.8 for a, b in lay["cursor_hidden"]))


def spotlights(layout):
    return [i for i in layout["items"] if i["kind"] == "spotlight"]


def form_field(t, t_end, x, y, selector, w=400, h=45):
    ev = field(t, t_end, x, y, w, h, selector)
    ev["form_box"] = dict(FORM)
    return ev


FORM = {"x": 273, "y": 152, "w": 878, "h": 585}


class RoundThreeTest(unittest.TestCase):
    """reglas/reglas-video.md §Parte 5: C1 revised, N10-N12; reglas-ronda3 S1(a)."""

    @classmethod
    def setUpClass(cls):
        cls.tls = {v: fixture(v) for v in ("tutorial", "redes")}
        cls.layouts = {v: compose.plan(cls.tls[v], BRAND) for v in cls.tls}
        cls.htmls = {v: compose.build(cls.tls[v], BRAND)[0] for v in cls.tls}

    def items(self, video, kind):
        return [i for i in self.layouts[video]["items"] if i["kind"] == kind]

    def events(self, video, kinds):
        return [e for s in self.tls[video]["steps"] for e in s["events"] if e["type"] in kinds]

    # C1 revised: buttons, toasts and rows framed at 1.4-1.8x (was 1.8-2.5x).
    def test_detail_zoom_is_1_4_to_1_8(self):
        self.assertEqual((compose.DETAIL_MIN, compose.DETAIL_MAX), (1.4, 1.8))
        for video, lay in self.layouts.items():
            click = self.events(video, {"click"})[0]          # "+ Nuevo contacto", outside any form
            self.assertNotIn("form_box", click)
            for ev in (click, *self.events(video, {"result", "highlight"})):
                s = compose.frame_at(lay["camera"], ev["t"] + (0.5 if ev["type"] == "highlight" else 0))["s"]
                with self.subTest(video=video, ev=ev["type"]):
                    self.assertGreaterEqual(s, 1.4 - 1e-6)
                    self.assertLessEqual(s, 1.8 + 1e-6)

    # N10: one form framing for every action inside the form; the camera does not move per field.
    def test_form_shot_is_one_framing_for_the_whole_form(self):
        for video, lay in self.layouts.items():
            inside_form = [e for e in self.events(video, {"type", "click", "focus"}) if e.get("form_box")]
            self.assertEqual(len(inside_form), 5)
            frames = {(round(f["x"], 1), round(f["y"], 1), round(f["s"], 3))
                      for e in inside_form for t in (e["t"] - 0.3, e["t"], e.get("t_end") or e["t"])
                      for f in [compose.frame_at(lay["camera"], t)]}
            pushes = [s for s in lay["camera"] if s["kind"] == "form" and s.get("push")]
            if not pushes:
                self.assertEqual(len(frames), 1, (video, frames))
            forms = [s for s in lay["camera"] if s["kind"] == "form"]
            self.assertTrue(forms, lay["camera"])
            self.assertFalse([s for s in lay["camera"] if s["kind"] == "move"
                              and inside_form[0]["t"] < s["t0"] < inside_form[-1]["t"]], video)
            for seg in forms:
                self.assertEqual(seg["form_box"], FORM)
            s = forms[0]["scale"]
            if lay["format"] == "16:9":
                self.assertGreaterEqual(s, 1.1)
                self.assertLessEqual(s, 1.5)
                # The whole card (fields and buttons) is inside the UI viewport.
                fr = {"x": forms[0]["x"], "y": forms[0]["y"], "s": s}
                self.assertTrue(inside(mapped(FORM, fr), lay["viewport"]), (fr, mapped(FORM, fr)))
            else:
                self.assertAlmostEqual(s, lay["base_scale"], places=3)     # N12: width-fit, never below base

    def test_inferred_form_box_for_older_captures(self):
        # No form_box (v3 captures): the step's consecutive fields are one form, their frame boxes + 24 px.
        lay = compose.plan(navigation_timeline(), BRAND)
        forms = [s for s in lay["camera"] if s["kind"] == "form"]
        self.assertEqual(len(forms), 1, lay["camera"])
        self.assertEqual(forms[0]["form_box"], {"x": 766, "y": 389.4, "w": 388, "h": 206.4})
        self.assertEqual(len(spotlights(lay)), 2)

    def test_tall_form_splits_into_the_fewest_top_to_bottom_framings(self):
        # 16:9: a form taller than the viewport at 1.0x is cut in two framings, never below 1.0x.
        tl = navigation_timeline()
        tall = {"x": 273, "y": 20, "w": 878, "h": 1050}
        evs = [form_field(12.79 + 0.9 * k, 13.39 + 0.9 * k, 301 + 422 * (k % 2), 60 + 120 * k, f"#f{k}")
               for k in range(8)]
        for ev in evs:
            ev["form_box"] = dict(tall)
        tl["steps"][1]["events"] = evs
        tl["steps"][1]["duration"] = 9.0
        tl["screen_end"] = tl["total"] = 21.2
        lay = compose.plan(tl, BRAND)
        framings = []
        for ev in evs:
            fr = compose.frame_at(lay["camera"], (ev["t"] + ev["t_end"]) / 2)
            self.assertGreaterEqual(fr["s"], 1.0 - 1e-6)
            self.assertTrue(inside(mapped(label_box(ev), fr), lay["viewport"]), (ev["selector"], fr))
            key = (round(fr["x"]), round(fr["y"]), round(fr["s"], 3))
            if not framings or framings[-1] != key:
                framings.append(key)
        self.assertEqual(len(framings), 2, framings)
        self.assertGreater(framings[0][1], framings[1][1])      # top part first, then the bottom part

    # N11: brand outline + soft dim on the active field, moving 250-400 ms ease-in-out between fields.
    def test_spotlight_items_follow_the_active_field(self):
        for video, lay in self.layouts.items():
            spots = spotlights(lay)
            self.assertEqual([s["selector"] for s in spots], ["#c-nombre", "#c-apellido", "#c-email", "#btn-guardar"])
            pal = lay["palette"]
            for a, b in zip(spots, spots[1:]):
                self.assertAlmostEqual(a["t1"], b["move"][0], places=3)
                self.assertAlmostEqual(b["t0"], b["move"][1], places=3)
                self.assertGreaterEqual(b["move"][1] - b["move"][0], 0.25 - 1e-6)
                self.assertLessEqual(b["move"][1] - b["move"][0], 0.4 + 1e-6)
            evs = {e["selector"]: e for e in self.events(video, {"type", "click"}) if e.get("form_box")}
            for spot in spots:
                ev = evs[spot["selector"]]
                self.assertLessEqual(spot["t0"], ev["t"] + 1e-6, spot)       # on the field before acting
                self.assertGreaterEqual(spot["t1"], ev.get("t_end") or ev["t"], spot)
                self.assertEqual(spot["color"], pal["highlight"])
                self.assertEqual(spot["dim_color"], pal["background"])
                self.assertGreater(spot["dim"], 0)
                self.assertLessEqual(spot["dim"], 0.25)
                fr = compose.frame_at(lay["camera"], spot["t0"])
                self.assertEqual(spot["rect"], [round(v, 1) for v in mapped(compose.label_box(ev), fr)])
                self.assertTrue(inside(spot["rect"], lay["viewport"]), spot)
            # Seek-safe: one element inside the camera driven by the GSAP timeline only.
            html = self.htmls[video]
            self.assertIn('class="spot"', html)
            self.assertIn('fill-opacity="0.22" mask="url(#spot-0-mask)"', html)
            self.assertRegex(html, r'tl\.to\("\.spot-0-box", \{attr: \{x: [^}]*\}, duration: 0\.\d+, ease: "power2\.inOut"\}')
            self.assertNotRegex(html, r'"#spot-\d+", \{(left|top):')
            self.assertLess(html.index('class="spot"'), html.index('id="cursor-layer"'))

    def test_c8_counts_spotlight_moves(self):
        # The form shot may outlast the C8 limit: spotlight moves (or a slow push) break it into runs <= limit.
        for video, lay in self.layouts.items():
            limit = 3.0 if lay["type"] == "RED" else 4.0
            moves = [tuple(s["move"]) for s in spotlights(lay) if s.get("move")]
            for seg in lay["camera"]:
                if seg["kind"] != "form" or seg.get("push"):
                    continue
                runs = compose.subtract([(seg["t0"], seg["t1"])], moves)
                with self.subTest(video=video, seg=seg):
                    self.assertFalse([r for r in runs if r[1] - r[0] > limit + 1e-6], (runs, moves))
            self.assertGreater(sum(s["t1"] - s["t0"] for s in lay["camera"] if s["kind"] == "form"), limit)
        self.assertEqual(compose.static_runs(0.0, 10.0, [(3.0, 3.3), (6.0, 6.3)]),
                         [(0.0, 3.0), (3.3, 6.0), (6.3, 10.0)])

    # N12: in 9:16 the form is framed across its whole width: the right column is never cut.
    def test_vertical_form_fits_the_width(self):
        lay = self.layouts["redes"]
        vx, vy, vw, vh = lay["viewport"]
        for ev in self.events("redes", {"type", "click"}):
            if not ev.get("form_box"):
                continue
            for t in (ev["t"], ev.get("t_end") or ev["t"]):
                fr = compose.frame_at(lay["camera"], t)
                x, y, w, h = mapped(compose.label_box(ev), fr)
                with self.subTest(sel=ev["selector"], t=t):
                    self.assertGreaterEqual(x, vx + 8)
                    self.assertLessEqual(x + w, vx + vw - 8)
                    self.assertTrue(inside([x, y, w, h], lay["viewport"]))
        # Both columns of the form (Nombre/Apellido, Empresa/Cargo, Correo/Teléfono) whole at once.
        fr = compose.frame_at(lay["camera"], self.events("redes", {"type"})[0]["t"])
        both = {"x": 301, "y": 181, "w": 822, "h": 238}
        self.assertTrue(inside(mapped(both, fr), lay["viewport"]), mapped(both, fr))

    # S1(a): a click that changes the screen to a toast cuts straight to the toast framing.
    def test_cut_to_the_toast_at_screen_at(self):
        for video, lay in self.layouts.items():
            cam = lay["camera"]
            at = screen_changes(self.tls[video])[-1]
            res = self.items(video, "result")[0]
            seg = next(s for s in cam if abs(s["t0"] - at) < 1e-3)
            self.assertEqual(seg["kind"], "detail", cam)
            toast = {"x": 1594, "y": 999, "w": 294, "h": 49}
            fr = {"x": seg["x"], "y": seg["y"], "s": seg["scale"]}
            self.assertTrue(inside(mapped(toast, fr), lay["viewport"]), (video, seg))
            self.assertFalse([s for s in cam if at - 1e-3 <= s["t0"] < res["t0"] and s["kind"] in ("move", "context")], cam)
            self.assertLessEqual(res["exempt"][0], at + 1e-3)
            self.assertIn(f'"--s": {compose.num(seg["scale"])}}}, {compose.num(at)});', self.htmls[video])


POPUP_SPEC = {"size": [420, 640], "dpr": 2, "anchor": "top-right", "file": "surface-popup.mp4", "windows": [[4.0, 10.0]]}
PANEL = {"x": 1484, "y": 54, "w": 420, "h": 640}
AREA = {"x": 1484, "y": 8, "w": 420, "h": 686}     # toolbar strip + panel


def surface_timeline(fmt="16:9", vtype="TUT"):
    """Perseo XML S5: the popup opens from the toolbar icon, a button is clicked inside it, the popup shows its
    progress, closes, then the page is clicked. Surface boxes are in popup CSS px (recorder)."""
    tl = copy.deepcopy(fixture("tutorial"))
    tl.update({"type": vtype, "format": fmt, "output": [1920, 1080] if fmt == "16:9" else [1080, 1920],
               "screen_start": 3.0, "screen_end": 12.0, "total": 14.5,
               "surfaces": {"popup": copy.deepcopy(POPUP_SPEC)}})
    tl["closing"].update({"start": 12.0, "voice_start": 12.1})
    boton = {"x": 40, "y": 300, "w": 340, "h": 44}
    tl["steps"] = [
        {"id": "abrir", "number": 1, "chapter": None, "narration": "Haz clic en el icono y luego en Descargar.",
         "start": 3.0, "duration": 6.0, "voice_start": 3.2, "voice_duration": 2.5, "events": [
             {"type": "open", "t": 4.0, "t_end": 4.0, "surface": "popup"},
             {"type": "click", "t": 5.5, "t_end": 5.5, "surface": "popup", "selector": "#boton4", "box": boton,
              "point": {"x": 210, "y": 322}, "frame_box": boton, "form_box": {"x": 0, "y": 0, "w": 420, "h": 640}},
             {"type": "result", "t": 7.0, "t_end": 8.5, "surface": "popup", "selector": "#estado",
              "box": {"x": 40, "y": 360, "w": 340, "h": 30}, "point": {"x": 210, "y": 375}}]},
        {"id": "cerrar", "number": 2, "chapter": None, "narration": "Cierra el panel y haz clic en Consultar.",
         "start": 9.0, "duration": 3.0, "voice_start": 9.1, "voice_duration": 1.8, "events": [
             {"type": "close", "t": 10.0, "t_end": 10.0, "surface": "popup"},
             {"type": "click", "t": 11.0, "t_end": 11.0, "selector": "#consultar",
              "box": {"x": 200, "y": 500, "w": 150, "h": 42}, "point": {"x": 275, "y": 521}}]}]
    return tl


class SurfaceComposeTest(unittest.TestCase):
    """perseo-xml S5 "se debe ver la interfaz de la extension": the popup is a floating panel under a toolbar
    strip, shown only while open; its events are mapped into source px so camera, cursor and spotlight follow."""

    @classmethod
    def setUpClass(cls):
        cls.tl = surface_timeline()
        cls.layout = compose.plan(cls.tl, BRAND)
        cls.html = compose.build(cls.tl, BRAND)[0]

    def items(self, kind, layout=None):
        return [i for i in (layout or self.layout)["items"] if i["kind"] == kind]

    def test_geometry_anchored_under_the_toolbar(self):
        geo = compose.surface_geometry({"size": [420, 640], "anchor": "top-right"})
        self.assertEqual(geo["panel"], PANEL)
        self.assertEqual(geo["toolbar"], {"x": 1848, "y": 8, "w": 56, "h": 40})
        self.assertEqual(geo["icon"], {"x": 1862, "y": 14, "w": 28, "h": 28})
        self.assertEqual(geo["area"], AREA)
        left = compose.surface_geometry({"size": [420, 640], "anchor": "top-left"})
        self.assertEqual((left["panel"]["x"], left["toolbar"]["x"]), (16, 16))

    def test_panel_only_while_open(self):
        panels = self.items("surface")
        self.assertEqual(len(panels), 1)
        self.assertEqual((panels[0]["t0"], panels[0]["t1"], panels[0]["name"]), (4.0, 10.0, "popup"))
        self.assertEqual(panels[0]["box"], PANEL)
        self.assertIn('tl.set("#surface-popup", {opacity: 1}, 4);', self.html)
        self.assertIn('tl.set("#surface-popup", {opacity: 0}, 10);', self.html)
        self.assertIn('src="assets/surface-popup.mp4"', self.html)
        bar = self.items("toolbar")
        self.assertEqual(len(bar), 1)
        self.assertLess(bar[0]["t0"], 4.0 - 0.8)             # the icon is there before the cursor travels to it
        self.assertGreaterEqual(bar[0]["t1"], 10.0)

    def test_surface_click_is_mapped_into_the_panel(self):
        active = next(i for i in self.items("active") if i["selector"] == "#boton4")
        fr = compose.frame_at(self.layout["camera"], 5.5)
        self.assertEqual(active["full_rect"], compose.rnd(compose.Stage.map(
            {"x": 1524, "y": 354, "w": 340, "h": 44}, fr)))
        panel = compose.Stage.map(PANEL, fr)
        cursor = next(i for i in self.items("cursor") if i["t0"] == 5.5)
        self.assertTrue(inside(cursor["rect"][:2] + [1, 1], panel), (cursor, panel))
        self.assertTrue(inside(active["rect"], panel))

    def test_camera_frames_the_whole_panel_as_a_form(self):
        seg = next(s for s in self.layout["camera"] if s["t0"] <= 5.5 < s["t1"])
        self.assertEqual(seg["kind"], "form")
        self.assertEqual(seg["form_box"], AREA)
        fr = {"x": seg["x"], "y": seg["y"], "s": seg["scale"]}
        self.assertTrue(inside(compose.Stage.map(AREA, fr), self.layout["viewport"]))
        self.assertGreaterEqual(seg["scale"], 1.0)
        self.assertLessEqual(seg["scale"], 1.5)

    def test_open_clicks_the_toolbar_icon(self):
        cursor = next(i for i in self.items("cursor") if i["t0"] == 4.0)
        fr = compose.frame_at(self.layout["camera"], 4.0)
        self.assertEqual(cursor["rect"][:2], [round(1876 * fr["s"] + fr["x"], 1), round(28 * fr["s"] + fr["y"], 1)])
        self.assertIn(4.0, [i["t"] for i in self.items("active") if i["selector"] == "popup:icon"])

    def test_spotlight_and_result_on_surface_targets(self):
        spot = next(i for i in self.items("spotlight") if i["selector"] == "#boton4")
        self.assertEqual(spot["box"], {"x": 1524, "y": 354, "w": 340, "h": 44})
        result = self.items("result")[0]
        fr = compose.frame_at(self.layout["camera"], result["t0"])
        self.assertTrue(inside(result["full_rect"], compose.Stage.map(PANEL, fr)))

    def test_events_after_close_stay_on_the_page(self):
        active = next(i for i in self.items("active") if i["selector"] == "#consultar")
        fr = compose.frame_at(self.layout["camera"], 11.0)
        self.assertEqual(active["full_rect"], compose.rnd(compose.Stage.map({"x": 200, "y": 500, "w": 150, "h": 42}, fr)))

    def test_vertical_keeps_the_panel_inside_the_ui(self):
        lay = compose.plan(surface_timeline("9:16", "RED"), BRAND)
        fr = compose.frame_at(lay["camera"], 5.5)
        self.assertTrue(inside(compose.Stage.map(PANEL, fr), lay["viewport"]), fr)

    def test_without_surfaces_nothing_is_drawn(self):
        # PRESERVE: a timeline without surfaces keeps its layout and has no panel markup.
        tl = fixture("tutorial")
        self.assertEqual(compose.plan(copy.deepcopy(tl), BRAND), compose.plan(tl, BRAND))
        html = compose.build(tl, BRAND)[0]
        self.assertNotIn("surface-", html)
        self.assertFalse([i for i in compose.plan(tl, BRAND)["items"] if i["kind"] in ("surface", "toolbar")])


class ParallelRenderTest(unittest.TestCase):
    def test_workers_are_split_across_videos(self):
        # S1(f): 2 Chrome workers per video measured fastest (6+6 on 12 threads oversubscribed: 276-296 s).
        import render
        self.assertEqual(render.workers_per_video(2, 12), 2)
        self.assertEqual(render.workers_per_video(3, 2), 1)
        self.assertEqual(render.workers_per_video(1, 8), 2)

    def test_final_render_defaults(self):
        # S1(f): looks + PNG frame extraction (sharp UI text) at 25 fps; --quality and --fps stay overridable.
        import tempfile
        import render
        self.assertEqual((render.QUALITY, render.FRAME_FORMAT, render.FPS), ("looks", "png", 25))
        calls = []

        def fake_hf(*args, **kwargs):
            calls.append([str(a) for a in args])
            Path(args[args.index("-o") + 1]).write_bytes(b"")

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "hf-tutorial"
            src.mkdir()
            (src / "layout.json").write_text('{"format": "16:9", "total": 1.0}', encoding="utf-8")
            hf, verify = render.hyperframes, render.verify
            render.hyperframes, render.verify = fake_hf, lambda *a: {"width": 1920, "height": 1080, "duration": 1.0,
                                                                     "video": "h264", "audio": "aac"}
            try:
                render.render_project(src, Path(tmp) / "a.mp4", render.QUALITY, 2)
                render.render_project(src, Path(tmp) / "b.mp4", "delivery", 2, fps=30)
            finally:
                render.hyperframes, render.verify = hf, verify
        first, second = calls
        for flag, value in (("--quality", "looks"), ("--video-frame-format", "png"), ("--fps", "25"),
                            ("--workers", "2"), ("--page-motion-blur", "off")):
            self.assertEqual(first[first.index(flag) + 1], value, first)
        self.assertEqual((second[second.index("--quality") + 1], second[second.index("--fps") + 1]), ("delivery", "30"))

    def test_renders_run_concurrently(self):
        import threading
        import time
        import render
        active, peak, lock = [0], [0], threading.Lock()

        def fake(src, out, quality, workers=None):
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            time.sleep(0.2)
            with lock:
                active[0] -= 1
            return {"path": str(out), "workers": workers}

        jobs = [(Path(f"hf-{v}"), Path(f"{v}.mp4")) for v in ("tutorial", "redes")]
        out = render.render_many(jobs, "draft", runner=fake, cores=8)
        self.assertEqual(peak[0], 2)
        self.assertEqual([r["workers"] for r in out.values()], [2, 2])
        self.assertEqual(list(out), ["tutorial", "redes"])


if __name__ == "__main__":
    unittest.main()
