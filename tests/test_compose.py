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
                self.assertIn(seg["kind"], {"context", "detail", "move"})
                self.assertLess(seg["t0"], seg["t1"])
            kinds = {"caption", "chip", "title", "card", "cursor", "active", "result", "highlight"}
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
        for video, lay in self.layouts.items():
            base = lay["base_scale"]
            for seg in lay["camera"]:
                if seg["kind"] == "detail":
                    self.assertGreaterEqual(seg["scale"], 1.8 - 1e-6, (video, seg))
                    self.assertLessEqual(seg["scale"], 2.5 + 1e-6, (video, seg))
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
            self.assertTrue(chips)
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
        self.assertEqual(self.items("tutorial", "chip")[0]["text"], "Paso 3 · Abre el formulario")

    def test_vertical_safe_zones_and_title(self):
        lay = self.layouts["redes"]
        top, bottom = 1920 * 0.15, 1920 * 0.80
        for item in self.items("redes", "caption") + self.items("redes", "chip") + self.items("redes", "title"):
            self.assertGreaterEqual(item["rect"][1], top - 0.5, item)
            self.assertLessEqual(item["rect"][1] + item["rect"][3], bottom + 0.5, item)
        for item in self.items("redes", "active") + self.items("redes", "result"):
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
            cards = self.items(video, "card")
            tl = fixture(video)
            self.assertEqual(cards[0]["t0"], 0)
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
        # C1 as qa.py measures it: consecutive camera time below detail scale, zoom-out move included.
        tl = navigation_timeline()
        for fmt, detail in (("16:9", 1.8), ("9:16", 1.75)):
            tl["format"] = fmt
            cam = compose.plan(tl, BRAND)["camera"]
            runs, start = [], None
            for seg in cam:
                if seg["scale"] < detail and start is None:
                    start = seg["t0"]
                elif seg["scale"] >= detail and start is not None:
                    runs.append(seg["t0"] - start)
                    start = None
            if start is not None:
                runs.append(cam[-1]["t1"] - start)
            with self.subTest(fmt=fmt):
                self.assertFalse([r for r in runs if r > 1.0 + 1e-6], cam)

    def test_detail_follows_the_click_to_the_new_screen(self):
        # After the click opens the form, the camera goes in detail to the first field (no 1.0x look at a
        # half-empty dimmed screen, C4), and it is there 0.3 s before typing starts (C3).
        tl = navigation_timeline()
        cam = compose.plan(tl, BRAND)["camera"]
        after = [s for s in cam if s["t1"] > 8.24 + 1e-6 and s["t0"] < 12.79]
        self.assertFalse([s for s in after if s["kind"] == "context"], after)
        framed = next(s for s in cam if s["t0"] <= 12.79 - 0.3 + 1e-6 < s["t1"])
        self.assertEqual(framed["kind"], "detail", cam)
        self.assertGreaterEqual(framed["scale"], 1.8)

    def test_camera_cuts_to_the_next_target_when_the_screen_changes(self):
        # edit marks when the click changed the screen (screen_at). Panning there crossed the empty part
        # of the new screen (C4: 75-95 % empty); a cut is no cross-fade (C2) and frames the new target at once.
        tl = navigation_timeline()
        tl["steps"][0]["events"][0]["screen_at"] = 8.35
        layout = compose.plan(tl, BRAND)
        cam = layout["camera"]
        before = next(s for s in cam if s["t0"] <= 8.24 < s["t1"])
        after = next(s for s in cam if s["t0"] <= 8.35 < s["t1"])
        self.assertEqual(before["kind"], "detail")
        self.assertEqual(after["kind"], "detail", cam)
        self.assertAlmostEqual(after["t0"], 8.35, places=3)
        self.assertNotEqual((before["x"], before["y"]), (after["x"], after["y"]))
        self.assertFalse([s for s in cam if s["kind"] != "detail" and s["t1"] > 8.24], cam)
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


if __name__ == "__main__":
    unittest.main()
