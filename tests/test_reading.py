"""P4 (reglas/reglas-video.md §Parte 7, odd/tasks/ritmo-perseo.md T4): every on-screen text stays long enough to
read it. Part separators >= 1.5 s, every caption >= max(1.5, chars/15 + 0.4) s, the step chip never changes
before 1.5 s, and the fast voice tempo at most x1.05. edit owns the timing, compose schedules the captions by
reading time, lint estimates P1 with it and qa checks it.

Run: .venv/Scripts/python.exe -m unittest discover -s tests -v
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
import compose  # noqa: E402
import edit  # noqa: E402
import lint  # noqa: E402
import qa  # noqa: E402
import test_compose  # noqa: E402
import test_edit  # noqa: E402
import test_lint  # noqa: E402
import test_qa  # noqa: E402
import test_schema  # noqa: E402
from test_pace import with_pace  # noqa: E402


def need(text):
    return max(1.5, len(text) / 15 + 0.4)


# --- common -------------------------------------------------------------------------------------

class ReadingTimeTest(unittest.TestCase):
    def test_reading_seconds(self):
        self.assertAlmostEqual(common.reading_seconds("Haz clic en Consultar."), 22 / 15 + 0.4)
        self.assertAlmostEqual(common.reading_seconds("Abre el menú."), 1.5)          # the 1.5 s floor
        self.assertAlmostEqual(common.reading_seconds(""), 1.5)
        self.assertEqual((common.PART_SECONDS, common.CHIP_MIN), (1.5, 1.5))


class SchemaTempoTest(test_schema.YamlCase):
    def test_fast_tempo_is_at_most_1_05(self):
        self.assertEqual(common.FAST_TEMPO, 1.05)
        tut = self.load(with_pace(test_schema.BASE, max_seconds=45))
        self.assertEqual(common.videos(tut)[0]["tempo"], 1.05)
        self.assertRejects(with_pace(test_schema.BASE, tempo=1.1),
                           "tutorial.yaml: video tutorial: 'tempo' con pace: fast es como máximo 1.05 (P4)")
        self.assertEqual(common.videos(self.load(with_pace(test_schema.BASE, tempo=1.05)))[0]["tempo"], 1.05)
        # PRESERVE: a normal video may still declare up to 1.25.
        self.assertEqual(common.videos(self.load(with_pace(test_schema.BASE, "normal", tempo=1.1)))[0]["tempo"], 1.1)


# --- edit ---------------------------------------------------------------------------------------

def click_step(sid, t0, x=300):
    return {"id": sid, "t0": t0, "t1": t0 + 1.5, "events": [
        {"type": "click", "t": t0 + 0.7, "selector": f"#{sid}", **test_edit.box(x, 300)}]}


def parted(pace="fast"):
    """Two parts of two steps; each voice 0.3 s shorter than its caption's reading time (a quick read)."""
    narrations = [("abrir", "Haz clic en Configuración avanzada."), ("cambiar", "Haz clic en Cambiar carpeta."),
                  ("menu", "Haz clic en Consultar."), ("lista", "Haz clic en Descargar todo.")]
    tut, video = test_edit.video_of(narrations)
    tut["parts"] = [{"n": 1, "title": "Configurar"}, {"n": 2, "title": "Descargar"}]
    for step, part in zip(video["steps"], (1, 1, 2, 2)):
        step["part"] = part
    video["pace"] = pace
    video["closing"] = None
    actions = {"steps": [click_step(sid, 2.0 * i, 200 + 300 * i) for i, (sid, _) in enumerate(narrations)]}
    durations = {"opening": 1.5, **{sid: need(text) - 0.3 for sid, text in narrations}}
    return edit.plan_video(tut, video, actions, [], durations)


class EditReadingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tl = parted()

    def test_separator_has_its_own_1_5_s_before_the_part(self):
        steps = {s["id"]: s for s in self.tl["steps"]}
        self.assertEqual([(p["n"], p["start"], p["duration"]) for p in self.tl["parts"]],
                         [(1, steps["abrir"]["start"], 1.5), (2, steps["menu"]["start"], 1.5)])
        for sid in ("abrir", "menu"):
            step = steps[sid]
            with self.subTest(step=sid):
                # The voice, the click and the step's first caption all come after the separator.
                self.assertGreaterEqual(step["voice_start"], step["start"] + 1.5 - 1e-6)
                self.assertGreaterEqual(step["action_t"], step["start"] + 1.5 - 1e-6)
                self.assertGreaterEqual(min(e["t"] for e in step["events"]), step["start"] + 1.5 - 1e-6)
        # A step that does not open a part has no separator time.
        self.assertLess(steps["cambiar"]["voice_start"] - steps["cambiar"]["start"], 0.5)

    def test_step_lasts_its_captions_reading_time(self):
        for step in self.tl["steps"]:
            with self.subTest(step=step["id"]):
                end = step["start"] + step["duration"]
                self.assertGreaterEqual(end - step["voice_start"], need(step["narration"]) - 1e-3)
                self.assertGreater(need(step["narration"]), step["voice_duration"])   # the voice alone is shorter

    def test_chip_is_visible_1_5_s(self):
        tut, video = test_edit.video_of([("a", ""), ("b", "Haz clic en Guardar.")])
        video["pace"] = "fast"
        actions = {"steps": [{"id": "a", "t0": 0.0, "t1": 0.4, "events": [{"type": "focus", "t": 0.1}]},
                             click_step("b", 0.4)]}
        tl = edit.plan_video(tut, video, actions, [], {"opening": 1.5, "a": 0.0, "b": 1.6, "closing": 1.2})
        self.assertGreaterEqual(tl["steps"][0]["duration"], 1.5 - 1e-6)

    def test_separator_is_not_a_voice_gap(self):
        self.assertFalse([w for w in self.tl["warnings"] if "silencio" in w], self.tl["warnings"])

    def test_normal_pace_gets_the_same_separator_and_reading_time(self):
        tl = parted("normal")
        self.assertEqual([p["duration"] for p in tl["parts"]], [1.5, 1.5])
        menu = next(s for s in tl["steps"] if s["id"] == "menu")
        self.assertGreaterEqual(menu["voice_start"], menu["start"] + 1.5 - 1e-6)

    def test_without_parts_nothing_is_inserted(self):
        # PRESERVE: a video without parts starts its first step's voice at the lead.
        tut, video = test_edit.video_of([("nuevo", "Haz clic en Nuevo contacto.")])
        actions = {"steps": [click_step("nuevo", 0.0)]}
        tl = edit.plan_video(tut, video, actions, [], {"opening": 1.5, "nuevo": 2.6, "closing": 1.2})
        self.assertNotIn("parts", tl)
        step = tl["steps"][0]
        self.assertLess(step["voice_start"] - step["start"], 0.5)


# --- compose ------------------------------------------------------------------------------------

def texts_of(blocks):
    return [" ".join(lines) for _, lines in blocks]


class ComposeReadingTest(unittest.TestCase):
    def test_captions_follow_reading_time(self):
        blocks = compose.caption_blocks("Haz clic en XML Desde el RIDE. Revisa el resumen.", None)
        out = compose.schedule(blocks, 1.0, 2.0, 0.8, 9.0)
        self.assertEqual([lines for _, _, lines, _ in out], [lines for _, lines in blocks])
        self.assertAlmostEqual(out[0][0], 1.0)
        for (t0, t1, lines, _), text in zip(out, texts_of(blocks)):
            self.assertGreaterEqual(t1 - t0, need(text) - 1e-6, text)
        self.assertAlmostEqual(out[1][0], out[0][1])                        # back to back, no blank band
        self.assertAlmostEqual(compose.caption_span(texts_of(blocks), 2.0), need(texts_of(blocks)[0])
                               + need(texts_of(blocks)[1]))

    def test_a_slow_voice_keeps_its_own_pace(self):
        # PRESERVE: a voice longer than the reading time still sets the captions' times.
        blocks = compose.caption_blocks("Haz clic en Consultar.", None)
        out = compose.schedule(blocks, 0.0, 4.0, 0.0, 6.0)
        self.assertGreaterEqual(out[0][1] - out[0][0], 4.0 - 1e-6)

    def test_separators_last_1_5_s_and_hide_no_caption(self):
        for pace in ("fast", "normal"):
            tl = test_compose.parts_timeline()
            tl["pace"] = pace
            lay = compose.plan(tl, test_compose.BRAND)
            seps = [i for i in lay["items"] if str(i.get("card", "")).startswith("part-")]
            with self.subTest(pace=pace):
                self.assertEqual([round(i["t1"] - i["t0"], 3) for i in seps], [1.5, 1.5])
                for cap in (i for i in lay["items"] if i["kind"] == "caption"):
                    for sep in seps:
                        self.assertLessEqual(min(cap["t1"], sep["t1"]) - max(cap["t0"], sep["t0"]), 1e-6,
                                             (cap["text"], sep["text"]))

    def test_edit_timeline_reads_through_compose_and_qa(self):
        lay = compose.plan(parted(), test_compose.BRAND)
        captions = [i for i in lay["items"] if i["kind"] == "caption"]
        self.assertEqual(len(captions), 4)
        for cap in captions:
            self.assertGreaterEqual(cap["t1"] - cap["t0"], need(cap["text"]) - 1e-3, cap["text"])
        rows = qa.check_reading(lay, parted())
        self.assertEqual([r["status"] for r in rows], ["PASS", "PASS", "PASS"], rows)


# --- lint ---------------------------------------------------------------------------------------

class LintReadingTest(unittest.TestCase):
    def test_estimate_counts_reading_time_and_separators(self):
        data = copy.deepcopy(test_lint.BASE)
        data["steps"] = [{"id": "menu", "narration": "Haz clic en Configuración avanzada de la carpeta.",
                          "actions": [{"click": "#m"}]}]
        video = {"id": "v", "type": "TUT", "steps": "all", "opening": {"narration": ""}, "pace": "fast"}
        text = data["steps"][0]["narration"]
        floor = 1.5 + 0.2 + need(text)                   # opening floor + fast lead + reading
        self.assertGreater(need(text), lint.words(text) / lint.BUDGET_WPS / common.FAST_TEMPO)
        self.assertAlmostEqual(lint.estimate(data, video, budget=True), floor, places=3)
        data["parts"] = [{"n": 1, "title": "Uno"}]
        data["steps"][0]["part"] = 1
        self.assertAlmostEqual(lint.estimate(data, video, budget=True), floor + 1.5, places=3)

    def test_fast_tempo_over_1_05_is_an_error(self):
        errors = lint.lint_data(with_pace(test_lint.BASE, tempo=1.1))[0]
        self.assertIn("[P4] videos.tutorial.tempo: con pace: fast es como máximo 1.05", errors)
        self.assertFalse([e for e in lint.lint_data(with_pace(test_lint.BASE, tempo=1.05))[0] if "tempo" in e])
        # PRESERVE: a normal video may declare 1.1.
        self.assertFalse([e for e in lint.lint_data(with_pace(test_lint.BASE, "normal", tempo=1.1))[0]
                          if "tempo" in e])


# --- qa -----------------------------------------------------------------------------------------

class QaReadingTest(unittest.TestCase):
    def setUp(self):
        self.tl = test_qa.fixture("tutorial", "timeline.json")
        self.lay = test_qa.fixture("tutorial", "layout.json")

    def rows(self):
        return {r["id"]: r for r in qa.check_layout(self.lay, self.tl, test_qa.TUTORIAL) if r["rule"] == "P4"}

    def test_fixture_passes(self):
        rows = self.rows()
        self.assertEqual(sorted(rows), ["P4.captions", "P4.chips", "P4.separators"])
        self.assertEqual({r["status"] for r in rows.values()}, {"PASS"}, rows)

    def test_short_caption_fails(self):
        cap = test_qa.item(self.lay, "caption")
        cap["t1"] = cap["t0"] + 1.2
        text = cap["text"]
        row = self.rows()["P4.captions"]
        self.assertEqual(row["status"], "FAIL")
        self.assertEqual(row["detail"], f"«{text}» 1.20 s visible (mínimo {need(text):.2f} s)")

    def test_caption_under_a_separator_is_not_visible(self):
        cap = test_qa.item(self.lay, "caption")
        self.lay["items"].append({"kind": "card", "card": "part-1", "text": "Parte 1: Uno", "t0": cap["t0"],
                                  "t1": cap["t0"] + 1.5})
        row = self.rows()["P4.captions"]
        self.assertEqual(row["status"], "FAIL")
        self.assertIn(f"«{cap['text']}» {cap['t1'] - cap['t0'] - 1.5:.2f} s visible", row["detail"])

    def test_short_separator_fails(self):
        self.lay["items"].append({"kind": "card", "card": "part-1", "text": "Parte 1: Uno", "t0": 2.0, "t1": 2.8})
        row = self.rows()["P4.separators"]
        self.assertEqual(row["status"], "FAIL")
        self.assertEqual(row["detail"], "«Parte 1: Uno» 0.80 s (mínimo 1.5 s)")

    def test_separator_is_no_voice_gap(self):
        tl = parted()
        self.assertEqual(test_qa.status(qa.check_timeline(tl), "A2.voice_gaps"), "PASS")
        menu = next(s for s in tl["steps"] if s["id"] == "menu")
        late = dict(menu, voice_start=menu["voice_start"] + 1.0)   # 1.0 s more silence after the separator
        rows = qa.check_timeline(dict(tl, steps=[late if s is menu else s for s in tl["steps"]]))
        detail = next(r["detail"] for r in rows if r["id"] == "A2.voice_gaps")
        self.assertRegex(detail, r"\(\d\.\d s sin los 1\.5 s del separador\)$")
        for part in tl["parts"]:
            part.pop("duration")              # without edit's separator times the same silence is a gap
        self.assertEqual(test_qa.status(qa.check_timeline(tl), "A2.voice_gaps"), "FAIL")

    def test_chip_changing_before_1_5_s_fails(self):
        chips = [i for i in self.lay["items"] if i["kind"] == "chip"]
        self.assertGreater(len(chips), 1)
        chips[0]["t1"] = chips[0]["t0"] + 1.0
        row = self.rows()["P4.chips"]
        self.assertEqual(row["status"], "FAIL")
        self.assertEqual(row["detail"], f"«{chips[0]['text']}» 1.00 s antes de cambiar (mínimo 1.5 s)")


if __name__ == "__main__":
    unittest.main()
