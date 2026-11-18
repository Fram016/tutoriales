"""edit.py time-warp (odd/tasks/reglas-video.md L4): typing retime (C6), blank cuts (C4),
holds (TUT4, R2), idle speed-up (<=3x), voice gaps (A2) and card lengths (E1, A2).

Run: .venv/Scripts/python.exe -m unittest discover -s tests -v
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import compose  # noqa: E402
import edit  # noqa: E402

TUT, RED = edit.pace("TUT"), edit.pace("RED")


def frames(t0, t1, step=0.1):
    n = int(round((t1 - t0) / step))
    return [{"file": f"f{i:06d}.jpg", "t": round(t0 + i * step, 3)} for i in range(n + 1)]


def length(pieces):
    return sum(p["d"] for p in pieces)


class TypingTest(unittest.TestCase):
    def test_short_text_at_13_5_cps(self):
        self.assertAlmostEqual(edit.typing_seconds(20), 20 / 13.5)
        self.assertAlmostEqual(edit.typing_seconds(30), 30 / 13.5)

    def test_long_text_triples_after_15_chars(self):
        self.assertAlmostEqual(edit.typing_seconds(31), 15 / 13.5 + 16 / 40.5)
        self.assertAlmostEqual(edit.typing_seconds(80), 15 / 13.5 + 65 / 40.5)

    def test_typing_span_is_retimed_regardless_of_capture_speed(self):
        for t_end in (2.0, 12.0):  # fast and slow capture of the same 45 characters
            ev = {"type": "type", "t": 1.0, "t_end": t_end, "chars": 45}
            pieces = edit.build_pieces(0.0, t_end + 0.5, [ev], [], TUT, 1.0)
            typed = edit.warp(pieces, t_end) - edit.warp(pieces, 1.0)
            with self.subTest(t_end=t_end):
                self.assertAlmostEqual(typed, edit.FOCUS + edit.typing_seconds(45), places=6)


class BlankTest(unittest.TestCase):
    def test_blank_spans_from_flags(self):
        fr = frames(0, 5)
        flags = [2.0 <= f["t"] < 3.0 for f in fr]
        self.assertEqual(edit.blank_spans(fr, flags), [(2.0, 3.0)])

    def test_blank_span_is_cut(self):
        pieces = edit.build_pieces(0.0, 5.0, [], [(2.0, 3.0)], TUT, 1.0)
        self.assertEqual(edit.warp(pieces, 3.0) - edit.warp(pieces, 2.0), 0)
        self.assertTrue(any(p["kind"] == "cut" for p in pieces))
        self.assertLess(length(pieces), 5.0)

    def test_blank_image_detection(self):
        blank = Image.new("RGB", (1920, 1080), "white")
        ImageDraw.Draw(blank).rectangle([900, 500, 960, 530], fill="black")  # a spinner
        ui = Image.new("RGB", (1920, 1080), "white")
        draw = ImageDraw.Draw(ui)
        draw.rectangle([0, 0, 240, 1080], fill="#1f1235")
        for y in range(120, 900, 60):
            draw.rectangle([300, y, 1800, y + 30], fill="#d0d0d0")
        self.assertTrue(edit.is_blank_image(blank))
        self.assertFalse(edit.is_blank_image(ui))

    def test_sparse_page_is_not_a_load(self):
        # A real but sparse screen (DemoCRM list: light background, header, a short table) is content,
        # not a load: cutting it hid the list after login and the whole saved result (C4, R1).
        page = Image.new("RGB", (1920, 1080), "#f3f4f6")
        draw = ImageDraw.Draw(page)
        draw.rectangle([0, 0, 1920, 62], fill="white")
        draw.rectangle([32, 22, 142, 40], fill="#1e3a8a")           # logo text
        draw.rectangle([1740, 24, 1888, 38], fill="#374151")         # user e-mail
        draw.rectangle([392, 120, 480, 142], fill="#111827")         # "Clientes"
        draw.rectangle([1377, 109, 1528, 151], fill="#2563eb")       # "+ Nuevo cliente"
        draw.rectangle([392, 186, 1528, 336], fill="white")          # table
        for y in (206, 256, 306):
            for x0, x1 in ((410, 500), (725, 840), (1172, 1250)):
                draw.rectangle([x0, y, x1, y + 9], fill="#374151")
        self.assertFalse(edit.is_blank_image(page))


class HeaderBlankTest(unittest.TestCase):
    """N26 "Hay una pantalla en blanco": a load of the SRI shell (header bar, white page) is cut too."""

    def shell(self):
        img = Image.new("RGB", (1920, 1080), "white")
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, 1920, 60], fill="#0b3c8c")                 # header bar
        draw.rectangle([70, 18, 180, 42], fill="white")                  # logo
        for x in range(1700, 1900, 40):
            draw.rectangle([x, 20, x + 20, 40], fill="white")          # header icons
        return img, draw

    def test_white_page_under_a_header_is_a_load(self):
        img, _ = self.shell()
        self.assertTrue(edit.is_blank_image(img))

    def test_header_with_content_below_is_not(self):
        img, draw = self.shell()
        draw.rectangle([376, 120, 900, 150], fill="#333333")             # page title
        for y in range(200, 480, 40):
            draw.rectangle([376, y, 900, y + 10], fill="#555555")      # form labels and fields
        self.assertFalse(edit.is_blank_image(img))

    def test_sparse_menu_page_is_not_a_load(self):
        # The SRI "Consulta de comprobantes" page: header, side menu and four links (real content).
        img, draw = self.shell()
        for y in range(70, 580, 38):
            draw.rectangle([20, y, 200, y + 10], fill="#444444")       # side menu entries
        draw.rectangle([376, 120, 950, 150], fill="#333333")
        for y in (240, 278, 316, 354):
            draw.rectangle([396, y, 640, y + 10], fill="#1f5fa8")
        self.assertFalse(edit.is_blank_image(img))


class MixedFrameTest(unittest.TestCase):
    """N26 "Algunos fotogramas mezclan dos vistas ... “Cr / usu”": frames caught mid-navigation are cut."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)

    @staticmethod
    def page(seed, shift=0):
        """A textured page (rows of 'text' blocks), scrolled up by `shift` px."""
        img = Image.new("RGB", (1920, 1080), "white")
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, 1920, 60], fill="#0b3c8c")
        for i in range(60):
            y = 80 + i * 36 - shift
            x0 = 200 + (i * 97 * seed) % 400
            draw.rectangle([x0, y, x0 + 300 + (i * 53 * seed) % 900, y + 14],
                           fill="#222222" if (i + seed) % 3 else "#1f5fa8")
        return img

    def save(self, images, step=0.1):
        fr = frames(0, step * (len(images) - 1), step)
        for f, img in zip(fr, images):
            img.save(self.dir / f["file"])
        return fr

    def mixed(self, images, step=0.1):
        fr = self.save(images, step)
        return edit.mixed_flags(fr, [False] * len(fr), self.dir)

    def test_half_old_half_new_frame_is_mixed(self):
        a, b = self.page(1), self.page(2)
        m = a.copy()
        m.paste(b.crop((0, 0, 1920, 540)), (0, 0))
        self.assertEqual(self.mixed([a, a, m, b, b]), [False, False, True, False, False])

    def test_a_clean_change_is_not_mixed(self):
        a, b = self.page(1), self.page(2)
        self.assertEqual(self.mixed([a, a, b, b]), [False] * 4)

    def test_smooth_scroll_is_kept(self):
        # scrollIntoView moves the page between consecutive frames: motion, not two views.
        self.assertEqual(self.mixed([self.page(1, s) for s in (0, 120, 240, 360, 480)]), [False] * 5)

    def test_second_change_later_than_0_3_s_is_a_real_screen(self):
        a, b = self.page(1), self.page(2)
        m = a.copy()
        m.paste(b.crop((0, 0, 1920, 540)), (0, 0))
        self.assertEqual(self.mixed([a, m, b], step=0.5), [False] * 3)

    def test_blank_frames_are_skipped(self):
        a, b = self.page(1), self.page(2)
        m = a.copy()
        m.paste(b.crop((0, 0, 1920, 540)), (0, 0))
        white = Image.new("RGB", (1920, 1080), "white")
        fr = self.save([a, white, m, b])
        self.assertEqual(edit.mixed_flags(fr, [False, True, False, False], self.dir), [False, False, True, False])


class HoldTest(unittest.TestCase):
    def test_tut_holds_1_5_s_after_result_and_highlight(self):
        for kind in ("result", "highlight"):
            ev = {"type": kind, "t": 4.0}
            pieces = edit.build_pieces(0.0, 4.3, [ev], [], TUT, 1.0)
            with self.subTest(kind=kind):
                self.assertGreaterEqual(length(pieces) - edit.warp(pieces, 4.0), 1.5 - 1e-9)

    def test_red_result_visible_0_8_s(self):
        pieces = edit.build_pieces(0.0, 4.3, [{"type": "result", "t": 4.0}], [], RED, 3.0)
        self.assertGreaterEqual(length(pieces) - edit.warp(pieces, 4.0), 0.8 - 1e-9)

    def test_hold_is_not_compressed_by_speed(self):
        ev = {"type": "result", "t": 1.0}
        pieces = edit.build_pieces(0.0, 6.0, [ev], [], TUT, 3.0)
        self.assertGreaterEqual(length(pieces) - edit.warp(pieces, 1.0), 1.5 - 1e-9)


class WarpTest(unittest.TestCase):
    def test_idle_never_faster_than_3x(self):
        evs = [{"type": "click", "t": 2.0}, {"type": "hover", "t": 9.0}]
        for vtype in ("TUT", "RED", "PRO", "NOV"):
            plan = edit.plan_step(0.0, 12.0, evs, [], 0.5, edit.pace(vtype))
            for p in plan["pieces"]:
                if p["kind"] == "idle" and p["d"] > 0:
                    with self.subTest(vtype=vtype):
                        self.assertLessEqual((p["c1"] - p["c0"]) / p["d"], 3.0 + 1e-9)

    def test_warp_is_monotonic(self):
        evs = [{"type": "click", "t": 1.0}, {"type": "type", "t": 2.0, "t_end": 6.0, "chars": 40},
               {"type": "result", "t": 8.0}]
        pieces = edit.build_pieces(0.0, 10.0, evs, [(6.5, 7.5)], TUT, 1.5)
        outs = [edit.warp(pieces, t / 10) for t in range(0, 101)]
        self.assertEqual(outs, sorted(outs))
        self.assertAlmostEqual(outs[-1], length(pieces))

    def test_target_visible_before_click(self):
        pieces = edit.build_pieces(0.0, 3.0, [{"type": "click", "t": 0.1}], [], RED, 3.0)
        self.assertGreaterEqual(edit.warp(pieces, 0.1), edit.PRE_CLICK - 1e-9)

    def test_next_field_lead_is_short_but_keeps_c3(self):
        # Typing field after field: the field is framed 0.3 s ahead (compose) and the focus click comes
        # FOCUS later, so C3 (>= 0.5 s) holds without the 0.6 s click freeze that bloated form steps (A2).
        evs = [{"type": "type", "t": 1.0, "t_end": 3.0, "chars": 10},
               {"type": "type", "t": 3.05, "t_end": 5.0, "chars": 10}]
        pieces = edit.build_pieces(0.0, 5.2, evs, [], TUT, 3.0)
        gap = edit.warp(pieces, 3.05) - edit.warp(pieces, 3.0)
        self.assertGreaterEqual(gap + edit.FOCUS, 0.5 - 1e-9)
        self.assertLessEqual(gap, 0.3 + 1e-9)

    def test_voice_gap_at_most_1_s_when_compressible(self):
        # Two camera-only events: no main action, so N1 does not hold the step (see SyncTest).
        evs = [{"type": "focus", "t": 1.0}, {"type": "focus", "t": 2.0}]
        plan = edit.plan_step(0.0, 7.0, evs, [], 2.5, TUT)
        self.assertLessEqual(plan["duration"] - 2.5, 1.0 + 1e-9)
        self.assertAlmostEqual(plan["voice_offset"], edit.LEAD)

    def test_long_voice_holds_last_frame(self):
        # Without a main action (a click waits for its narration instead, see SyncTest).
        plan = edit.plan_step(0.0, 1.0, [{"type": "focus", "t": 0.3}, {"type": "focus", "t": 0.6}], [], 4.0, TUT)
        self.assertAlmostEqual(plan["duration"], 4.0 + edit.LEAD + edit.TAIL)
        self.assertEqual(plan["pieces"][-1]["kind"], "freeze")

    def test_red_is_faster_than_tut(self):
        evs = [{"type": "click", "t": 0.8}, {"type": "click", "t": 1.6}]
        tut = edit.plan_step(0.0, 2.4, evs, [], 0.0, TUT)["duration"]
        red = edit.plan_step(0.0, 2.4, evs, [], 0.0, RED)["duration"]
        self.assertLess(red, tut)


def tutorial_of(step_ids):
    tut = {"title": "Cómo crear un cliente", "product": "DemoCRM", "viewport": [1920, 1080]}
    video = {"id": "tutorial", "type": "TUT", "format": "16:9", "requirements": None,
             "steps": [{"id": s, "number": i + 1, "narration": "Haz clic aquí."} for i, s in enumerate(step_ids)],
             "opening": {"text": "Aprende", "narration": "En este video aprendes algo."},
             "closing": {"text": "Siguiente", "narration": "Siguiente video: otra cosa."}}
    return tut, video


def box(x, y):
    return {"box": {"x": x, "y": y, "w": 150, "h": 42}, "point": {"x": x + 75, "y": y + 21}}


def voice_gaps(tl):
    blocks = [tl["opening"], tl["requirements"]] + tl["steps"] + [tl["closing"]]
    spans = sorted((b["voice_start"], b["voice_start"] + b["voice_duration"]) for b in blocks
                   if b and b["voice_duration"] > 0)
    return [b[0] - a[1] for a, b in zip(spans, spans[1:])]


def capture_at(step, o):
    """Capture time shown at output time `o` of a planned step (inverse of the warp)."""
    for p in step["warp"]:
        if p["o0"] <= o < p["o1"]:
            return p["c0"] + (p["c1"] - p["c0"]) * (o - p["o0"]) / (p["o1"] - p["o0"])
    raise AssertionError(f"{o} fuera del paso")


class ScreenChangeTest(unittest.TestCase):
    """A click that opens or closes a screen: edit finds when it changed so compose cuts there (C2, C4)."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        page = Image.new("RGB", (1920, 1080), "#f3f4f6")
        draw = ImageDraw.Draw(page)
        draw.rectangle([0, 0, 1920, 62], fill="white")
        draw.rectangle([392, 186, 1528, 336], fill="white")
        draw.rectangle([1377, 109, 1528, 151], fill="#2563eb")
        modal = Image.blend(page, Image.new("RGB", page.size, "#111827"), 0.45)
        ImageDraw.Draw(modal).rectangle([750, 320, 1170, 760], fill="white")
        ticked = page.copy()
        ImageDraw.Draw(ticked).rectangle([400, 200, 416, 216], fill="#2563eb")   # a checkbox
        self.images = {"page": page, "modal": modal, "ticked": ticked}

    def capture(self, after):
        """Frames every 0.1 s: `page` until 1.0 s, then `after`."""
        fr = frames(0, 3)
        for f in fr:
            self.images["page" if f["t"] < 1.0 else after].save(self.dir / f["file"])
        return fr

    def test_new_screen_is_found_after_the_click(self):
        fr = self.capture("modal")
        flags = [False] * len(fr)
        self.assertAlmostEqual(edit.screen_change(fr, flags, self.dir, 0.9), 1.0)

    def test_same_screen_is_not_a_change(self):
        fr = self.capture("ticked")
        self.assertIsNone(edit.screen_change(fr, [False] * len(fr), self.dir, 0.9))

    def test_a_list_appearing_is_an_effect_not_a_screen(self):
        # N14: "Aparece la lista" under the form is the click's visible effect (effect_c), not a new screen.
        listed = self.images["page"].copy()
        draw = ImageDraw.Draw(listed)
        for y in range(400, 640, 40):
            draw.rectangle([392, y, 1528, y + 20], fill="#374151")
        self.images["listed"] = listed
        fr = self.capture("listed")
        flags = [False] * len(fr)
        self.assertIsNone(edit.screen_change(fr, flags, self.dir, 0.9))
        actions = {"steps": [{"id": "consultar", "t0": 0.0, "t1": 3.0, "events": [
            {"type": "click", "t": 1.05, "selector": "#consultar"},
            {"type": "click", "t": 1.05, "selector": "#boton4", "surface": "popup"}]}]}
        edit.mark_screen_changes(actions, fr, flags, self.dir)
        click, inside = actions["steps"][0]["events"]
        self.assertAlmostEqual(click["effect_c"], 1.0)
        self.assertNotIn("screen_c", click)
        self.assertNotIn("effect_c", inside)   # a click inside a surface changes the surface only

    def test_a_new_screen_is_also_the_effect(self):
        fr = self.capture("modal")
        actions = {"steps": [{"id": "nuevo", "t0": 0.0, "t1": 3.0, "events": [
            {"type": "click", "t": 1.05, "selector": "#btn-new"}]}]}
        edit.mark_screen_changes(actions, fr, [False] * len(fr), self.dir)
        click = actions["steps"][0]["events"][0]
        self.assertAlmostEqual(click["screen_c"], 1.0)
        self.assertAlmostEqual(click["effect_c"], 1.0)

    def test_change_is_mapped_to_output_time(self):
        tut, video = tutorial_of(["nuevo"])
        actions = {"steps": [{"id": "nuevo", "t0": 0.0, "t1": 3.0, "events": [
            {"type": "click", "t": 1.05, "selector": "#btn-new", "screen_c": 1.0, **box(1377, 109)}]}]}
        tl = edit.plan_video(tut, video, actions, [], {"opening": 2.0, "nuevo": 2.0, "closing": 1.5})
        step = tl["steps"][0]
        click = step["events"][0]
        self.assertGreaterEqual(click["screen_at"], click["t"])
        self.assertAlmostEqual(capture_at(step, click["screen_at"] + 1e-6), 1.0, delta=0.005)  # ms rounding at 3x


class TimelineTest(unittest.TestCase):
    def test_click_effect_is_not_shown_before_the_click(self):
        # The recorder logs a click once page.mouse.click returns: the page already changed ~50 ms before.
        tut, video = tutorial_of(["nuevo"])
        logged = 2.0
        actions = {"steps": [{"id": "nuevo", "t0": 0.0, "t1": 3.0,
                               "events": [{"type": "click", "t": logged, "selector": "#btn-new", **box(1377, 109)}]}]}
        tl = edit.plan_video(tut, video, actions, [], {"opening": 2.0, "nuevo": 2.0, "closing": 1.5})
        step = tl["steps"][0]
        click = step["events"][0]["t"]
        self.assertLessEqual(capture_at(step, click - 0.01), logged - edit.CLICK_LAG + 1e-6)
        # C3 still holds: the pre-click frames last >= 0.5 s.
        self.assertGreaterEqual(click - step["start"], 0.5)

    def test_voice_is_placed_to_keep_every_silence_within_1_s(self):
        # "ver" shows two results (1.5 s each, TUT4) but its narration is short: centring its voice inside
        # the step left 1.15 s before and 1.45 s after. Neighbours that hold a frame give way (A2).
        # Camera-only neighbours: a click step's voice is pinned before its click instead (N1, SyncTest).
        tut, video = tutorial_of(["abrir", "ver", "cerrar"])
        actions = {"steps": [
            {"id": "abrir", "t0": 0.0, "t1": 0.5, "events": [{"type": "focus", "t": 0.2, **box(100, 100)}]},
            {"id": "ver", "t0": 10.0, "t1": 10.0, "events": [{"type": "result", "t": 10.0, **box(300, 300)},
                                                          {"type": "highlight", "t": 10.0, **box(300, 400)}]},
            {"id": "cerrar", "t0": 11.0, "t1": 11.5, "events": [{"type": "focus", "t": 11.2, **box(500, 100)}]},
        ]}
        durations = {"opening": 2.0, "abrir": 2.0, "ver": 1.1, "cerrar": 2.0, "closing": 1.5}
        tl = edit.plan_video(tut, video, actions, [], durations)
        for gap in voice_gaps(tl):
            self.assertLessEqual(gap, edit.GAP + 1e-6, voice_gaps(tl))
        for step in tl["steps"]:
            with self.subTest(step=step["id"]):
                self.assertGreaterEqual(step["voice_start"], step["start"] - 1e-6)
                self.assertLessEqual(step["voice_start"] + step["voice_duration"],
                                     step["start"] + step["duration"] + 1e-6)
        self.assertFalse([w for w in tl["warnings"] if "silencio" in w], tl["warnings"])
        ver = tl["steps"][1]
        self.assertAlmostEqual(ver["duration"], 3.0)   # TUT4: the holds are never shortened

    def test_voice_keeps_its_lead_when_silences_are_short(self):
        tut, video = tutorial_of(["abrir", "cerrar"])
        actions = {"steps": [
            {"id": "abrir", "t0": 0.0, "t1": 0.5, "events": [{"type": "click", "t": 0.2, **box(100, 100)}]},
            {"id": "cerrar", "t0": 1.0, "t1": 1.5, "events": [{"type": "click", "t": 1.2, **box(500, 100)}]},
        ]}
        tl = edit.plan_video(tut, video, actions, [], {"opening": 2.0, "abrir": 2.0, "cerrar": 2.0, "closing": 1.5})
        for step in tl["steps"]:
            self.assertAlmostEqual(step["voice_start"] - step["start"], edit.LEAD, places=3)


class CardTest(unittest.TestCase):
    def test_opening_at_most_3_s(self):
        card = edit.plan_card("opening", "TUT", 2.0)
        self.assertLessEqual(card["duration"], 3.0)
        self.assertLessEqual(card["voice_start"] + 2.0, card["duration"])

    def test_red_hook_1_5_to_2_s(self):
        card = edit.plan_card("opening", "RED", 1.2)
        self.assertGreaterEqual(card["duration"], 1.5)
        self.assertLessEqual(card["duration"], 2.0)

    def test_closing_at_most_2_5_s(self):
        for voice in (0.8, 1.6, 2.2):
            card = edit.plan_card("closing", "TUT", voice)
            with self.subTest(voice=voice):
                self.assertLessEqual(card["duration"], 2.5)
                self.assertGreaterEqual(card["duration"], voice)

    def test_voice_longer_than_cap_is_not_cut_and_warns(self):
        card = edit.plan_card("closing", "TUT", 3.4)
        self.assertGreaterEqual(card["duration"], 3.4 + card["voice_start"])
        self.assertIn("closing", card["warning"])


def video_of(steps, vtype="TUT", omit=()):
    """steps: [(id, narration)]."""
    tut = {"title": "Cómo crear un contacto", "product": "Nexo CRM", "viewport": [1920, 1080]}
    video = {"id": "v", "type": vtype, "format": "16:9", "requirements": None, "omit": list(omit),
             "steps": [{"id": s, "number": i + 1, "narration": n} for i, (s, n) in enumerate(steps)],
             "opening": {"text": "Aprende", "narration": "En este video aprendes algo."},
             "closing": {"text": "Siguiente", "narration": "Siguiente video: otra cosa."}}
    return tut, video


def event(tl, step, kind):
    return next(e for e in tl["steps"][step]["events"] if e["type"] == kind)


class SyncTest(unittest.TestCase):
    """N1: the narration asking for an action ends before it (at most 0.3 s after the click)."""

    def test_nuevo_contacto_is_heard_before_the_form_opens(self):
        # "Haz clic en Nuevo contacto" appeared with the form already open (≈0:16).
        tut, video = video_of([("nuevo", "Haz clic en Nuevo contacto.")])
        actions = {"steps": [{"id": "nuevo", "t0": 0.0, "t1": 1.8, "events": [
            {"type": "click", "t": 0.9, "selector": "#btn-new", "screen_c": 0.8, **box(1377, 109)}]}]}
        tl = edit.plan_video(tut, video, actions, [], {"opening": 2.0, "nuevo": 2.6, "closing": 1.5})
        step, click = tl["steps"][0], event(tl, 0, "click")
        self.assertGreaterEqual(step["voice_start"], step["start"] - 1e-6)
        self.assertLessEqual(step["voice_start"] + step["voice_duration"], click["t"] + 0.3 + 1e-6)
        self.assertGreaterEqual(click["screen_at"], click["t"])
        self.assertAlmostEqual(step["action_t"], click["t"])
        # The hold is a freeze before the click: the form is not shown before the click.
        self.assertLess(capture_at(step, click["t"] - 0.01), 0.8)

    def test_guardar_is_heard_before_the_list_appears(self):
        # "Haz clic en Guardar contacto" appeared over the saved list (≈0:31).
        tut, video = video_of([("guardar", "Haz clic en Guardar contacto. El contacto nuevo queda primero "
                                           "en la lista, resaltado.")])
        actions = {"steps": [{"id": "guardar", "t0": 0.0, "t1": 4.0, "events": [
            {"type": "click", "t": 0.7, "selector": "#btn-save", **box(1300, 900)},
            {"type": "result", "t": 1.2, "selector": "#toast", **box(1500, 950)},
            {"type": "highlight", "t": 2.0, "selector": "tr.new", **box(400, 200)}]}]}
        voice = 4.2
        tl = edit.plan_video(tut, video, actions, [], {"opening": 2.0, "guardar": voice, "closing": 1.5})
        step, click = tl["steps"][0], event(tl, 0, "click")
        instruction = step["instruction_duration"]
        self.assertLess(instruction, voice)          # only the first sentence asks for the click
        self.assertGreater(instruction, 0.3 * voice)
        self.assertLessEqual(step["voice_start"] + instruction, click["t"] + 0.3 + 1e-6)
        self.assertGreaterEqual(step["voice_start"], step["start"] - 1e-6)
        self.assertLessEqual(step["voice_start"] + voice, step["start"] + step["duration"] + 1e-6)
        result = event(tl, 0, "result")
        self.assertGreaterEqual(result["t_end"] - result["t"], 1.5 - 1e-6)   # TUT4 kept
        for gap in voice_gaps(tl):
            self.assertLessEqual(gap, edit.GAP + 1e-6)

    def test_no_hold_when_the_lead_in_is_long_enough(self):
        tut, video = video_of([("nuevo", "Haz clic en Nuevo contacto.")])
        actions = {"steps": [{"id": "nuevo", "t0": 0.0, "t1": 5.0, "events": [
            {"type": "hover", "t": 0.5, "selector": "#menu", **box(10, 100)},
            {"type": "hover", "t": 1.0, "selector": "#menu2", **box(10, 200)},
            {"type": "click", "t": 4.5, "selector": "#btn-new", **box(1377, 109)}]}]}
        tl = edit.plan_video(tut, video, actions, [], {"opening": 2.0, "nuevo": 1.2, "closing": 1.5})
        step = tl["steps"][0]
        # No N1 hold before the click (the only freeze long enough is C7's room before the first hover).
        self.assertFalse([p for p in step["warp"] if p["kind"] == "freeze" and p["o1"] - p["o0"] > 0.7
                          and p["c0"] > 0.5])
        self.assertLessEqual(step["voice_start"] + 1.2, event(tl, 0, "click")["t"] + 0.3 + 1e-6)

    def test_steps_without_a_main_action_are_free(self):
        # Several fields and no click: the narration describes the typing while it happens.
        tut, video = video_of([("datos", "Completa el nombre y el correo.")])
        actions = {"steps": [{"id": "datos", "t0": 0.0, "t1": 4.0, "events": [
            {"type": "type", "t": 0.5, "t_end": 1.5, "chars": 10, "selector": "#a", **box(800, 400)},
            {"type": "type", "t": 1.6, "t_end": 3.0, "chars": 12, "selector": "#b", **box(800, 500)}]}]}
        tl = edit.plan_video(tut, video, actions, [], {"opening": 2.0, "datos": 2.0, "closing": 1.5})
        self.assertIsNone(tl["steps"][0]["action_t"])

    def test_instruction_share(self):
        self.assertEqual(edit.instruction_share("Haz clic en Nuevo contacto."), 1.0)
        text = "Haz clic en Guardar. Tu contacto queda primero en la lista."
        self.assertAlmostEqual(edit.instruction_share(text), len("Haz clic en Guardar.") / len(text), places=2)
        # The instruction is the first sentence that asks for something, not the context before it.
        share = edit.instruction_share("Ya tienes los datos. Ahora haz clic en Guardar. Listo.")
        self.assertGreater(share, 0.5)
        self.assertLess(share, 0.95)


class NoClosingTest(unittest.TestCase):
    def test_tut_without_closing_ends_on_the_last_step(self):
        # N27 "quita el ultimo espacio que dice siguiente video": no closing card, the video ends on the result.
        tut, video = video_of([("nuevo", "Haz clic aquí.")])
        video["closing"] = None
        actions = {"steps": [{"id": "nuevo", "t0": 0.0, "t1": 3.0, "events": [
            {"type": "click", "t": 1.0, "selector": "#btn", **box(100, 100)}]}]}
        tl = edit.plan_video(tut, video, actions, [], {"opening": 1.5, "nuevo": 1.0})
        self.assertIsNone(tl["closing"])
        self.assertEqual(tl["total"], tl["screen_end"])


class EffectSyncTest(unittest.TestCase):
    """N14/N1: “Haz clic en Consultar. Aparece la lista” llega cuando la lista ya está en pantalla (≈1:13).
    The click comes after the instruction sentence and the list after the effect sentence starts."""

    NARRATION = "Haz clic en Consultar. Aparece la lista"

    def plan(self, click, narration=NARRATION, voice=2.6):
        tut, video = video_of([("consultar", narration)])
        actions = {"steps": [{"id": "consultar", "t0": 0.0, "t1": 3.2, "events": [
            {"type": "click", "t": 1.0, "selector": "#btnConsultar", **box(700, 500), **click},
            {"type": "highlight", "t": 2.6, "selector": "#tabla", **box(400, 600)}]}]}
        return edit.plan_video(tut, video, actions, [], {"opening": 1.5, "consultar": voice, "closing": 1.5})

    def check(self, tl, appears):
        step, click = tl["steps"][0], event(tl, 0, "click")
        self.assertLessEqual(step["instruction_end"], click["t"] + 1e-6)          # click after "Haz clic en Consultar."
        self.assertGreater(step["effect_start"], step["instruction_end"])
        self.assertLessEqual(step["effect_start"], step["effect_t"] + 1e-6)          # list after "Aparece" starts
        self.assertLess(capture_at(step, step["effect_start"] - 0.01), appears)    # no list frame before it
        self.assertGreaterEqual(capture_at(step, step["effect_t"] + 1e-3), appears - 1e-6)
        self.assertGreaterEqual(step["voice_start"], step["start"] - 1e-6)
        self.assertLessEqual(step["voice_start"] + step["voice_duration"], step["start"] + step["duration"] + 1e-6)
        return step, click

    def test_list_after_a_screen_change(self):
        tl = self.plan({"screen_c": 1.3, "effect_c": 1.3})
        step, click = self.check(tl, 1.3)
        self.assertAlmostEqual(step["effect_t"], click["screen_at"], places=3)

    def test_list_appearing_under_the_form(self):
        self.check(self.plan({"effect_c": 1.3}), 1.3)

    def test_effect_right_at_the_click(self):
        self.check(self.plan({"effect_c": 1.0}), 1.0)

    def test_effect_shares(self):
        text = self.NARRATION
        self.assertAlmostEqual(edit.effect_share(text), len("Haz clic en Consultar. ") / len(text))
        self.assertIsNone(edit.effect_share("Haz clic en Consultar."))
        # A second instruction is not a visible effect.
        self.assertIsNone(edit.effect_share("Escribe la fecha. Para una consulta corta, elige el establecimiento."))

    def test_without_an_effect_sentence_n1_is_unchanged(self):
        # PRESERVE: one sentence keeps N1 (instruction ends at most SYNC_AFTER after the click).
        tl = self.plan({"effect_c": 1.3}, narration="Haz clic en Consultar.", voice=1.6)
        step, click = tl["steps"][0], event(tl, 0, "click")
        self.assertIsNone(step["effect_t"])
        self.assertLessEqual(step["instruction_end"], click["t"] + edit.SYNC_AFTER + 1e-6)
        self.assertGreater(step["instruction_end"], click["t"] + 0.05)


class OmitTest(unittest.TestCase):
    """videos[].omit: typing on those fields is cut from that video; the step and its number stay."""

    ACTIONS = {"steps": [{"id": "datos", "t0": 0.0, "t1": 9.0, "events": [
        {"type": "type", "t": 0.5, "t_end": 2.5, "chars": 14, "selector": "#c-name", **box(800, 400)},
        {"type": "type", "t": 3.0, "t_end": 6.0, "chars": 17, "selector": "#c-email", **box(800, 500)},
        {"type": "select", "t": 6.65, "selector": "#c-stage", **box(800, 600)},
        {"type": "type", "t": 7.0, "t_end": 8.5, "chars": 12, "selector": "#c-phone", **box(800, 700)}]}]}
    DURATIONS = {"opening": 1.5, "datos": 1.0, "closing": 1.5}

    def plan(self, omit=()):
        tut, video = video_of([("datos", "Completa los datos.")], "RED", omit)
        video["steps"][0]["number"] = 3
        return edit.plan_video(tut, video, self.ACTIONS, [], self.DURATIONS)

    def test_omitted_typing_is_cut(self):
        full, short = self.plan(), self.plan(["#c-email", "#c-stage"])
        step = short["steps"][0]
        self.assertEqual([e["selector"] for e in step["events"]], ["#c-name", "#c-phone"])
        self.assertEqual(step["number"], 3)
        self.assertLess(step["duration"], full["steps"][0]["duration"] - edit.typing_seconds(17))
        for p in step["warp"]:   # no frame of the e-mail typing nor of the stage change is shown
            if p["o1"] - p["o0"] > 1e-6:
                with self.subTest(piece=p):
                    self.assertFalse(p["c0"] < 6.5 and p["c1"] > 3.0, p)
                    self.assertFalse(p["c0"] == p["c1"] and 3.0 < p["c0"] < 6.5, p)

    def test_other_videos_keep_the_typing(self):
        self.assertEqual(len(self.plan()["steps"][0]["events"]), 4)

    def test_the_field_left_after_omit_is_not_a_main_action(self):
        # N1 looks at the step as written: its main action (the select) is omitted here, and the single
        # field omit leaves in this video does not become one.
        step = self.plan(["#c-email", "#c-stage", "#c-phone"])["steps"][0]
        self.assertEqual([e["selector"] for e in step["events"]], ["#c-name"])
        self.assertIsNone(step["action_t"])


class EventFieldsTest(unittest.TestCase):
    def test_frame_box_reaches_the_timeline(self):
        tut, video = video_of([("datos", "Completa el nombre.")])
        fb = {"x": 790, "y": 410, "w": 340, "h": 80}
        actions = {"steps": [{"id": "datos", "t0": 0.0, "t1": 3.0, "events": [
            {"type": "type", "t": 0.5, "t_end": 2.0, "chars": 10, "selector": "#c-name", "frame_box": fb,
             **box(790, 446)}]}]}
        tl = edit.plan_video(tut, video, actions, [], {"opening": 1.5, "datos": 1.0, "closing": 1.5})
        self.assertEqual(tl["steps"][0]["events"][0]["frame_box"], fb)

    def test_form_box_reaches_the_timeline(self):
        tut, video = video_of([("datos", "Completa el nombre.")])
        form = {"x": 640, "y": 200, "w": 640, "h": 620}
        actions = {"steps": [{"id": "datos", "t0": 0.0, "t1": 3.0, "events": [
            {"type": "type", "t": 0.5, "t_end": 2.0, "chars": 10, "selector": "#c-name", "form_box": form,
             **box(790, 446)}]}]}
        tl = edit.plan_video(tut, video, actions, [], {"opening": 1.5, "datos": 1.0, "closing": 1.5})
        self.assertEqual(tl["steps"][0]["events"][0]["form_box"], form)


class RoundFourFieldsTest(unittest.TestCase):
    def test_target_check_reaches_the_timeline(self):
        # N13: qa reads target_ok / target_text per event.
        tut, video = video_of([("nuevo", "Haz clic en Nuevo.")])
        actions = {"steps": [{"id": "nuevo", "t0": 0.0, "t1": 3.0, "events": [
            {"type": "click", "t": 1.0, "selector": "#btn", "target_ok": True, "target_text": "Nuevo", **box(100, 100)},
            {"type": "highlight", "t": 2.0, "selector": "#t", "target_ok": True, **box(100, 300)}]}]}
        tl = edit.plan_video(tut, video, actions, [], {"opening": 1.5, "nuevo": 1.0, "closing": 1.5})
        click, mark = tl["steps"][0]["events"]
        self.assertEqual((click["target_ok"], click["target_text"]), (True, "Nuevo"))
        self.assertNotIn("target_text", mark)

    def test_censor_regions_in_output_time(self):
        # N25: regions of a followed chrome:// tab go through the warp like a surface window.
        tut, video = video_of([("carpeta", "Haz clic en Carpeta.")])
        b = {"x": 627, "y": 154, "w": 213, "h": 17}
        actions = {"steps": [{"id": "carpeta", "t0": 0.0, "t1": 4.0, "events": [
            {"type": "click", "t": 1.0, "selector": "#configure-folder", **box(100, 100)}]}],
            "censor_regions": [{"t0": 2.0, "t1": 3.5, "box": b}]}
        tl = edit.plan_video(tut, video, actions, [], {"opening": 1.5, "carpeta": 1.0, "closing": 1.5})
        step = tl["steps"][0]
        (region,) = tl["censor_regions"]
        self.assertEqual(region["box"], b)
        self.assertAlmostEqual(capture_at(step, region["t0"] + 1e-3), 2.0, delta=0.01)
        self.assertAlmostEqual(capture_at(step, region["t1"] - 1e-3), 3.5, delta=0.01)
        # PRESERVE: without regions the key is absent.
        del actions["censor_regions"]
        self.assertNotIn("censor_regions", edit.plan_video(tut, video, actions, [], {"opening": 1.5, "carpeta": 1.0}))


class ToastWindowTest(unittest.TestCase):
    """S1(b), R2/N6: the toast plays at 1.0x for >= R2_CLEAN + margin after compose's camera lands on it."""

    def plan(self, vtype):
        # v3 RED: Guardar, then the toast 1.1 s later and the new row; the toast was clean only 0.60 s.
        tut, video = video_of([("guardar", "Haz clic en Guardar.")], vtype)
        actions = {"steps": [{"id": "guardar", "t0": 0.0, "t1": 3.6, "events": [
            {"type": "click", "t": 0.7, "selector": "#btn-save", **box(1300, 900)},
            {"type": "result", "t": 1.8, "selector": "#toast", **box(1500, 950)},
            {"type": "highlight", "t": 2.6, "selector": "tr.new", **box(400, 200)}]}]}
        return edit.plan_video(tut, video, actions, [], {"opening": 1.5, "guardar": 1.0, "closing": 1.5})

    def test_toast_is_clean_after_the_camera_lands_in_every_type(self):
        for vtype in ("RED", "TUT", "PRO", "NOV"):
            tl = self.plan(vtype)
            step, click, result = tl["steps"][0], event(tl, 0, "click"), event(tl, 0, "result")
            # compose pans to a toast once the click's framing is done (HOLD) and the pan (MOVE) ends.
            lands = max(result["t"], click["t"] + compose.HOLD["click"] + compose.MOVE)
            with self.subTest(vtype=vtype):
                self.assertGreaterEqual(result["t_end"] - lands, compose.R2_CLEAN + edit.R2_MARGIN - 1e-3)
                for p in step["warp"]:   # the whole window at 1.0x: real time or a still of the toast
                    if p["o1"] > result["t"] + 1e-6 and p["o0"] < result["t_end"] - 1e-6:
                        self.assertIn(p["kind"], ("hold", "freeze"), p)
                        if p["kind"] == "hold":
                            self.assertAlmostEqual(p["o1"] - p["o0"], p["c1"] - p["c0"], delta=2e-3)

    def test_toast_after_a_new_screen_is_reached_fast(self):
        # S1(a), C4: Guardar closes the form; the list waits 2 s for the toast. Those frames are all cut: compose
        # cuts to the toast framing at screen_at, so the new screen opens with the toast already on it (v3 TUT
        # 18.42-18.72: 0.3 s of an empty corner).
        for vtype in ("RED", "TUT"):
            tut, video = video_of([("guardar", "Haz clic en Guardar.")], vtype)
            actions = {"steps": [{"id": "guardar", "t0": 0.0, "t1": 4.5, "events": [
                {"type": "click", "t": 0.9, "selector": "#btn-save", "screen_c": 0.8, **box(1300, 900)},
                {"type": "result", "t": 3.0, "selector": "#toast", **box(1500, 950)}]}]}
            tl = edit.plan_video(tut, video, actions, [], {"opening": 1.5, "guardar": 1.0, "closing": 1.5})
            step, click, result = tl["steps"][0], event(tl, 0, "click"), event(tl, 0, "result")
            with self.subTest(vtype=vtype):
                self.assertAlmostEqual(result["t"], click["screen_at"], delta=1e-3)
                self.assertGreaterEqual(capture_at(step, click["screen_at"] + 1e-3), 3.0 - 1e-6)   # with the toast
                self.assertGreaterEqual(result["t_end"] - result["t"], compose.R2_CLEAN + edit.R2_MARGIN - 1e-3)

    def test_typing_after_a_new_screen_is_not_cut(self):
        # Only the wait for a toast is cut: a new screen followed by a field keeps its frames (C7 room).
        tut, video = video_of([("nuevo", "Haz clic en Nuevo contacto.")], "RED")
        actions = {"steps": [{"id": "nuevo", "t0": 0.0, "t1": 4.5, "events": [
            {"type": "click", "t": 0.9, "selector": "#btn-new", "screen_c": 0.8, **box(1377, 109)},
            {"type": "type", "t": 3.0, "t_end": 3.5, "chars": 5, "selector": "#c-name", **box(790, 446)}]}]}
        tl = edit.plan_video(tut, video, actions, [], {"opening": 1.5, "nuevo": 1.0, "closing": 1.5})
        self.assertFalse([p for p in tl["steps"][0]["warp"] if p["kind"] == "cut"])


class ClosingCardTest(unittest.TestCase):
    def test_closing_is_voice_plus_at_most_0_3_s(self):
        for voice in (0.9, 1.4, 2.0, 2.2):
            card = edit.plan_card("closing", "TUT", voice)
            with self.subTest(voice=voice):
                self.assertLessEqual(card["duration"], voice + 0.3 + 1e-6)
                self.assertGreaterEqual(card["duration"], card["voice_start"] + voice - 1e-6)
                self.assertIsNone(card["warning"])

    def test_closing_caps_at_2_5_s_while_the_voice_fits(self):
        card = edit.plan_card("closing", "RED", 2.4)
        self.assertAlmostEqual(card["duration"], 2.5)
        self.assertIsNone(card["warning"])

    def test_voice_over_the_cap_warns(self):
        card = edit.plan_card("closing", "RED", 2.6)
        self.assertIn("closing", card["warning"])
        self.assertGreaterEqual(card["duration"], 2.6)


def surface_actions():
    """perseo-xml S5: the popup is open from 1.0 to 5.0 s of capture; a button is clicked inside it."""
    return {"steps": [
        {"id": "abrir", "t0": 0.0, "t1": 4.0, "events": [
            {"type": "open", "t": 1.0, "surface": "popup"},
            {"type": "click", "t": 2.0, "surface": "popup", "selector": "#boton4", **box(40, 300)}]},
        {"id": "cerrar", "t0": 4.0, "t1": 6.0, "events": [
            {"type": "close", "t": 5.0, "surface": "popup"}]}],
        "surfaces": {"popup": {"size": [420, 640], "dpr": 2, "anchor": "top-right", "dir": "surfaces/popup",
                               "windows": [{"t0": 1.0, "t1": 5.0}]}}}


class SurfaceTest(unittest.TestCase):
    """Surface frames go through the same time-warp; the timeline carries their visibility windows."""

    def plan(self, steps=("abrir", "cerrar"), vtype="TUT"):
        tut, video = video_of([(s, "Haz clic en el icono.") for s in steps], vtype)
        tut["surfaces"] = {"popup": {"icon": "brand/icon48.png"}}
        return edit.plan_video(tut, video, surface_actions(), [], {"opening": 1.5, **{s: 1.0 for s in steps},
                                                                  "closing": 1.5})

    def test_windows_follow_the_open_and_close_events(self):
        tl = self.plan()
        opened, closed = event(tl, 0, "open"), event(tl, 1, "close")
        spec = tl["surfaces"]["popup"]
        self.assertEqual(spec["windows"], [[opened["t"], closed["t"]]])
        self.assertEqual((spec["size"], spec["dpr"], spec["anchor"], spec["icon"], spec["file"]),
                         ([420, 640], 2, "top-right", "brand/icon48.png", "surface-popup.mp4"))

    def test_surface_events_keep_their_surface(self):
        tl = self.plan()
        self.assertEqual(event(tl, 0, "click")["surface"], "popup")
        self.assertEqual(event(tl, 0, "open")["surface"], "popup")

    def test_open_is_a_pointer_action(self):
        # The cursor travels to the toolbar icon: C3 lead before the open, and it is the step's main action (N1).
        tl = self.plan()
        step, opened = tl["steps"][0], event(tl, 0, "open")
        self.assertGreaterEqual(opened["t"] - step["start"], edit.PRE_CLICK - 1e-6)
        self.assertEqual(step["action_t"], opened["t"])

    def test_subset_video_shows_the_popup_from_its_first_step(self):
        tl = self.plan(steps=("cerrar",), vtype="RED")
        self.assertEqual(tl["surfaces"]["popup"]["windows"], [[tl["steps"][0]["start"], event(tl, 0, "close")["t"]]])

    def test_windows_through_freezes_and_cuts(self):
        steps = [{"warp": [{"kind": "idle", "c0": 0.0, "c1": 1.0, "o0": 3.0, "o1": 3.5},
                           {"kind": "freeze", "c0": 1.0, "c1": 1.0, "o0": 3.5, "o1": 4.1},    # before the open
                           {"kind": "idle", "c0": 1.0, "c1": 3.0, "o0": 4.1, "o1": 5.1},
                           {"kind": "cut", "c0": 3.0, "c1": 3.5, "o0": 5.1, "o1": 5.1},
                           {"kind": "idle", "c0": 3.5, "c1": 5.5, "o0": 5.1, "o1": 6.1},
                           {"kind": "freeze", "c0": 5.5, "c1": 5.5, "o0": 6.1, "o1": 7.0}]}]
        self.assertEqual(edit.surface_windows(steps, [(1.0, 5.0)]), [[4.1, 5.85]])
        self.assertEqual(edit.surface_windows(steps, [(1.0, 6.0)]), [[4.1, 7.0]])
        self.assertEqual(edit.surface_windows(steps, [(0.5, 2.0), (3.6, 4.0)]), [[3.25, 4.6], [5.15, 5.35]])

    def test_surface_frames_use_the_same_warp(self):
        tl = self.plan()
        fr = [{"file": f"w0_f{i:06d}.jpg", "t": round(1.0 + i * 0.1, 3)} for i in range(41)]
        entries, end = edit.frame_entries(fr, [False] * len(fr), tl)
        self.assertAlmostEqual(end, tl["screen_end"] - tl["screen_start"])
        times = [t for _, t in entries]
        self.assertEqual(times, sorted(times))
        opened = event(tl, 0, "open")["t"] - tl["screen_start"]
        shown = [name for name, t in entries if t <= opened + 1e-6]
        self.assertEqual(shown[-1], "w0_f000000.jpg")

    def test_no_surfaces_no_key(self):
        # PRESERVE: captures without surfaces keep the timeline as before.
        tut, video = video_of([("nuevo", "Haz clic aquí.")])
        actions = {"steps": [{"id": "nuevo", "t0": 0.0, "t1": 3.0, "events": [
            {"type": "click", "t": 1.0, "selector": "#btn", **box(100, 100)}]}]}
        tl = edit.plan_video(tut, video, actions, [], {"opening": 1.5, "nuevo": 1.0, "closing": 1.5})
        self.assertNotIn("surfaces", tl)
        self.assertNotIn("surface", tl["steps"][0]["events"][0])


RECORDER = Path(__file__).resolve().parents[1] / "tools" / "capture" / "recorder.mjs"


@unittest.skipUnless(shutil.which("node"), "node no está instalado")
class FrameBoxTest(unittest.TestCase):
    """C9: the recorder frames a field together with its visible label (recorder.mjs frameBox)."""

    def frame_box(self, control, labels, viewport=(1920, 1080)):
        import json
        import subprocess
        script = (f"const {{ frameBox }} = await import({json.dumps(RECORDER.as_uri())});"
                  f"console.log(JSON.stringify(frameBox({json.dumps(control)}, {json.dumps(labels)}, "
                  f"{json.dumps(list(viewport))})));")
        out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True,
                             check=True)
        return json.loads(out.stdout)

    def test_label_above_is_included(self):
        control = {"x": 790, "y": 446, "w": 340, "h": 44}
        label = {"x": 790, "y": 420, "w": 60, "h": 18}
        self.assertEqual(self.frame_box(control, [label]), {"x": 790, "y": 420, "w": 340, "h": 70})

    def test_label_beside_is_included(self):
        control = {"x": 400, "y": 300, "w": 200, "h": 40}
        label = {"x": 250, "y": 310, "w": 120, "h": 20}
        self.assertEqual(self.frame_box(control, [label]), {"x": 250, "y": 300, "w": 350, "h": 40})

    def test_no_label_is_the_control(self):
        control = {"x": 400, "y": 300, "w": 200, "h": 40}
        self.assertEqual(self.frame_box(control, []), control)

    def test_far_or_huge_labels_are_ignored(self):
        control = {"x": 400, "y": 300, "w": 200, "h": 40}
        far = {"x": 400, "y": 20, "w": 80, "h": 20}           # a heading far above
        wide = {"x": 0, "y": 270, "w": 1900, "h": 24}         # a legend spanning the page
        self.assertEqual(self.frame_box(control, [far, wide]), control)

    def test_clamped_to_the_viewport(self):
        control = {"x": 10, "y": 30, "w": 200, "h": 40}
        label = {"x": 10, "y": -6, "w": 80, "h": 20}
        self.assertEqual(self.frame_box(control, [label]), {"x": 10, "y": 0, "w": 200, "h": 70})


@unittest.skipUnless(shutil.which("node"), "node no está instalado")
class FormBoxTest(unittest.TestCase):
    """N10: the recorder logs the box of the field's form container (recorder.mjs formBox)."""

    ROW = {"tag": "div", "role": None, "fields": 2, "box": {"x": 660, "y": 300, "w": 600, "h": 70}}
    FORM = {"tag": "form", "role": None, "fields": 6, "box": {"x": 640.4, "y": 200.2, "w": 640, "h": 620}}
    MAIN = {"tag": "main", "role": None, "fields": 7, "box": {"x": 0, "y": 60, "w": 1920, "h": 1020}}

    def form_box(self, ancestors, viewport=(1920, 1080)):
        import json
        import subprocess
        script = (f"const {{ formBox }} = await import({json.dumps(RECORDER.as_uri())});"
                  f"console.log(JSON.stringify(formBox({json.dumps(ancestors)}, {json.dumps(list(viewport))})));")
        out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True,
                             check=True)
        return json.loads(out.stdout)

    def test_form_wins_over_a_closer_row_of_fields(self):
        self.assertEqual(self.form_box([self.ROW, self.FORM, self.MAIN]), {"x": 640, "y": 200, "w": 640, "h": 620})

    def test_dialog_and_fieldset_are_form_containers(self):
        dialog = {"tag": "div", "role": "dialog", "fields": 1, "box": {"x": 700, "y": 300, "w": 520, "h": 400}}
        fieldset = {"tag": "fieldset", "role": None, "fields": 1, "box": {"x": 720, "y": 340, "w": 480, "h": 200}}
        self.assertEqual(self.form_box([dialog, self.MAIN]), dialog["box"])
        self.assertEqual(self.form_box([fieldset, dialog]), fieldset["box"])

    def test_without_one_the_nearest_ancestor_with_two_fields(self):
        card = {"tag": "div", "role": None, "fields": 4, "box": {"x": 500, "y": 150, "w": 900, "h": 700}}
        single = {"tag": "div", "role": None, "fields": 1, "box": {"x": 520, "y": 300, "w": 400, "h": 80}}
        self.assertEqual(self.form_box([single, card, self.MAIN]), card["box"])

    def test_unrendered_body_or_lonely_fields_give_none(self):
        hidden = {"tag": "form", "role": None, "fields": 6, "box": None}             # display: contents
        body = {"tag": "body", "role": None, "fields": 3, "box": {"x": 0, "y": 0, "w": 1920, "h": 1080}}
        single = {"tag": "div", "role": None, "fields": 1, "box": {"x": 520, "y": 300, "w": 400, "h": 80}}
        self.assertIsNone(self.form_box([single, hidden, body]))
        self.assertIsNone(self.form_box([]))

    def test_clamped_to_the_viewport(self):
        tall = {"tag": "form", "role": None, "fields": 9, "box": {"x": -10, "y": 120, "w": 900, "h": 1400}}
        self.assertEqual(self.form_box([tall]), {"x": 0, "y": 120, "w": 890, "h": 960})

    def test_frame_box_is_unchanged(self):
        # PRESERVE: the C9 helper next to it keeps its result.
        self.assertEqual(FrameBoxTest.frame_box(self, {"x": 790, "y": 446, "w": 340, "h": 44},
                                                [{"x": 790, "y": 420, "w": 60, "h": 18}]),
                         {"x": 790, "y": 420, "w": 340, "h": 70})


if __name__ == "__main__":
    unittest.main()


class PartsContextTest(unittest.TestCase):
    """N16/N17: "Debería dividirse en partes" and "dejar claro cuándo se trabaja en el SRI y cuándo en Perseo":
    the timeline carries `parts` and each step's `part`/`context` for compose and qa."""

    def plan(self, parts):
        tut, video = tutorial_of(["nuevo"])
        if parts:
            tut["parts"] = [{"n": 1, "title": "Configurar la carpeta"}]
        video["steps"][0]["part"] = 1 if parts else None
        video["steps"][0]["context"] = "sri"
        actions = {"steps": [{"id": "nuevo", "t0": 0.0, "t1": 3.0,
                               "events": [{"type": "click", "t": 1.0, "selector": "#btn-new", **box(1377, 109)}]}]}
        return edit.plan_video(tut, video, actions, [], {"opening": 2.0, "nuevo": 2.0, "closing": 1.5})

    def test_parts_and_step_part_context_reach_the_timeline(self):
        tl = self.plan(parts=True)
        self.assertEqual(tl["parts"], [{"n": 1, "title": "Configurar la carpeta"}])
        self.assertEqual((tl["steps"][0]["part"], tl["steps"][0]["context"]), (1, "sri"))

    def test_no_parts_key_without_parts(self):
        self.assertNotIn("parts", self.plan(parts=False))
