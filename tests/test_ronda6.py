"""Round six (odd/tasks/perseo-ronda6.md T1; reglas/reglas-video.md §Parte 8): D3 pronunciation map, D4 download
folder shown on chrome://settings (press_visual on "Change", show_download_dir writes it into the row: display only,
the parent's decision after settingsPrivate refused the pref), more than one follow: tab per take, and D5 one voice tone (batch cache key, leveled clips, qa pitch/loudness spread).

Run: .venv/Scripts/python.exe -m unittest tests.test_ronda6 -v
"""
import copy
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import yaml

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(Path(__file__).resolve().parent))   # test_tts (batch_audio) also under -m tests.test_ronda6
import capture  # noqa: E402
import common  # noqa: E402
import lint  # noqa: E402
import qa  # noqa: E402
import test_tts  # noqa: E402
import tts  # noqa: E402

RECORDER = TOOLS / "capture" / "recorder.mjs"
USER_DIR = "C:\\Users\\Prueba\\Downloads\\Perseo XML"


def minimal(steps=None, **top):
    data = {
        "title": "T",
        "steps": steps or [{"id": "a", "narration": "Haz clic en Consultar.", "actions": [{"click": "#a"}]}],
        "videos": [{"id": "tutorial", "type": "TUT", "steps": "all", "opening": {"narration": "Aprendes algo."}}],
    }
    data.update(top)
    return data


def settings_steps(*actions):
    return [{"id": "carpeta", "narration": "Abre Carpeta de descargas.",
             "actions": [{"click": "#configure-folder"}, {"follow": "tab"}, *actions, {"back": "main"}]}]


# ---------- D3: pronunciation ----------

class SpokenTextTest(unittest.TestCase):
    """D3 "RIDE se pronuncia RI DE no raid": whole-word, case-sensitive replacements for the voice only."""

    MAP = {"RIDE": "ri de"}

    def test_whole_words_are_replaced(self):
        self.assertEqual(common.spoken_text("Haz clic en XML desde el RIDE.", self.MAP), "Haz clic en XML desde el ri de.")
        self.assertEqual(common.spoken_text("RIDE, luego otro RIDE.", self.MAP), "ri de, luego otro ri de.")

    def test_case_and_word_boundaries_are_kept(self):
        for text in ("Los RIDES quedan.", "El ride queda.", "PRIDE queda.", "RIDEX queda."):
            with self.subTest(text=text):
                self.assertEqual(common.spoken_text(text, self.MAP), text)

    def test_longer_terms_first_and_no_map(self):
        self.assertEqual(common.spoken_text("SRI en línea y SRI.", {"SRI": "ese erre i", "SRI en línea": "ese erre i en línea"}),
                         "ese erre i en línea y ese erre i.")
        self.assertEqual(common.spoken_text("El RIDE.", None), "El RIDE.")


class PronunciationSchemaTest(unittest.TestCase):
    def test_valid_map_loads(self):
        common.validate_tutorial(minimal(pronunciation={"RIDE": "ri de"}))

    def test_bad_maps_are_rejected(self):
        for bad in (["RIDE"], {"RIDE": ""}, {"": "ri de"}, {"RIDE": 3}, {"RIDE": "RIDE"}):
            with self.subTest(bad=bad), self.assertRaises(common.PipelineError) as ctx:
                common.validate_tutorial(minimal(pronunciation=bad))
            self.assertIn("'pronunciation'", str(ctx.exception))
            self.assertIn("(D3)", str(ctx.exception))

    def test_lint_reports_the_map(self):
        errors, _ = lint.lint_data(minimal(pronunciation={"RIDE": ""}))
        self.assertTrue(any(e.startswith("[D3] pronunciation") for e in errors), errors)
        errors, _ = lint.lint_data(minimal(pronunciation={"RIDE": "ri de"}))
        self.assertFalse(any(e.startswith("[D3]") for e in errors), errors)


def padded_tone(path: Path, freq=200, volume_db=0.0, seconds=1.0) -> bytes:
    """A voice-like clip (fundamental + 2 harmonics) with silence around it, like the API returns."""
    expr = f"0.5*sin(2*PI*{freq}*t)+0.25*sin(4*PI*{freq}*t)+0.12*sin(6*PI*{freq}*t)"
    common.ffmpeg("-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono:d=0.3",
                  "-f", "lavfi", "-i", f"aevalsrc={expr}:s=24000:d={seconds}",
                  "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono:d=0.3",
                  "-filter_complex", f"[1]volume={volume_db}dB[v];[0][v][2]concat=n=3:v=0:a=1",
                  "-ac", "1", "-c:a", "pcm_s16le", str(path))
    return path.read_bytes()


TUTORIAL = {
    "title": "T",
    "pronunciation": {"RIDE": "ri de"},
    "steps": [
        {"id": "ride", "narration": "Haz clic en XML desde el RIDE.", "actions": [{"click": "#a"}]},
        {"id": "nuevo", "narration": "Haz clic en Nuevo.", "actions": [{"click": "#b"}]},
        {"id": "guardar", "narration": "Guarda el contacto.", "actions": [{"result": "#t"}]},
    ],
    "videos": [
        {"id": "tutorial", "type": "TUT", "steps": "all", "pace": "fast", "tempo": 1.05,
         "opening": {"narration": "Aprendes a descargar.", "text": "x"}},
        {"id": "redes", "type": "RED", "steps": ["guardar"],
         "opening": {"narration": "¿Feria?", "text": "x"},
         "closing": {"narration": "Mira el perfil.", "text": "x"}},
    ],
}


class FakeApiCase(unittest.TestCase):
    """tts.tts against a fake Gemini: records every text sent; a batch is one tone per line (12 dB quieter for the
    line with "Nuevo"), a single text a padded tone. `split = False` returns one tone for a batch (no pauses)."""

    split = True

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(setattr, common, "PROJECTS", common.PROJECTS)
        common.PROJECTS = Path(self.tmp.name)
        self.pdir = common.PROJECTS / "px"
        self.pdir.mkdir()
        self.calls = []

        def fake(client, model, text, voice, style):
            self.calls.append(text)
            path = Path(self.tmp.name) / f"api{len(self.calls)}.wav"
            if not self.split:
                return padded_tone(path)
            return test_tts.batch_audio(path, text, volume_db=lambda line: -12.0 if "Nuevo" in line else 0.0)

        for name, value in (("synthesize", fake), ("make_client", lambda: object())):
            self.addCleanup(setattr, tts, name, getattr(tts, name))
            setattr(tts, name, value)

    def write(self, data):
        (self.pdir / "tutorial.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")

    def run_tts(self, data):
        self.write(data)
        with redirect_stdout(io.StringIO()):
            return tts.tts("px")


class PronunciationTtsTest(FakeApiCase):
    def test_the_voice_reads_the_spoken_form_and_captions_keep_the_term(self):
        self.run_tts(TUTORIAL)
        self.assertIn("Haz clic en XML desde el ri de.", self.calls[0].split("\n\n"))
        self.assertFalse(any("RIDE" in c for c in self.calls))
        tut = common.load_tutorial("px")
        self.assertEqual(common.videos(tut)[0]["steps"][0]["narration"], "Haz clic en XML desde el RIDE.")

    def test_a_new_reading_is_synthesized_again(self):
        self.run_tts(TUTORIAL)
        before = len(self.calls)
        data = copy.deepcopy(TUTORIAL)
        data["pronunciation"] = {"RIDE": "ri dé"}
        self.run_tts(data)
        self.assertIn("Haz clic en XML desde el ri dé.", self.calls[before].split("\n\n"))


class OneVoiceToneTest(FakeApiCase):
    """D5 "mantene un solo tono de voz": a video's clips come from one batch and are leveled alike."""

    def test_one_request_per_video_cut_into_its_clips(self):
        result = self.run_tts(TUTORIAL)
        self.assertEqual(len(self.calls), 2)               # one request per video, never a clip alone
        self.assertEqual(self.calls[0].split("\n\n"), ["Aprendes a descargar.", "Haz clic en XML desde el ri de.",
                                                       "Haz clic en Nuevo.", "Guarda el contacto."])
        for name, seconds in result["tutorial"].items():
            with self.subTest(clip=name):   # each line is a 1 s tone: trimmed, sped up x1.05
                self.assertAlmostEqual(seconds, (1.0 + 2 * tts.TRIM_PAD) / 1.05, delta=0.06)

    def test_one_changed_narration_resynthesizes_the_whole_video_only(self):
        self.run_tts(TUTORIAL)
        data = copy.deepcopy(TUTORIAL)
        data["steps"][1]["narration"] = "Haz clic en Nuevo contacto."
        self.run_tts(data)
        self.assertEqual(len(self.calls), 3)               # the tutorial again in one request, redes from the cache
        self.assertEqual(len(self.calls[2].split("\n\n")), 4)
        self.run_tts(data)
        self.assertEqual(len(self.calls), 3)               # unchanged batch: all from the cache

    def test_tempo_and_reading_are_part_of_the_batch(self):
        self.run_tts(TUTORIAL)
        data = copy.deepcopy(TUTORIAL)
        data["videos"][0]["tempo"] = 1.0
        self.run_tts(data)
        self.assertEqual(len(self.calls), 3)

    def test_a_batch_without_pauses_falls_back_to_one_request_per_clip(self):
        self.split = False
        out = io.StringIO()
        self.write(TUTORIAL)
        with redirect_stdout(out):
            tts.tts("px")
        self.assertEqual(len(self.calls), 2 + 4 + 3)
        self.assertIn("aviso (D5) tutorial: no pude cortar la tanda", out.getvalue())

    def test_every_clip_is_leveled_to_the_same_loudness(self):
        self.run_tts(TUTORIAL)
        voice = self.pdir / "audio" / "voice" / "tutorial"
        levels = {p.stem: common.measure_loudness(p)[0] for p in voice.glob("*.wav")}
        self.assertEqual(set(levels), {"opening", "ride", "nuevo", "guardar"})
        for name, lufs in levels.items():
            with self.subTest(clip=name):
                self.assertAlmostEqual(lufs, tts.VOICE_LUFS, delta=0.7)


class SplitPointsTest(unittest.TestCase):
    """D5: a batch is cut at the pauses nearest to where each clip ends by its characters."""

    # Measured on a real 5-line batch (rehearsal 2026-11-18): 4 boundaries + one pause inside the 4th line.
    PAUSES = [(0.0, 0.28), (2.25, 2.94), (4.96, 5.42), (7.53, 8.11), (10.12, 10.66), (12.74, 13.21), (14.25, 14.48)]
    TEXTS = ["Aprendes a descargar tus XML.", "Ingresa a la plataforma del SRI.", "Luego abre Perseo XML.",
             "Haz clic en XML desde el ri de. Transforma los ri de en XML.", "Haz clic en Consultar."]

    def test_the_pause_inside_a_clip_is_skipped(self):
        cuts = tts.split_points(self.PAUSES, 14.48, self.TEXTS)
        self.assertEqual([round(c, 3) for c in cuts], [2.595, 5.19, 7.82, 12.975])

    def test_not_enough_pauses(self):
        self.assertIsNone(tts.split_points(self.PAUSES[:3], 14.48, self.TEXTS))

    def test_a_cut_far_from_its_share_is_refused(self):
        self.assertIsNone(tts.split_points([(0.3, 0.5)], 14.0, ["Una frase bastante larga para su parte.", "Otra."]))

    def test_one_clip_needs_no_cut(self):
        self.assertEqual(tts.split_points([], 3.0, ["Sola."]), [])


class VoiceToneQaTest(unittest.TestCase):
    """D5: qa compares each clip's mean pitch (F0) and loudness with the video median."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def clips(self, *specs):
        out = []
        for i, (freq, vol) in enumerate(specs):
            path = self.dir / f"c{i}.wav"
            padded_tone(path, freq=freq, volume_db=vol)
            out.append((f"c{i}", path))
        return out

    def rows(self, clips):
        return {r["id"]: r for r in qa.check_voice_tone(clips)}

    def test_pitch_estimate(self):
        (_, path), = self.clips((200, 0))
        self.assertAlmostEqual(qa.clip_pitch(path), 200, delta=4)

    def test_same_tone_passes_with_the_spread(self):
        rows = self.rows(self.clips((200, 0), (200, 0), (202, 0), (200, -1)))
        self.assertEqual(rows["D5.pitch"]["status"], "PASS")
        self.assertEqual(rows["D5.loudness"]["status"], "PASS")
        self.assertIn("st", rows["D5.pitch"]["detail"])
        self.assertIn("LU", rows["D5.loudness"]["detail"])
        self.assertEqual(rows["D5.pitch"]["rule"], "D5")

    def test_a_clip_three_semitones_higher_warns(self):
        # Intonation alone moves a clip ~3 st inside one request (perseo-xml-v3): listen, do not fail.
        rows = self.rows(self.clips((200, 0), (200, 0), (200, 0), (238, 0)))
        self.assertEqual(rows["D5.pitch"]["status"], "WARN")
        self.assertIn("c3 +3.0 st", rows["D5.pitch"]["detail"])
        self.assertEqual(rows["D5.loudness"]["status"], "PASS")

    def test_a_clip_five_semitones_higher_fails(self):
        rows = self.rows(self.clips((200, 0), (200, 0), (200, 0), (267, 0)))
        self.assertEqual(rows["D5.pitch"]["status"], "FAIL")
        self.assertIn("c3", rows["D5.pitch"]["detail"])

    def test_a_clip_six_lu_quieter_fails(self):
        rows = self.rows(self.clips((200, 0), (200, 0), (200, 0), (200, -6)))
        self.assertEqual(rows["D5.loudness"]["status"], "FAIL")
        self.assertIn("c3", rows["D5.loudness"]["detail"])

    def test_video_clips_in_durations_order(self):
        vdir = self.dir / "audio" / "voice" / "tutorial"
        vdir.mkdir(parents=True)
        for name in ("opening", "a"):
            padded_tone(vdir / f"{name}.wav")
        (vdir / "durations.json").write_text(json.dumps({"opening": 1.0, "a": 1.0, "silent": 0.0}), encoding="utf-8")
        self.assertEqual([n for n, _ in qa.voice_clips(self.dir, "tutorial")], ["opening", "a"])
        self.assertEqual(qa.voice_clips(self.dir, "otro"), [])


# ---------- D4: schema and capture.py ----------

class DownloadDirSchemaTest(unittest.TestCase):
    def test_valid_on_the_followed_tab(self):
        common.validate_tutorial(minimal(settings_steps(
            {"press_visual": "#changeDownloadsPath"},
            {"show_download_dir": {"path": "%USERPROFILE%\\Downloads\\Perseo XML\\Emitidos"}})))

    def test_needs_the_settings_tab(self):
        steps = [{"id": "a", "narration": "Haz clic en Consultar.",
                  "actions": [{"click": "#a"}, {"show_download_dir": {"path": "C:\\x"}}]}]
        with self.assertRaises(common.PipelineError) as ctx:
            common.validate_tutorial(minimal(steps))
        self.assertIn("'show_download_dir' va en la pestaña seguida (follow: tab antes)", str(ctx.exception))

    def test_shape(self):
        for bad in ("C:\\x", {"path": ""}, {"path": "C:\\x", "mkdir": True}, {"path": "C:\\x", "result": 3}):
            with self.subTest(bad=bad), self.assertRaises(common.PipelineError) as ctx:
                common.validate_tutorial(minimal(settings_steps({"show_download_dir": bad})))
            self.assertIn("'show_download_dir' necesita {path: CARPETA, result?: SELECTOR} (D4)", str(ctx.exception))

    def test_press_visual_needs_a_selector(self):
        with self.assertRaises(common.PipelineError) as ctx:
            common.validate_tutorial(minimal(settings_steps({"press_visual": 3})))
        self.assertIn("'press_visual' necesita un selector", str(ctx.exception))

    def test_follow_and_back_twice_in_one_take(self):
        steps = settings_steps({"press_visual": "#c"}) + [
            {"id": "otra", "narration": "Abre Carpeta de descargas.",
             "actions": [{"click": "#configure-folder"}, {"follow": "tab"}, {"back": "main"}]}]
        common.validate_tutorial(minimal(steps))

    def test_lint_counts_press_visual_as_a_user_action(self):
        data = minimal([{"id": "cambiar", "narration": "Haz clic en Change.", "part": 1,
                         "actions": [{"press_visual": "#c"}]},
                        {"id": "b", "narration": "Haz clic en Consultar.", "part": 1, "actions": [{"click": "#a"}]}],
                       parts=[{"n": 1, "title": "Uno"}])
        errors, _ = lint.lint_data(data)
        self.assertFalse(any(e.startswith("[N15]") for e in errors), errors)


class DownloadDirCaptureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = self.tmp.name
        os.environ["TUTORIAL_TEST_HOME"] = self.home
        self.addCleanup(os.environ.pop, "TUTORIAL_TEST_HOME", None)

    def resolved(self, path):
        steps = settings_steps({"show_download_dir": {"path": path}})
        out = io.StringIO()
        with redirect_stdout(out):
            actions = capture.resolve_actions(steps)[0]["actions"]
        self.assertEqual(out.getvalue(), "")
        return next(a["show_download_dir"] for a in actions if "show_download_dir" in a)

    def test_env_vars_are_expanded_in_python_and_nothing_is_created(self):
        arg = self.resolved("%TUTORIAL_TEST_HOME%\\Downloads\\Perseo XML\\Emitidos")
        self.assertEqual(arg, {"path": self.home + "\\Downloads\\Perseo XML\\Emitidos"})
        self.assertEqual(list(Path(self.home).iterdir()), [])     # display only: no folder is made

    def test_a_missing_variable_names_only_the_variable(self):
        with self.assertRaises(common.PipelineError) as ctx:
            self.resolved("%TUTORIAL_NO_EXISTE%\\x")
        self.assertIn("TUTORIAL_NO_EXISTE", str(ctx.exception))
        self.assertNotIn("\\x", str(ctx.exception))


# ---------- D4: recorder ----------

FAKES = r"""
const state = { clicks: [], moves: [], newPages: 0, closed: 0, rowTexts: [] };
const row = { _t: "C:\\Users\\Prueba\\Downloads",
  get textContent() { return this._t; }, set textContent(v) { this._t = v; state.rowTexts.push(v); } };
globalThis.document = { querySelector: (sel) => (sel === "#defaultDownloadPath" ? row : null), querySelectorAll: () => [],
  documentElement: { get textContent() { return "Location " + row._t; }, querySelectorAll: () => [] } };
const FOUND = { box: { x: 100, y: 100, w: 200, h: 40 }, labels: [], ancestors: [], target_ok: true,
  target_text: "C:\\Users\\Prueba\\Downloads" };
let tabs = [];
function fakePage(url, onClick) {
  const page = { targetId: "t" + Math.random(), label: null, url: async () => url,
    mouse: { move: async (x, y) => state.moves.push([x, y]),
             click: async (x, y) => { state.clicks.push([x, y]); if (onClick) onClick(); } },
    keyboard: { press: async () => {}, type: async () => {} },
    goto: async (u) => { url = u; }, waitForLoadState: async () => {},
    close: async () => { state.closed++; }, evaluate: async () => [1920, 1080],
    cdp: async (method, params) => {
      if (method === "Page.captureScreenshot") { await new Promise((r) => setTimeout(r, 40)); return { data: "" }; }
      if (method !== "Runtime.evaluate") return {};
      const e = params.expression;
      if (e.includes("return shownTargets")) return { result: { value: 1 } };
      if (e.includes("return await findTarget")) return { result: { value: e.includes('"#missing"') ? null : FOUND } };
      try { return { result: { value: await (0, eval)(e) } }; } catch (err) { return { exceptionDetails: {} }; }
    } };
  return page;
}
const openSettings = () => { tabs.push({ targetId: "s" + tabs.length, active: true,
  page: fakePage("chrome://settings/downloads") }); };
const main = fakePage("https://srienlinea.sri.gob.ec/", openSettings);
main.targetId = "main";
tabs.push({ targetId: "main", label: "p1", page: main, active: false });
const task = { pages: async () => [main], tabs: async () => tabs, adopt: async (p) => p, page: () => main,
  newPage: async () => { state.newPages++; return fakePage("about:blank"); } };
const rec = { now: () => 0, setPage() {}, clock: null };
const ctx = { task, main, page: main, rec, surfaces: {}, state: {}, known: new Set(["main"]), censor: null,
  censorCfg: { text: [], flags: "i" }, viewport: [1920, 1080], followed: null, track: null, regions: [] };
const settings = (dir) => ({ id: "carpeta-" + dir, hold_ms: 0, actions: [
  { click: "#configure-folder" }, { follow: "tab" }, { press_visual: "#changeDownloadsPath" },
  { show_download_dir: { path: "C:\\Users\\Prueba\\Downloads\\Perseo XML\\" + dir } }, { back: "main" }] });
"""


@unittest.skipUnless(shutil.which("node"), "node no está instalado")
class RecorderDownloadDirTest(unittest.TestCase):
    """D4 "no mostraste tambien como configurar correctamente la carpeta de descargas" (display only, L2/L4)."""

    def node(self, body: str):
        script = (f"const R = await import({json.dumps(RECORDER.as_uri())});\n"
                  "const logged = [];\n"
                  "for (const k of ['log', 'info', 'warn', 'error', 'debug']) console[k] = (...a) => logged.push(a.join(' '));\n"
                  f"{FAKES}\n"
                  f"const result = await (async () => {{ {body} }})();\n"
                  "process.stdout.write(JSON.stringify({ result, logged }));")
        out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True,
                             encoding="utf-8", timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr[-2000:])
        data = json.loads(out.stdout)
        self.assertFalse([line for line in data["logged"] if "Prueba" in line], "una ruta llegó al log")
        return data["result"]

    def test_two_folders_two_follows_shown_in_the_row(self):
        res = self.node("""
          const log = await R.runSteps(ctx, rec, [settings("Emitidos"), settings("Recibidos")]);
          return { log, clicks: state.clicks.length, closed: state.closed, rowTexts: state.rowTexts,
                   newPages: state.newPages };
        """)
        steps = res["log"]
        self.assertEqual([s["id"] for s in steps], ["carpeta-Emitidos", "carpeta-Recibidos"])
        for step in steps:
            ev = step["events"]
            self.assertEqual([e["type"] for e in ev], ["click", "goto", "click", "result", "goto"])
            self.assertEqual([ev[1].get("tab"), ev[4].get("tab")], ["follow", "main"])
            self.assertTrue(ev[2]["visual"])
            self.assertEqual(ev[2]["selector"], "#changeDownloadsPath")
            self.assertEqual(ev[3]["selector"], "#defaultDownloadPath")
            self.assertTrue(ev[3]["download_dir"])
            self.assertNotIn("target_text", ev[3])
        # The fake gives every target the path as its text: the folder row never keeps it.
        self.assertNotIn("Prueba", json.dumps([e for s in steps for e in s["events"] if e["type"] == "result"]))
        self.assertEqual(res["clicks"], 2)                         # press_visual never clicks "Change"
        self.assertEqual(res["rowTexts"], [USER_DIR + "\\Emitidos", USER_DIR + "\\Recibidos"])
        self.assertEqual(res["closed"], 2)                         # each followed settings tab closed by back
        self.assertEqual(res["newPages"], 0)

    def test_a_missing_row_stops_the_take_without_the_path(self):
        out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, out, True)
        res = self.node(f"""
          const steps = [{{ id: "carpeta", hold_ms: 0, actions: [{{ click: "#configure-folder" }}, {{ follow: "tab" }},
            {{ show_download_dir: {{ path: "C:\\\\Users\\\\Prueba\\\\x", result: "#otra-fila" }} }}] }}];
          const r = await R.take(task, {{ outDir: {json.dumps(Path(out).as_posix())}, steps, viewport: [1920, 1080] }});
          return {{ failure: r.failure }};
        """)
        self.assertIn("#otra-fila", res["failure"])
        self.assertNotIn("Prueba", res["failure"])
        actions = (Path(out) / "actions.json").read_text(encoding="utf-8")
        self.assertNotIn("Prueba", actions)
        self.assertNotIn("download_dir", json.loads(actions))


if __name__ == "__main__":
    unittest.main()
