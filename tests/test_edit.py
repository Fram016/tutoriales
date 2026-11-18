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
        evs = [{"type": "click", "t": 1.0}]
        plan = edit.plan_step(0.0, 7.0, evs, [], 2.5, TUT)
        self.assertLessEqual(plan["duration"] - 2.5, 1.0 + 1e-9)
        self.assertAlmostEqual(plan["voice_offset"], edit.LEAD)

    def test_long_voice_holds_last_frame(self):
        plan = edit.plan_step(0.0, 1.0, [{"type": "click", "t": 0.5}], [], 4.0, TUT)
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
        tut, video = tutorial_of(["abrir", "ver", "cerrar"])
        actions = {"steps": [
            {"id": "abrir", "t0": 0.0, "t1": 0.5, "events": [{"type": "click", "t": 0.2, **box(100, 100)}]},
            {"id": "ver", "t0": 10.0, "t1": 10.0, "events": [{"type": "result", "t": 10.0, **box(300, 300)},
                                                          {"type": "highlight", "t": 10.0, **box(300, 400)}]},
            {"id": "cerrar", "t0": 11.0, "t1": 11.5, "events": [{"type": "click", "t": 11.2, **box(500, 100)}]},
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


if __name__ == "__main__":
    unittest.main()
