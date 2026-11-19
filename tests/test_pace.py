"""Round five (reglas/reglas-video.md §Parte 7, odd/tasks/ritmo-perseo.md S1-S3): `videos[].pace: fast` and
`videos[].max_seconds` across the pipeline. P1 total cap, P2 fast pace (replaces TUT4), P3 less zoom.
Without `pace` every tool keeps its previous behavior (the PRESERVE tests below).

Run: .venv/Scripts/python.exe -m unittest discover -s tests -v
"""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))   # the fixtures of the other test modules
import common  # noqa: E402
import compose  # noqa: E402
import edit  # noqa: E402
import lint  # noqa: E402
import qa  # noqa: E402
import tts  # noqa: E402
import test_compose  # noqa: E402
import test_edit  # noqa: E402
import test_lint  # noqa: E402
import test_qa  # noqa: E402
import test_schema  # noqa: E402
import test_tts  # noqa: E402

def FAST_PACE():
    return edit.pace("TUT", "fast")


def NORMAL_PACE():
    return edit.pace("TUT")


def with_pace(data, pace="fast", **extra):
    data = copy.deepcopy(data)
    data["videos"][0].update({"pace": pace, **extra})
    return data


# --- schema (common) --------------------------------------------------------------------------

class SchemaPaceTest(test_schema.YamlCase):
    def test_invalid_pace_max_seconds_and_tempo_are_rejected(self):
        self.assertRejects(with_pace(test_schema.BASE, "lento"),
                           "tutorial.yaml: video tutorial: 'pace' tiene que ser normal o fast (P2)")
        for bad in (0, -3, "45", True):
            with self.subTest(max_seconds=bad):
                self.assertRejects(with_pace(test_schema.BASE, max_seconds=bad),
                                   "tutorial.yaml: video tutorial: 'max_seconds' tiene que ser un número "
                                   "mayor que 0 (P1)")
        for bad in (0.9, 1.3, "1.1"):
            with self.subTest(tempo=bad):
                self.assertRejects(with_pace(test_schema.BASE, tempo=bad),
                                   "tutorial.yaml: video tutorial: 'tempo' tiene que ser un número entre 1 y "
                                   "1.25 (P2)")

    def test_videos_carry_pace_max_seconds_and_tempo(self):
        tut = self.load(with_pace(test_schema.BASE, max_seconds=45))
        fast, redes = common.videos(tut)
        self.assertEqual((fast["pace"], fast["max_seconds"], fast["tempo"]), ("fast", 45, common.FAST_TEMPO))
        self.assertEqual(common.FAST_TEMPO, 1.05)   # P4 (round five, second pass): at most x1.05
        # PRESERVE: a video without pace is normal, has no cap and keeps the voice as synthesized.
        self.assertEqual((redes["pace"], redes["max_seconds"], redes["tempo"]), ("normal", None, 1.0))
        tut = self.load(with_pace(test_schema.BASE, tempo=1.03))
        self.assertEqual(common.videos(tut)[0]["tempo"], 1.03)


# --- tts ----------------------------------------------------------------------------------------

class TtsTempoTest(unittest.TestCase):
    """P2: the fast voice is sped up (atempo) after trimming and before measuring; the raw API cache is shared."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(setattr, common, "PROJECTS", common.PROJECTS)
        common.PROJECTS = Path(self.tmp.name)
        self.pdir = common.PROJECTS / "crm"
        self.pdir.mkdir()
        self.tone = test_tts.padded_tone(Path(self.tmp.name) / "tone.wav")
        self.calls = []

        def fake(client, model, text, voice, style):
            self.calls.append(text)
            return self.tone

        for name, value in (("synthesize", fake), ("make_client", lambda: object())):
            self.addCleanup(setattr, tts, name, getattr(tts, name))
            setattr(tts, name, value)

    def write(self, **video):
        data = copy.deepcopy(test_tts.TUTORIAL)
        data["videos"][0].update(video)
        (self.pdir / "tutorial.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")

    def test_fast_clips_are_sped_up_after_trimming(self):
        self.write(pace="fast")
        result = tts.tts("crm")
        trimmed = 1.0 + 2 * tts.TRIM_PAD
        for name, seconds in result["tutorial"].items():
            with self.subTest(clip=name):
                self.assertAlmostEqual(seconds, trimmed / common.FAST_TEMPO, delta=0.05)
                wav = self.pdir / "audio" / "voice" / "tutorial" / f"{name}.wav"
                self.assertAlmostEqual(common.media_duration(wav), seconds, delta=0.01)
        # PRESERVE: the normal video keeps the trimmed length, and a text in both videos is billed once.
        self.assertAlmostEqual(result["redes"]["closing"], trimmed, delta=0.04)
        self.assertEqual(len(self.calls), 7)

    def test_tempo_is_part_of_the_clip_cache_key(self):
        self.write(pace="fast")
        tts.tts("crm")
        self.write(pace="fast", tempo=1.02)
        again = tts.tts("crm")
        self.assertEqual(len(self.calls), 7)          # a new tempo re-derives from the raw cache, no API call
        self.assertAlmostEqual(again["tutorial"]["opening"], (1.0 + 2 * tts.TRIM_PAD) / 1.02, delta=0.05)

    def test_offline_fast_clips_follow_the_tempo(self):
        self.write(pace="fast")
        result = tts.tts("crm", offline=True)
        text = test_tts.TUTORIAL["videos"][0]["opening"]["narration"]
        self.assertAlmostEqual(result["tutorial"]["opening"], tts.estimate_seconds(text) / common.FAST_TEMPO,
                               delta=0.05)
        self.assertAlmostEqual(result["redes"]["opening"],
                               tts.estimate_seconds(test_tts.TUTORIAL["videos"][1]["opening"]["narration"]), delta=0.05)


# --- edit ---------------------------------------------------------------------------------------

def length(pieces):
    return sum(p["d"] for p in pieces)


class EditFastTest(unittest.TestCase):
    def test_fast_pace_profile(self):
        self.assertEqual(FAST_PACE()["hold"], {"result": 0.5, "highlight": 0.5})   # P2 replaces TUT4's 1.5 s
        self.assertEqual(FAST_PACE()["max"], 8.0)
        self.assertEqual(NORMAL_PACE()["hold"], {"result": 1.5, "highlight": 1.5})   # PRESERVE: TUT4
        self.assertEqual(NORMAL_PACE()["max"], 3.0)

    def test_highlight_holds_half_a_second(self):
        pieces = edit.build_pieces(0.0, 4.3, [{"type": "highlight", "t": 4.0}], [], FAST_PACE(), 1.0)
        self.assertAlmostEqual(length(pieces) - edit.warp(pieces, 4.0), 0.5, places=6)

    def test_long_wait_is_cut_to_its_first_and_last_state(self):
        # A download: the click, ~24 s of progress, the summary. Fast: 8x and the middle cut, ~1 s on screen.
        evs = [{"type": "click", "t": 1.0}, {"type": "result", "t": 25.0}]
        pieces = edit.build_pieces(0.0, 26.0, evs, [], FAST_PACE(), 2.0)
        shown = edit.warp(pieces, 25.0) - edit.warp(pieces, 1.0)
        self.assertAlmostEqual(shown, edit.FAST_WAIT, delta=0.01)
        between = [p for p in pieces if p["c0"] >= 1.0 and p["c1"] <= 25.0 and p["c1"] > p["c0"]]
        self.assertEqual([p["kind"] for p in between], ["idle", "cut", "idle"])
        self.assertEqual((between[0]["c0"], between[-1]["c1"]), (1.0, 25.0))   # the initial and the final state
        for p in pieces:
            if p["kind"] == "idle" and p["d"] > 0:
                self.assertLessEqual((p["c1"] - p["c0"]) / p["d"], 8.0 + 1e-9)
        # PRESERVE: the normal pace plays the whole wait at 3x.
        normal = edit.build_pieces(0.0, 26.0, evs, [], NORMAL_PACE(), 1.0)
        self.assertAlmostEqual(edit.warp(normal, 25.0) - edit.warp(normal, 1.0), 24.0 / 3.0, places=6)
        self.assertFalse([p for p in normal if p["kind"] == "cut"])

    def test_step_tail_is_minimal(self):
        evs = [{"type": "focus", "t": 0.3}, {"type": "focus", "t": 0.6}]
        fast = edit.plan_step(0.0, 1.0, evs, [], 4.0, FAST_PACE())
        self.assertAlmostEqual(fast["duration"], 4.0 + FAST_PACE()["lead"] + FAST_PACE()["tail"])
        self.assertLessEqual(FAST_PACE()["lead"] + FAST_PACE()["tail"], 0.3 + 1e-9)
        normal = edit.plan_step(0.0, 1.0, evs, [], 4.0, NORMAL_PACE())
        self.assertAlmostEqual(normal["duration"], 4.0 + edit.LEAD + edit.TAIL)   # PRESERVE

    def test_cards_are_shorter(self):
        self.assertLessEqual(edit.plan_card("opening", "TUT", 1.7, "fast")["duration"], 2.0)
        self.assertIsNone(edit.plan_card("opening", "TUT", 1.7, "fast")["warning"])
        self.assertAlmostEqual(edit.plan_card("opening", "TUT", 1.0, "fast")["duration"], 1.4)
        self.assertIn("opening", edit.plan_card("opening", "TUT", 2.0, "fast")["warning"])
        self.assertLessEqual(edit.plan_card("requirements", "TUT", 2.0, "fast")["duration"], 2.5)
        self.assertIn("requirements", edit.plan_card("requirements", "TUT", 2.5, "fast")["warning"])
        # PRESERVE: the normal opening lasts at least 2 s.
        self.assertAlmostEqual(edit.plan_card("opening", "TUT", 1.0)["duration"], 2.0)

    def test_new_screen_needs_less_room(self):
        self.assertLess(compose.establish_room("click", True), compose.establish_room("click"))
        self.assertAlmostEqual(compose.establish_room("click"), 1.6)   # PRESERVE
        # P3: a form shot is its own establishing shot, so only the C3 lead is left.
        self.assertAlmostEqual(compose.establish_room("type", True, form=True), compose.LEAD_BY_TYPE["type"])
        self.assertAlmostEqual(compose.establish_room("type", form=True), compose.establish_room("type"))

    def test_first_field_of_a_new_screen_waits_only_for_its_lead(self):
        form = {"x": 300, "y": 150, "w": 900, "h": 500}
        evs = [{"type": "click", "t": 0.5, "screen_c": 0.6},
               {"type": "type", "t": 0.8, "t_end": 1.2, "chars": 5, "form_box": form}]
        held = {}
        for name, pc in (("fast", FAST_PACE()), ("normal", NORMAL_PACE())):
            pieces = edit.build_pieces(0.0, 2.0, evs, [], pc, 2.0)
            edit.leave_room(pieces, evs, 0.0, 2.0, None, name == "fast")
            held[name] = edit.warp(pieces, 0.8) - edit.warp(pieces, 0.6)
        self.assertAlmostEqual(held["fast"], compose.LEAD_BY_TYPE["type"], delta=0.02)
        self.assertGreaterEqual(held["normal"], compose.establish_room("type") - 1e-6)   # PRESERVE

    def test_surface_click_is_the_main_action(self):
        evs = [{"type": "open", "t": 1.0, "surface": "popup"},
               {"type": "click", "t": 2.0, "surface": "popup", "selector": "#boton4"}]
        self.assertIs(edit.main_action(evs, fast=True), evs[1])
        self.assertIs(edit.main_action(evs), evs[0])           # PRESERVE
        single = [{"type": "open", "t": 1.0, "surface": "popup"}, {"type": "focus", "t": 1.5, "surface": "popup"}]
        self.assertIs(edit.main_action(single, fast=True), single[0])


def download(pace=None):
    tut, video = test_edit.video_of([("bajar", "Haz clic en XML Desde el RIDE. Revisa el resumen.")])
    if pace:
        video["pace"] = pace
    actions = {"steps": [{"id": "bajar", "t0": 0.0, "t1": 12.0, "events": [
        {"type": "open", "t": 1.0, "surface": "popup"},
        {"type": "click", "t": 2.0, "surface": "popup", "selector": "#boton4", **test_edit.box(40, 300)},
        {"type": "result", "t": 9.0, "surface": "popup", "selector": ".estadisticas", **test_edit.box(40, 420)}]}],
        "surfaces": {"popup": {"size": [460, 660], "dpr": 2, "anchor": "top-right", "dir": "surfaces/popup",
                               "windows": [{"t0": 1.0, "t1": 12.0}]}}}
    # P4: a real read of the two sentences (3.67 s at x1.05 in perseo-xml-v2) is about their reading time.
    return edit.plan_video(tut, video, actions, [], {"opening": 1.5, "bajar": 3.6, "closing": 1.5})


class EditFastTimelineTest(unittest.TestCase):
    def test_timeline_carries_pace_and_warns_over_max_seconds(self):
        tut, video = test_edit.video_of([("nuevo", "Haz clic en Nuevo contacto.")])
        video.update(pace="fast", max_seconds=3)
        actions = {"steps": [{"id": "nuevo", "t0": 0.0, "t1": 3.0, "events": [
            {"type": "click", "t": 1.0, "selector": "#btn", **test_edit.box(100, 100)}]}]}
        tl = edit.plan_video(tut, video, actions, [], {"opening": 1.5, "nuevo": 1.6, "closing": 1.2})
        self.assertEqual((tl["pace"], tl["max_seconds"]), ("fast", 3))
        self.assertEqual([w for w in tl["warnings"] if "(P1)" in w],
                         [f"el video dura {tl['total']:.1f} s y el máximo es 3 s (P1): acorta la narración o "
                          "quita pasos"])
        video.pop("max_seconds")
        video.pop("pace")
        tl = edit.plan_video(tut, video, actions, [], {"opening": 1.5, "nuevo": 1.6, "closing": 1.2})
        self.assertEqual(tl["pace"], "normal")
        self.assertNotIn("max_seconds", tl)

    def test_summary_sentence_starts_with_the_summary(self):
        # "Haz clic en XML Desde el RIDE. Revisa el resumen.": the click in the popup is the instruction's action
        # (N1) and the second sentence starts when the summary shows (N14), so no silence > 1 s after it (A2).
        tl = download("fast")
        step = tl["steps"][0]
        click = next(e for e in step["events"] if e["type"] == "click")
        result = next(e for e in step["events"] if e["type"] == "result")
        self.assertAlmostEqual(step["action_t"], click["t"])
        self.assertLessEqual(step["instruction_end"], click["t"] + edit.SYNC_AFTER + 1e-6)   # N1
        self.assertAlmostEqual(step["effect_t"], result["t"], places=3)
        self.assertLessEqual(step["effect_start"], result["t"] + 1e-6)
        self.assertGreater(step["voice_start"] + step["voice_duration"], result["t"])   # said over the summary
        self.assertLessEqual(step["start"] + step["duration"] - (step["voice_start"] + step["voice_duration"]),
                             edit.GAP + 1e-6)
        # PRESERVE: the normal pace keeps the open as the main action and has no summary sync.
        normal = download()["steps"][0]
        self.assertAlmostEqual(normal["action_t"], next(e["t"] for e in normal["events"] if e["type"] == "open"))
        self.assertIsNone(normal["effect_t"])


# --- compose ------------------------------------------------------------------------------------

def fast(tl):
    tl = copy.deepcopy(tl)
    tl["pace"] = "fast"
    return tl


def frame_s(layout, t):
    return compose.frame_at(layout["camera"], t)["s"]


class ComposeFastTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tl = test_compose.fixture("tutorial")
        cls.fast = compose.plan(fast(cls.tl), test_compose.BRAND)
        cls.normal = compose.plan(cls.tl, test_compose.BRAND)

    def test_stage_zoom_ranges(self):
        stage = compose.Stage("16:9", pace="fast")
        self.assertEqual((stage.detail_min, stage.detail_max, stage.legible, stage.form_min, stage.form_pref),
                         (1.15, 1.4, 1.0, 1.0, 1.2))
        normal = compose.Stage("16:9")
        self.assertEqual((normal.detail_min, normal.detail_max, normal.legible, normal.form_min, normal.form_pref),
                         (1.4, 1.8, 1.3, 1.3, 1.5))   # PRESERVE

    def test_detail_is_1_15_to_1_4_and_nothing_above(self):
        for seg in self.fast["camera"]:
            self.assertLessEqual(seg["scale"], 1.4 + 1e-6, seg)
        events = [e for s in self.tl["steps"] for e in s["events"]
                  if e["type"] in ("click", "result", "highlight") and not e.get("form_box")]
        self.assertTrue(events)
        for ev in events:
            s = frame_s(self.fast, ev["t"] + (0.5 if ev["type"] == "highlight" else 0))
            with self.subTest(ev=ev["type"]):
                self.assertGreaterEqual(s, 1.15 - 1e-6)
                self.assertLessEqual(s, 1.4 + 1e-6)

    def test_form_is_framed_whole_at_1_0_to_1_2(self):
        forms = [s for s in self.fast["camera"] if s["kind"] == "form"]
        self.assertTrue(forms)
        for seg in forms:
            self.assertGreaterEqual(seg["scale"], 1.0 - 1e-6)
            self.assertLessEqual(seg["scale"], 1.2 + 1e-6)
            fr = {"x": seg["x"], "y": seg["y"], "s": seg["scale"]}
            self.assertTrue(test_compose.inside(test_compose.mapped(seg["form_box"], fr), self.fast["viewport"]))

    def test_form_shot_is_the_establishing_shot(self):
        # P3 "el plano de ubicación puede ser el propio plano del formulario": the screen that opens on the form cuts
        # straight to the whole form; PRESERVE: the normal pace shows the full screen first.
        at = test_compose.screen_changes(self.tl)[0]
        first = next(s for s in self.fast["camera"] if abs(s["t0"] - at) < 1e-3)
        self.assertEqual(first["kind"], "form", self.fast["camera"])
        normal = next(s for s in self.normal["camera"] if abs(s["t0"] - at) < 1e-3)
        self.assertEqual((normal["kind"], normal.get("reason")), ("context", "establishing"))

    def test_wide_form_fits_the_width_at_1_0(self):
        stage = compose.Stage("16:9", pace="fast")
        form = {"x": -60, "y": 200, "w": 2040, "h": 400}
        boxes = [{"x": 100, "y": 260, "w": 400, "h": 70}, {"x": 1300, "y": 400, "w": 400, "h": 70}]
        fr = stage.form_frame(form, boxes)
        self.assertEqual(fr["s"], 1.0)
        self.assertTrue(stage.holds(fr, boxes))

    def test_popup_is_whole_and_in_detail(self):
        lay = compose.plan(fast(test_compose.surface_timeline()), test_compose.BRAND)
        result = next(i for i in lay["items"] if i["kind"] == "result")
        fr = compose.frame_at(lay["camera"], (result["t0"] + result["t1"]) / 2)
        self.assertGreaterEqual(fr["s"], 1.15 - 1e-6)
        self.assertLessEqual(fr["s"], 1.4 + 1e-6)
        self.assertTrue(test_compose.inside(compose.Stage.map(test_compose.AREA, fr), lay["viewport"]))

    def test_part_separators_last_1_5_s(self):
        lay = compose.plan(fast(test_compose.parts_timeline()), test_compose.BRAND)
        cards = [i for i in lay["items"] if str(i.get("card", "")).startswith("part-")]
        self.assertEqual(len(cards), 2)
        for card in cards:
            self.assertAlmostEqual(card["t1"] - card["t0"], 1.5)   # P4 replaces P2's 0.8 s
        normal = compose.plan(test_compose.parts_timeline(), test_compose.BRAND)   # P4: 1.5 s in every pace
        self.assertEqual(sorted(round(i["t1"] - i["t0"], 3) for i in normal["items"]
                                if str(i.get("card", "")).startswith("part-")), [1.5, 1.5])

    def test_band_under_a_separator_may_be_occluded(self):
        # The separator opens its part over the first step (N16): that step's chip, badge and caption are hidden by
        # design, so hyperframes check must not call them occluded text (a 2.7 s chip got one sample, under it).
        html, lay = compose.build(fast(test_compose.parts_timeline()), test_compose.BRAND)
        seps = [(i["t0"], i["t1"]) for i in lay["items"] if str(i.get("card", "")).startswith("part-")]
        layers = [i for i in lay["items"] if i["kind"] in ("chip", "caption")]
        under = [i for i in layers if any(i["t0"] < b and a < i["t1"] for a, b in seps)]
        self.assertTrue(under)
        # hyperframes only excuses an occluder that carries the flag (allowsOcclusionOf): the separator scene does
        # (a 1.5 s separator over the chip failed the check, perseo-xml-v2 T4).
        for n in (1, 2):
            self.assertIn(f'id="part-{n}" class="clip scene" data-layout-allow-occlusion', html)
        self.assertEqual(html.count("data-layout-allow-occlusion"), len(under) + len(seps))
        plain, _ = compose.build(test_compose.fixture("tutorial"), test_compose.BRAND)   # PRESERVE: no parts
        self.assertNotIn("data-layout-allow-occlusion", plain)

    def test_no_still_framing_over_2_5_s(self):
        excluded = qa.cards(self.tl)
        spots = [i for i in self.fast["items"] if i["kind"] == "spotlight"]
        row = qa.check_static(self.fast["camera"], "TUT", excluded, spots, fast=True)
        self.assertEqual(row["status"], "PASS", row["detail"])

    def test_layout_records_pace_and_legible_scale(self):
        self.assertEqual((self.fast["pace"], self.fast["legible_scale"]), ("fast", 1.0))
        self.assertEqual(self.normal["pace"], "normal")
        self.assertNotIn("legible_scale", self.normal)      # PRESERVE: qa falls back to compose's format floor


# --- lint ---------------------------------------------------------------------------------------

class LintPaceTest(unittest.TestCase):
    def errors(self, data):
        return lint.lint_data(data)[0]

    def warnings(self, data):
        return lint.lint_data(data)[1]

    def test_estimate_over_max_seconds_is_an_error(self):
        data = with_pace(test_lint.BASE, "normal", max_seconds=5)
        estimate = lint.estimate(data, data["videos"][0], budget=True)
        self.assertEqual([e for e in self.errors(data) if e.startswith("[P1]")],
                         [f"[P1] videos.tutorial: duración estimada ~{estimate:.0f} s y el máximo es 5 s "
                          "(max_seconds); acorta la narración o quita pasos"])
        self.assertFalse([e for e in self.errors(with_pace(test_lint.BASE, "normal", max_seconds=300))
                          if e.startswith("[P1]")])
        self.assertFalse([e for e in self.errors(test_lint.BASE) if e.startswith("[P1]")])   # PRESERVE

    def test_budget_is_a_lower_bound_of_the_trimmed_voice(self):
        # P1 is an error, so its estimate may not exceed what tts measures: perseo-xml-v2 "En el SRI, abre el menú."
        # (6 words) was 2.15 s trimmed, where the range estimate (1.9 words/s + 0.5 s per clip) says 3.66 s.
        data = copy.deepcopy(test_lint.BASE)
        data["steps"] = [{"id": "menu", "narration": "En el SRI, abre el menú.", "actions": [{"click": "#m"}]}]
        video = {"id": "v", "type": "TUT", "steps": "all", "opening": {"narration": ""}}
        # opening floor + the clip, or (P4) the lead and the caption's reading time when that is longer
        read = edit.LEAD + common.reading_seconds("En el SRI, abre el menú.")
        self.assertLessEqual(lint.estimate(data, video, budget=True), 1.5 + max(2.15, read) + 1e-9)
        self.assertAlmostEqual(lint.estimate(data, video), 1.5 + lint.seconds("En el SRI, abre el menú."))   # PRESERVE

    def test_estimate_uses_the_voice_tempo(self):
        normal, quick = with_pace(test_lint.BASE, "normal"), with_pace(test_lint.BASE)
        slow = lint.estimate(normal, normal["videos"][0], budget=True)
        sped = lint.estimate(quick, quick["videos"][0], budget=True)
        self.assertLess(sped, slow)
        limit = (slow + sped) / 2
        self.assertTrue([e for e in self.errors(with_pace(test_lint.BASE, "normal", max_seconds=limit))
                         if e.startswith("[P1]")])
        self.assertFalse([e for e in self.errors(with_pace(test_lint.BASE, max_seconds=limit)) if e.startswith("[P1]")])

    def test_invalid_pace_and_max_seconds(self):
        self.assertIn("[P2] videos.tutorial.pace: 'lento' (normal | fast)",
                      self.errors(with_pace(test_lint.BASE, "lento")))
        self.assertIn("[P1] videos.tutorial.max_seconds: tiene que ser un número de segundos mayor que 0",
                      self.errors(with_pace(test_lint.BASE, max_seconds="45")))

    def test_fast_opening_over_2_s_warns(self):
        data = with_pace(test_lint.BASE)
        data["videos"][0]["opening"]["narration"] = "Aprendes a crear contactos nuevos en tu cuenta hoy."
        self.assertTrue([w for w in self.warnings(data) if w.startswith("[P2] videos.tutorial.opening")])
        short = with_pace(test_lint.BASE)
        short["videos"][0]["opening"]["narration"] = "Crea contactos."
        self.assertFalse([w for w in self.warnings(short) if w.startswith("[P2] videos.tutorial.opening")])
        self.assertFalse([w for w in self.warnings(with_pace(test_lint.BASE, "normal")) if w.startswith("[P2]")])


# --- qa -----------------------------------------------------------------------------------------

class QaPaceTest(unittest.TestCase):
    def setUp(self):
        self.tl = test_qa.fixture("tutorial", "timeline.json")
        self.lay = test_qa.fixture("tutorial", "layout.json")

    def checks(self, pace=None):
        tl = dict(self.tl, pace=pace) if pace else self.tl
        return qa.check_layout(self.lay, tl, test_qa.TUTORIAL)

    def status(self, check_id, pace=None):
        return test_qa.status(self.checks(pace), check_id)

    def test_P1_total_over_max_seconds_fails(self):
        self.tl["max_seconds"] = 5
        rows = qa.check_timeline(self.tl)
        self.assertEqual(test_qa.status(rows, "P1.max_seconds"), "FAIL")
        self.assertEqual(next(r["detail"] for r in rows if r["id"] == "P1.max_seconds"),
                         "6.0 s (máximo 5 s, max_seconds)")
        self.tl["max_seconds"] = 45
        self.assertEqual(test_qa.status(qa.check_timeline(self.tl), "P1.max_seconds"), "PASS")
        self.tl.pop("max_seconds")
        self.assertNotIn("P1.max_seconds", {r["id"] for r in qa.check_timeline(self.tl)})   # PRESERVE

    def test_detail_floor_is_1_15_and_ceiling_1_4(self):
        cam = self.lay["camera"]
        cam[3].update(scale=1.2, t1=4.0)
        cam.insert(4, {"t0": 4.0, "t1": 5.0, "scale": 1.25, "kind": "detail"})
        for check_id in ("R1.detail", "C1.context"):
            self.assertEqual(self.status(check_id), "FAIL", check_id)     # PRESERVE: 1.4x floor
            self.assertEqual(self.status(check_id, "fast"), "PASS", check_id)
        cam[3]["scale"] = 1.5
        self.assertEqual(self.status("C1.zoom"), "PASS")
        self.assertEqual(self.status("C1.zoom", "fast"), "FAIL")

    def test_C8_limit_is_2_5_s(self):
        # detail 1.9-5.0 = 3.1 s with the same framing
        self.assertEqual(self.status("C8.static"), "PASS")
        self.assertEqual(self.status("C8.static", "fast"), "FAIL")

    def test_C8_spotlight_jumping_to_another_target_is_a_change(self):
        # perseo-xml-v2: the menu (hamburger, then FACTURACIÓN once it opens) is one 3.1 s framing; the outline jumps
        # to the next item at 10.39 s (N13: not before the click that reveals it), a visual change.
        spot = {"kind": "spotlight", "color": test_qa.PURPLE, "dim": 0.2, "step": "guardar", "selector": "#a"}
        self.lay["items"] += [dict(spot, t0=1.9, t1=3.4, rect=[100, 100, 200, 50], group=0),
                              dict(spot, t0=3.4, t1=5.0, rect=[400, 100, 200, 50], group=1, selector="#b")]
        self.assertEqual(self.status("C8.static", "fast"), "PASS")
        self.lay["items"][-1]["rect"] = [100, 100, 200, 50]          # the same target again: no change
        self.assertEqual(self.status("C8.static", "fast"), "FAIL")

    def test_C7_form_shot_opens_the_screen(self):
        self.tl["steps"][1]["events"][0]["screen_at"] = 3.4
        self.lay["items"] = [i for i in self.lay["items"] if i["kind"] != "result"]
        cam = self.lay["camera"]
        cam[3:4] = [{"t0": 1.9, "t1": 3.4, "scale": 1.3, "kind": "detail"},
                    {"t0": 3.4, "t1": 5.0, "scale": 1.1, "kind": "form", "x": 0, "y": -100,
                     "form_box": dict(test_qa.FORM)}]
        self.assertEqual(self.status("C7.establishing"), "FAIL")
        self.assertEqual(self.status("C7.establishing", "fast"), "PASS")

    def test_form_wider_than_the_viewport_is_cropped_beyond_the_used_fields(self):
        wide = {"x": -40, "y": 200, "w": 2000, "h": 500}
        fields = [test_qa.field("#c-nombre", "type", 2.0, 600, 230, t_end=2.3, form=wide),
                  test_qa.field("#c-apellido", "type", 2.4, 980, 230, t_end=2.7, form=wide)]
        self.tl["steps"][0]["events"] += fields
        cam = self.lay["camera"]
        cam[3:4] = [{"t0": 1.9, "t1": 3.0, "scale": 1.0, "kind": "form", "x": 0, "y": -150, "form_box": dict(wide)},
                    {"t0": 3.0, "t1": 5.0, "scale": 1.3, "kind": "detail"}]
        self.lay["items"] += test_qa.spotlights(fields, cam, 3.0)
        self.assertEqual(self.status("N12.form_fields"), "FAIL")     # PRESERVE
        self.assertEqual(self.status("N12.form_fields", "fast"), "PASS")
        fields[1]["frame_box"]["x"] = 1900                           # a used field cut by the edge still fails
        self.assertEqual(self.status("N12.form_fields", "fast"), "FAIL")

    def test_form_shot_usual_range_is_1_0_to_1_2(self):
        cam = self.lay["camera"]
        cam[2]["scale"] = 1.0                      # the move into the form shot
        cam[3:4] = [{"t0": 1.9, "t1": 3.0, "scale": 1.0, "kind": "form", "x": 0, "y": -100,
                     "form_box": dict(test_qa.FORM)},
                    {"t0": 3.0, "t1": 5.0, "scale": 1.3, "kind": "detail"}]
        self.assertEqual(self.status("C1.zoom"), "WARN")          # PRESERVE: usual 1.1-1.5x
        self.assertEqual(self.status("C1.zoom", "fast"), "PASS")


if __name__ == "__main__":
    unittest.main()
