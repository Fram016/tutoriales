"""Round seven (odd/tasks/perseo-instalacion.md T1; reglas/reglas-video.md §Parte 9: I1-I3): the install of the
extension shown honestly in the page (I2: `show_text` relabels a button for display only, `simulate_dialog` draws
Chrome's confirmation dialog, `remove_dialog` takes it away, a top-level `hide` for the store's "switch browser"
notices, the "chrome" context badge) and takes merged into one capture (I3: tools/merge_takes.py).

Run: .venv/Scripts/python.exe -m unittest tests.test_ronda7 -v
"""
import base64
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import capture  # noqa: E402
import common  # noqa: E402
import compose  # noqa: E402
import merge_takes  # noqa: E402

RECORDER = TOOLS / "capture" / "recorder.mjs"
PYTHON = sys.executable

DIALOG = {"title": '¿Quieres agregar "Perseo XML"?', "body": ["Puede:", "Leer y cambiar tus datos en srienlinea.sri.gob.ec"],
          "buttons": ["Agregar extensión", "Cancelar"]}


def minimal(steps, **top):
    data = {"title": "T", "steps": steps,
            "videos": [{"id": "tutorial", "type": "TUT", "steps": "all", "opening": {"narration": "Aprendes algo."}}]}
    data.update(top)
    return data


def install_steps(*extra):
    return [{"id": "agregar", "narration": "Haz clic en Agregar a Chrome.", "context": "chrome",
             "actions": [{"show_text": {"sel": "button.add", "text": "Agregar a Chrome"}},
                         {"press_visual": "button.add"},
                         {"simulate_dialog": dict(DIALOG)},
                         {"press_visual": "#sim-btn-0"},
                         {"remove_dialog": True},
                         *extra]}]


# ---------- schema ----------

class InstallSchemaTest(unittest.TestCase):
    """I2: display-only actions are validated like the others; their errors name the expected shape."""

    def test_valid_install_step(self):
        common.validate_tutorial(minimal(install_steps()))

    def test_show_text_shape(self):
        for bad in ("Agregar", {"sel": "b"}, {"text": "x"}, {"sel": "", "text": "x"}, {"sel": "b", "text": 3},
                    {"sel": "b", "text": "x", "otro": 1}, {"sel": "b", "text": "x", "watch": "si"}):
            steps = [{"id": "a", "narration": "x", "actions": [{"show_text": bad}]}]
            with self.subTest(bad=bad), self.assertRaises(common.PipelineError) as ctx:
                common.validate_tutorial(minimal(steps))
            self.assertIn("'show_text' necesita {sel: SELECTOR, text: TEXTO, watch?: true} (I2)", str(ctx.exception))
        common.validate_tutorial(minimal([{"id": "a", "narration": "x",
                                           "actions": [{"show_text": {"sel": "b", "text": "x", "watch": True}}]}]))

    def test_simulate_dialog_shape(self):
        bads = [{**DIALOG, "title": ""}, {**DIALOG, "buttons": []}, {**DIALOG, "buttons": ["Ok", 3]},
                {**DIALOG, "body": 4}, {**DIALOG, "primary": 2}, {**DIALOG, "anchor": ""}, {**DIALOG, "icon": 1},
                {**DIALOG, "otro": True}, "dialogo"]
        for bad in bads:
            steps = [{"id": "a", "narration": "x", "actions": [{"simulate_dialog": bad}, {"remove_dialog": True}]}]
            with self.subTest(bad=bad), self.assertRaises(common.PipelineError) as ctx:
                common.validate_tutorial(minimal(steps))
            self.assertIn("'simulate_dialog' necesita {title, body?, buttons: [...], primary?, anchor?, icon?} (I2)",
                          str(ctx.exception))

    def test_dialog_open_and_close_in_order(self):
        lone = [{"id": "a", "narration": "x", "actions": [{"remove_dialog": True}]}]
        with self.assertRaises(common.PipelineError) as ctx:
            common.validate_tutorial(minimal(lone))
        self.assertIn("'remove_dialog' sin un 'simulate_dialog' antes (I2)", str(ctx.exception))
        twice = [{"id": "a", "narration": "x", "actions": [{"simulate_dialog": DIALOG}, {"simulate_dialog": DIALOG}]}]
        with self.assertRaises(common.PipelineError) as ctx:
            common.validate_tutorial(minimal(twice))
        self.assertIn("'simulate_dialog' con otro diálogo abierto (usa remove_dialog antes; I2)", str(ctx.exception))
        bad_arg = [{"id": "a", "narration": "x", "actions": [{"simulate_dialog": DIALOG}, {"remove_dialog": "x"}]}]
        with self.assertRaises(common.PipelineError) as ctx:
            common.validate_tutorial(minimal(bad_arg))
        self.assertIn("'remove_dialog' solo admite true", str(ctx.exception))

    def test_chrome_context_and_its_badge(self):
        common.validate_tutorial(minimal(install_steps()))
        self.assertEqual(compose.context_label({"product": "Perseo XML"}, "chrome"), "En Chrome")
        # PRESERVE: the existing labels are unchanged.
        self.assertEqual(compose.context_label({"product": "Perseo XML"}, "sri"), "En el SRI")
        self.assertEqual(compose.context_label({"product": "Perseo XML"}, "extension"), "En Perseo XML")
        with self.assertRaises(common.PipelineError) as ctx:
            common.validate_tutorial(minimal([{"id": "a", "narration": "x", "context": "tienda", "actions": []}]))
        self.assertIn("'context' tiene que ser sri, extension, page o chrome (N17)", str(ctx.exception))

    def test_top_level_hide(self):
        common.validate_tutorial(minimal(install_steps(), hide=[".gSrP5d"]))
        for bad in (".a", [""], [3]):
            with self.subTest(bad=bad), self.assertRaises(common.PipelineError) as ctx:
                common.validate_tutorial(minimal(install_steps(), hide=bad))
            self.assertIn("'hide' tiene que ser una lista de selectores CSS (I2)", str(ctx.exception))


# ---------- capture.py ----------

class InstallCaptureConfigTest(unittest.TestCase):
    """The take of a part (install.yaml) goes to its own take dir; the dialog icon travels as a data URL."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(setattr, common, "PROJECTS", common.PROJECTS)
        common.PROJECTS = Path(self.tmp.name)
        self.pdir = common.PROJECTS / "px"
        (self.pdir / "brand").mkdir(parents=True)
        self.icon = b"\x89PNG\r\n\x1a\nfake"
        (self.pdir / "brand" / "ext-icon48.png").write_bytes(self.icon)

    def test_icon_becomes_a_data_url(self):
        steps = install_steps()
        steps[0]["actions"][2]["simulate_dialog"]["icon"] = "brand/ext-icon48.png"
        out = io.StringIO()
        with redirect_stdout(out):
            actions = capture.resolve_actions(steps, self.pdir)[0]["actions"]
        dialog = next(a["simulate_dialog"] for a in actions if "simulate_dialog" in a)
        self.assertEqual(dialog["icon"], "data:image/png;base64," + base64.b64encode(self.icon).decode())
        self.assertEqual(dialog["title"], DIALOG["title"])
        self.assertEqual(out.getvalue(), "")

    def test_a_missing_icon_names_the_file(self):
        steps = install_steps()
        steps[0]["actions"][2]["simulate_dialog"]["icon"] = "brand/no-existe.png"
        with self.assertRaises(common.PipelineError) as ctx:
            capture.resolve_actions(steps, self.pdir)
        self.assertIn("simulate_dialog: no existe el ícono brand/no-existe.png", str(ctx.exception))

    def test_config_file_and_take_dir(self):
        import yaml
        (self.pdir / "tutorial.yaml").write_text(yaml.safe_dump(minimal(install_steps())), encoding="utf-8")
        install = {"title": "Instalar", "app_url": "https://chromewebstore.google.com/", "hide": [".gSrP5d"],
                   "steps": install_steps()}
        (self.pdir / "install.yaml").write_text(yaml.safe_dump(install, allow_unicode=True), encoding="utf-8")
        tut, out_dir, config = capture.take_config("px", "install.yaml", "takes/install")
        self.assertEqual(tut["title"], "Instalar")
        self.assertEqual(out_dir, self.pdir / "takes" / "install")
        self.assertEqual(config["outDir"], out_dir.as_posix())
        self.assertEqual(config["hide"], [".gSrP5d"])
        self.assertEqual(config["startUrl"], "https://chromewebstore.google.com/")
        # PRESERVE: the default is tutorial.yaml into capture/, without a page hide.
        tut, out_dir, config = capture.take_config("px")
        self.assertEqual(out_dir, self.pdir / "capture")
        self.assertEqual(config["hide"], [])
        with self.assertRaises(common.PipelineError) as ctx:
            capture.take_config("px", "install.yaml", "../fuera")
        self.assertIn("--out tiene que quedar dentro del proyecto", str(ctx.exception))

    def test_a_previous_take_in_a_take_dir_is_moved_aside(self):
        take = self.pdir / "takes" / "install"
        take.mkdir(parents=True)
        (take / "actions.json").write_text("{}", encoding="utf-8")
        dest = capture.keep_previous_take(self.pdir, now=0, out_dir=take)
        self.assertEqual(dest.parent, take.parent)
        self.assertTrue(dest.name.startswith("install.prev-"))
        self.assertTrue((dest / "actions.json").exists())
        self.assertFalse(take.exists())


# ---------- recorder ----------

FAKES = r"""
const state = { clicks: [], moves: [], evaluated: [], scripts: [] };
const FOUND = { box: { x: 1300, y: 260, w: 140, h: 40 }, labels: [], ancestors: [], target_ok: true,
  target_text: "Agregar a Chrome" };
function fakePage(url) {
  return { targetId: "main", label: "p1", url: async () => url,
    mouse: { move: async (x, y) => state.moves.push([x, y]), click: async (x, y) => state.clicks.push([x, y]) },
    keyboard: { press: async () => {}, type: async () => {} },
    goto: async (u) => { url = u; }, waitForLoadState: async () => {}, close: async () => {},
    evaluate: async () => [1920, 1080],
    cdp: async (method, params) => {
      if (method === "Page.captureScreenshot") { await new Promise((r) => setTimeout(r, 40)); return { data: "" }; }
      if (method === "Page.addScriptToEvaluateOnNewDocument") { state.scripts.push(params.source); return {}; }
      if (method !== "Runtime.evaluate") return {};
      const e = params.expression;
      if (e.includes("return shownTargets")) return { result: { value: 1 } };
      if (e.includes("return await findTarget")) {
        const box = e.includes("tutorial-sim-dialog") ? { x: 740, y: 8, w: 440, h: 220 } : FOUND.box;
        return { result: { value: e.includes('"#missing"') ? null : { ...FOUND, box } } };
      }
      state.evaluated.push(e);
      if (e.includes("__tutorialWatchText")) return { result: { value: true } };
      if (e.includes("__tutorialShowText")) return { result: { value: !e.includes('"#missing"') } };
      if (e.includes("tutorial-sim-dialog")) return { result: { value: true } };
      if (e.includes("data-tutorial-hide")) return { result: { value: true } };
      return { result: { value: null } };
    } };
}
const main = fakePage("https://chromewebstore.google.com/");
const task = { pages: async () => [main], tabs: async () => [{ targetId: "main", label: "p1", page: main }],
  adopt: async (p) => p, page: () => main, newPage: async () => main };
const rec = { now: () => 0, setPage() {}, clock: null };
const ctx = (censor = []) => ({ task, main, page: main, rec, surfaces: {}, state: {}, known: new Set(["main"]),
  censor: null, censorCfg: { text: censor, flags: "i" }, viewport: [1920, 1080], followed: null, track: null, regions: [] });
"""


@unittest.skipUnless(shutil.which("node"), "node no está instalado")
class RecorderInstallTest(unittest.TestCase):
    """I2 "simula la instalacion del plugin": relabel, Chrome-like dialog, visual presses, never a real click."""

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
        return json.loads(out.stdout)

    def test_install_step_events(self):
        steps = install_steps()
        data = self.node(f"""
          const steps = {json.dumps([{**steps[0], "hold_ms": 0}])};
          const log = await R.runSteps(ctx(), rec, steps);
          return {{ log, clicks: state.clicks.length, evaluated: state.evaluated }};
        """)
        res = data["result"]
        ev = res["log"][0]["events"]
        self.assertEqual([e["type"] for e in ev], ["result", "click", "result", "click"])
        self.assertTrue(ev[0]["show_text"])
        self.assertEqual(ev[0]["selector"], "button.add")
        self.assertEqual(ev[0]["target_text"], "Agregar a Chrome")
        self.assertTrue(ev[1]["visual"])
        self.assertEqual(ev[2]["selector"], "#tutorial-sim-dialog")
        self.assertTrue(ev[2]["simulated"])
        self.assertEqual(ev[2]["box"], {"x": 740, "y": 8, "w": 440, "h": 220})
        self.assertEqual(ev[3]["selector"], "#sim-btn-0")
        self.assertTrue(ev[3]["visual"])
        self.assertEqual(res["clicks"], 0)                     # nothing is really clicked (I2)
        shown = [e for e in res["evaluated"] if "__tutorialShowText" in e]
        self.assertEqual(len(shown), 1)
        self.assertIn(json.dumps("Agregar a Chrome"), shown[0])
        self.assertTrue(any("tutorial-sim-dialog" in e and ".remove()" in e for e in res["evaluated"]))
        self.assertEqual([line for line in data["logged"] if not line.startswith("[take]")], [])

    def test_watch_relabels_before_the_element_exists(self):
        # The store opens the listing in the same document (rehearsal 2026-11-19): a watcher installed before the
        # click relabels the button when it is inserted, before any frame shows "Agregar a ego".
        steps = [{"id": "a", "hold_ms": 0, "actions": [
            {"show_text": {"sel": "xpath=//button[contains(normalize-space(.),' a ego')]", "text": "Agregar a Chrome",
                           "watch": True}}]}]
        data = self.node(f"""
          const log = await R.runSteps(ctx(), rec, {json.dumps(steps)});
          return {{ log, clicks: state.clicks.length, evaluated: state.evaluated }};
        """)
        res = data["result"]
        self.assertEqual(res["log"][0]["events"], [])            # nothing is marked yet: the element comes later
        watched = [e for e in res["evaluated"] if "__tutorialWatchText" in e]
        self.assertEqual(len(watched), 1)
        self.assertIn(json.dumps("Agregar a Chrome"), watched[0])
        self.assertIn("MutationObserver", watched[0])
        self.assertEqual(res["clicks"], 0)

    def test_clicks_and_gotos_log_when_they_were_dispatched(self):
        # ego returns from a click only once a fast navigation has finished (Google, the store): `t_down` keeps the
        # moment the click was sent, so edit can find the screen change the click caused.
        steps = [{"id": "a", "hold_ms": 0, "actions": [{"click": "button.add"}, {"goto": "https://example.com/"},
                                                        {"press": "Enter"}]}]
        data = self.node(f"""
          let n = 0;
          const timed = {{ ...rec, now: () => (n += 0.5) }};
          const log = await R.runSteps(ctx(), timed, {json.dumps(steps)});
          return {{ log }};
        """)
        click, goto, press = data["result"]["log"][0]["events"]
        self.assertEqual((click["type"], goto["type"], press["type"]), ("click", "goto", "press"))
        for ev in (click, goto, press):
            self.assertIn("t_down", ev)
            self.assertLess(ev["t_down"], ev["t"])

    def test_censored_replacement_text_is_never_logged(self):
        steps = [{"id": "a", "hold_ms": 0, "actions": [{"show_text": {"sel": "button.add", "text": "Agregar a Chrome"}}]}]
        data = self.node(f"""
          const log = await R.runSteps(ctx(["agregar"]), rec, {json.dumps(steps)});
          return {{ log }};
        """)
        ev = data["result"]["log"][0]["events"][0]
        self.assertNotIn("target_text", ev)
        self.assertNotIn("Agregar a Chrome", json.dumps(data["logged"]))

    def test_a_missing_element_stops_the_take(self):
        steps = [{"id": "a", "hold_ms": 0, "actions": [{"show_text": {"sel": "#missing", "text": "x"}}]}]
        data = self.node(f"""
          try {{ await R.runSteps(ctx(), rec, {json.dumps(steps)}); return null; }}
          catch (err) {{ return String(err.message); }}
        """)
        self.assertIn("show_text: no encontré '#missing' (I2)", data["result"])

    def test_dialog_html_looks_like_chrome(self):
        data = self.node(f"""
          return {{ plain: R.dialogHtml({json.dumps(DIALOG)}),
                    icon: R.dialogHtml({{ ...{json.dumps(DIALOG)}, icon: "data:image/png;base64,AAAA", primary: 1 }}) }};
        """)
        plain, icon = data["result"]["plain"], data["result"]["icon"]
        self.assertIn('id="tutorial-sim-dialog"', plain)
        self.assertIn("¿Quieres agregar &quot;Perseo XML&quot;?", plain)
        self.assertIn("Leer y cambiar tus datos en srienlinea.sri.gob.ec", plain)
        self.assertIn('id="sim-btn-0"', plain)
        self.assertIn('id="sim-btn-1"', plain)
        self.assertIn("Segoe UI", plain)
        self.assertNotIn("<img", plain)
        # The primary button (first by default, Chrome on Windows) is the blue one.
        self.assertRegex(plain, r'id="sim-btn-0"[^>]*background:#0b57d0')
        self.assertNotRegex(plain, r'id="sim-btn-1"[^>]*background:#0b57d0')
        self.assertRegex(icon, r'id="sim-btn-1"[^>]*background:#0b57d0')
        self.assertIn('<img src="data:image/png;base64,AAAA"', icon)

    def test_dialog_is_built_without_html_strings(self):
        # Google pages enforce Trusted Types (rehearsal 2026-11-19): insertAdjacentHTML/innerHTML throw there.
        data = self.node(f"""
          const made = [];
          const node = (tag) => ({{ tag, attrs: {{}}, kids: [], text: null,
            setAttribute(k, v) {{ this.attrs[k] = v; }}, appendChild(c) {{ this.kids.push(c); return c; }},
            set textContent(v) {{ this.text = v; }}, style: {{}} }});
          const body = node("body");
          globalThis.document = {{ body, createElement: (t) => {{ const n = node(t); made.push(n); return n; }},
            getElementById: (id) => made.find((n) => n.attrs.id === id && body.kids.includes(n)) || null,
            querySelector: () => null }};
          globalThis.innerWidth = 1920;
          const src = R.simulateDialogSource({json.dumps(DIALOG)});
          const shown = (0, eval)(src);
          const dialog = body.kids[0];
          const buttons = made.filter((n) => n.tag === "button").map((b) => [b.attrs.id, b.text]);
          return {{ shown, html: /insertAdjacentHTML|innerHTML|outerHTML/.test(src), id: dialog.attrs.id,
                    title: made.find((n) => n.text === {json.dumps(DIALOG["title"])}) ? true : false, buttons }};
        """)
        self.assertEqual(data["result"], {"shown": True, "html": False, "id": "tutorial-sim-dialog", "title": True,
                                          "buttons": [["sim-btn-0", "Agregar extensión"], ["sim-btn-1", "Cancelar"]]})

    def test_relabel_hides_the_original_and_adds_its_own_label(self):
        # The store's framework puts its own text back into the label it renders (rehearsal 2026-11-19), so the
        # original label is hidden, not edited, and a sibling with its class shows the new text.
        data = self.node("""
          const doc = { createElement: (tag) => el(tag, []) };
          function el(tag, kids, cls = "") {
            const e = { nodeType: 1, tagName: tag, className: cls, attrs: {}, childNodes: [], ownerDocument: doc,
              style: { setProperty(k, v, p) { this[k] = v + (p ? " !" + p : ""); } },
              setAttribute(k, v) { this.attrs[k] = v; },
              set textContent(v) { this.childNodes = [{ nodeType: 3, nodeValue: v, parentElement: this }]; },
              get textContent() { return this.childNodes.map((c) => c.nodeType === 3 ? c.nodeValue : c.textContent).join(""); },
              querySelector(sel) {
                for (const c of this.childNodes) {
                  if (c.nodeType !== 1) continue;
                  if ("data-tutorial-text" in c.attrs) return c;
                  const f = c.querySelector(sel);
                  if (f) return f;
                }
                return null;
              },
              after(node) {
                const kids = this.parentElement.childNodes;
                kids.splice(kids.indexOf(this) + 1, 0, node);
                node.parentElement = this.parentElement;
              } };
            for (const k of kids) { k.parentElement = e; e.childNodes.push(k); }
            return e;
          }
          const t = (v) => ({ nodeType: 3, nodeValue: v });
          const icon = el("SPAN", [t("")]);
          const label = el("SPAN", [t("Agregar a ego")], "UywwFc-vQzf8d");
          const button = el("BUTTON", [icon, label]);
          const first = R.relabel(button, "Agregar a Chrome");
          label.childNodes[0].nodeValue = "Agregar a ego";      // the framework puts its text back
          const shown = button.childNodes[2];
          const again = R.relabel(button, "Quitar de Chrome");
          const none = R.relabel(el("BUTTON", [el("SPAN", [t(" ")])]), "x");
          return { first, again, none, kids: button.childNodes.length, hidden: label.style.display,
                   cls: shown.className, mine: "data-tutorial-text" in shown.attrs, text: shown.textContent };
        """)
        self.assertEqual(data["result"], {"first": True, "again": True, "none": False, "kids": 3,
                                          "hidden": "none !important", "cls": "UywwFc-vQzf8d", "mine": True,
                                          "text": "Quitar de Chrome"})

    def test_take_hides_page_notices_before_the_first_frame(self):
        out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, out, True)
        data = self.node(f"""
          const r = await R.take(task, {{ outDir: {json.dumps(Path(out).as_posix())}, steps: [], viewport: [1920, 1080],
            hide: [".gSrP5d"] }});
          return {{ failure: r.failure, scripts: state.scripts }};
        """)
        self.assertIsNone(data["result"]["failure"])
        self.assertTrue(any(".gSrP5d { display: none !important; }" in s for s in data["result"]["scripts"]))

    def test_take_without_hide_adds_no_script(self):
        out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, out, True)
        data = self.node(f"""
          const r = await R.take(task, {{ outDir: {json.dumps(Path(out).as_posix())}, steps: [], viewport: [1920, 1080] }});
          return {{ failure: r.failure, scripts: state.scripts }};
        """)
        self.assertEqual(data["result"], {"failure": None, "scripts": []})


# ---------- compose: a wide form keeps fitting while the camera pushes in (N12, C8) ----------

def search_form_timeline():
    """Google's home (rehearsal 2026-11-19): its <form> spans 1728 px; one typing step held ~6 s under pace fast."""
    form = {"x": 96, "y": 376, "w": 1728, "h": 140}
    ev = {"type": "type", "t": 4.2, "t_end": 5.4, "chars": 16, "selector": "textarea[name=q]",
          "box": {"x": 655, "y": 383, "w": 600, "h": 36}, "point": {"x": 955, "y": 401},
          "frame_box": {"x": 655, "y": 383, "w": 600, "h": 36}, "form_box": form}
    return {"video": "tutorial", "type": "TUT", "format": "16:9", "total": 10.0, "product": "Perseo XML",
            "title": "T", "opening": None, "requirements": None, "closing": None, "pace": "fast",
            "screen_start": 3.6, "screen_end": 10.0, "steps": [
                {"id": "buscar-tienda", "number": 1, "title": "Busca", "narration": "Primero, busca Chrome Web Store en Google.",
                 "start": 3.6, "duration": 6.4, "voice_start": 3.9, "voice_duration": 3.0, "events": [ev]}]}


class WideFormPushTest(unittest.TestCase):
    def test_the_push_in_keeps_the_whole_form_across(self):
        tl = search_form_timeline()
        lay = compose.plan(tl, json.loads((TOOLS.parent / "templates" / "fixtures" / "brand.json").read_text(encoding="utf-8")))
        vx, vy, vw, vh = lay["viewport"]
        forms = [s for s in lay["camera"] if s["kind"] == "form"]
        self.assertTrue(forms, lay["camera"])
        form = tl["steps"][0]["events"][0]["form_box"]
        for seg in forms:
            for fr in [seg] + ([{"x": seg["from"]["x"], "y": seg["from"]["y"], "scale": seg["from"]["s"]}]
                               if seg.get("from") else []):
                x0 = fr["x"] + form["x"] * fr["scale"]
                with self.subTest(seg=seg["t0"], scale=fr["scale"]):
                    self.assertGreaterEqual(x0, vx - 1)
                    self.assertLessEqual(x0 + form["w"] * fr["scale"], vx + vw + 1)
        # C8 still holds: the 6 s form shot is not one frozen framing.
        self.assertTrue(any(s.get("push") for s in forms) or len(forms) > 1, lay["camera"])


# ---------- qa: N14 "Perseo" in the browser (I1) ----------

class NamedInChromeTest(unittest.TestCase):
    """N14.named reads "Perseo" as the extension popup. In a `chrome` step (the store) "Perseo XML" is the typed query
    or the listing, which the timeline cannot prove: the check asks for the visual review instead of failing."""

    def run_check(self, context):
        import qa
        timeline = {"steps": [{"id": "buscar-perseo", "context": context, "start": 10.0, "duration": 3.0, "events": []}],
                    "surfaces": {"popup": {"windows": [[30.0, 35.0]]}}}
        captions = [{"t0": 10.3, "t1": 12.0, "text": "Después busca Perseo XML.", "step": "buscar-perseo"}]
        by_kind = {"surface": [{"t0": 30.0, "t1": 35.0}]}
        return qa.check_named(captions, by_kind, timeline)

    def test_store_mentions_need_the_visual_review(self):
        res = self.run_check("chrome")
        self.assertEqual(res["status"], "WARN", res)
        self.assertIn("«Después busca Perseo XML.» nombra Perseo en Chrome", res["detail"])

    def test_elsewhere_the_popup_must_be_open(self):
        # PRESERVE: outside the browser context the popup still has to be on screen.
        res = self.run_check("sri")
        self.assertEqual(res["status"], "FAIL", res)
        self.assertIn("nombra Perseo, que no está en pantalla", res["detail"])


# ---------- edit: a click that returned after its navigation (t_down) ----------

class ClickAfterNavigationTest(unittest.TestCase):
    """Google and the store load the next screen before ego's click returns: the screen change is before the logged
    click time. edit finds it from `t_down` and places the click there (C10 cut, no box over the new screen)."""

    def setUp(self):
        import edit
        from PIL import Image
        self.edit = edit
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.frames = []
        for i, (t, shade) in enumerate(((0.0, 30), (0.5, 30), (1.0, 220), (1.5, 220), (2.0, 220))):
            name = f"f{i:06d}.jpg"
            img = Image.new("RGB", (1920, 1080), (shade, shade, shade))
            if shade == 30:
                img.paste((200, 200, 200), (800, 400, 1100, 450))      # the old screen: a field
            img.save(self.dir / name)
            self.frames.append({"file": name, "t": t})

    def mark(self, ev):
        actions = {"steps": [{"id": "a", "t0": 0.0, "t1": 2.0, "events": [ev]}]}
        self.edit.mark_screen_changes(actions, self.frames, [False] * len(self.frames), self.dir)
        return actions["steps"][0]["events"][0]

    def test_the_change_before_the_logged_time_is_found_from_t_down(self):
        ev = self.mark({"type": "click", "t": 1.6, "t_down": 0.8, "selector": "#b", "box": {"x": 0, "y": 0, "w": 9, "h": 9}})
        self.assertEqual(ev["screen_c"], 1.0)
        self.assertEqual(ev["t"], 0.8)

    def test_without_t_down_nothing_changes(self):
        # PRESERVE: older captures (no t_down) keep their logged time and find no change after it.
        ev = self.mark({"type": "click", "t": 1.6, "selector": "#b", "box": {"x": 0, "y": 0, "w": 9, "h": 9}})
        self.assertNotIn("screen_c", ev)
        self.assertEqual(ev["t"], 1.6)


# ---------- merge_takes ----------

def write_take(root: Path, name: str, frames, steps, surfaces=None, regions=None, failure=None,
               viewport=(1920, 1080)) -> Path:
    take = root / name
    (take / "frames").mkdir(parents=True)
    for f in frames:
        (take / "frames" / f["file"]).write_bytes(f"{name}/{f['file']}".encode())
    (take / "frames.json").write_text(json.dumps({"frames": frames, "errors": 1}), encoding="utf-8")
    actions = {"viewport": list(viewport), "steps": steps, "failure": failure}
    for sname, spec in (surfaces or {}).items():
        sdir = take / "surfaces" / sname
        (sdir / "frames").mkdir(parents=True)
        for f in spec["frames"]:
            (sdir / "frames" / f["file"]).write_bytes(f"{name}/{sname}/{f['file']}".encode())
        (sdir / "frames.json").write_text(json.dumps({"frames": spec["frames"]}), encoding="utf-8")
        actions.setdefault("surfaces", {})[sname] = {
            "size": [460, 660], "dpr": 2, "anchor": "top-right", "dir": f"surfaces/{sname}",
            "windows": spec["windows"], "frames": len(spec["frames"])}
    if regions:
        actions["censor_regions"] = regions
    (take / "actions.json").write_text(json.dumps(actions), encoding="utf-8")
    return take


def tree_digest(path: Path) -> dict:
    return {p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(path.rglob("*")) if p.is_file()}


class MergeTakesTest(unittest.TestCase):
    """I3 "Tomas unidas": the install take, then the approved v3 take, on one clock."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.out = root / "proyecto"
        self.out.mkdir()
        self.install = write_take(root, "install", [{"file": "f000000.jpg", "t": 0.1}, {"file": "f000001.jpg", "t": 0.6},
                                                    {"file": "f000002.jpg", "t": 1.0}],
                                  [{"id": "tienda", "t0": 0.1, "t1": 0.9,
                                    "events": [{"type": "click", "t": 0.5, "selector": "#a", "visual": True},
                                               {"type": "type", "t": 0.2, "ts": 0.25, "t_end": 0.4, "chars": 3}]}])
        self.v3 = write_take(root, "v3", [{"file": "f000000.jpg", "t": 0.0}, {"file": "f000001.jpg", "t": 2.0}],
                             [{"id": "sri", "t0": 0.2, "t1": 1.5,
                               "events": [{"type": "goto", "t": 0.7, "t_down": 0.6, "tab": "follow", "censor": "script"},
                                          {"type": "result", "t": 1.0, "selector": ".estadisticas", "surface": "popup"}]}],
                             surfaces={"popup": {"frames": [{"file": "w0_f000000.jpg", "t": 0.35}],
                                                 "windows": [{"t0": 0.3, "t1": 0.8}]}},
                             regions=[{"t0": 0.5, "t1": 0.9, "box": {"x": 1, "y": 2, "w": 3, "h": 4}}])

    def merge(self, *takes):
        out = io.StringIO()
        with redirect_stdout(out):
            merge_takes.merge_takes(self.out, list(takes))
        return out.getvalue()

    def read(self, rel):
        return json.loads((self.out / "capture" / rel).read_text(encoding="utf-8"))

    def test_takes_are_concatenated_on_one_clock(self):
        printed = self.merge(self.install, self.v3)
        frames = self.read("frames.json")
        self.assertEqual(frames["frames"], [
            {"file": "t0_f000000.jpg", "t": 0.1}, {"file": "t0_f000001.jpg", "t": 0.6}, {"file": "t0_f000002.jpg", "t": 1.0},
            {"file": "t1_f000000.jpg", "t": 1.2}, {"file": "t1_f000001.jpg", "t": 3.2}])
        self.assertEqual(frames["errors"], 2)
        self.assertEqual((self.out / "capture" / "frames" / "t1_f000001.jpg").read_bytes(), b"v3/f000001.jpg")
        actions = self.read("actions.json")
        self.assertIsNone(actions["failure"])
        self.assertEqual(actions["viewport"], [1920, 1080])
        self.assertEqual([s["id"] for s in actions["steps"]], ["tienda", "sri"])
        self.assertEqual(actions["steps"][0]["events"][1], {"type": "type", "t": 0.2, "ts": 0.25, "t_end": 0.4, "chars": 3})
        sri = actions["steps"][1]
        self.assertEqual((sri["t0"], sri["t1"]), (1.4, 2.7))
        self.assertEqual(sri["events"][0], {"type": "goto", "t": 1.9, "t_down": 1.8, "tab": "follow", "censor": "script"})
        self.assertEqual(sri["events"][1]["t"], 2.2)
        self.assertEqual(actions["surfaces"]["popup"]["windows"], [{"t0": 1.5, "t1": 2.0}])
        self.assertEqual(actions["surfaces"]["popup"]["frames"], 1)
        self.assertEqual(actions["censor_regions"], [{"t0": 1.7, "t1": 2.1, "box": {"x": 1, "y": 2, "w": 3, "h": 4}}])
        self.assertEqual(self.read("surfaces/popup/frames.json"), {"frames": [{"file": "t1_w0_f000000.jpg", "t": 1.55}]})
        self.assertTrue((self.out / "capture" / "surfaces" / "popup" / "frames" / "t1_w0_f000000.jpg").exists())
        self.assertIn("[merge] 2 tomas → ", printed)

    def test_idempotent_and_sources_untouched(self):
        before = (tree_digest(self.install), tree_digest(self.v3))
        self.merge(self.install, self.v3)
        first = tree_digest(self.out / "capture")
        self.merge(self.install, self.v3)
        self.assertEqual(tree_digest(self.out / "capture"), first)
        self.assertEqual((tree_digest(self.install), tree_digest(self.v3)), before)
        # A new merge leaves nothing of the previous one behind.
        self.merge(self.install)
        self.assertEqual(sorted(p.name for p in (self.out / "capture" / "frames").iterdir()),
                         ["t0_f000000.jpg", "t0_f000001.jpg", "t0_f000002.jpg"])
        self.assertFalse((self.out / "capture" / "surfaces").exists())
        self.assertEqual(list(self.out.glob("capture.prev-*")), [])

    def test_a_recorded_take_in_the_way_is_moved_aside(self):
        (self.out / "capture").mkdir()
        (self.out / "capture" / "actions.json").write_text("{}", encoding="utf-8")
        self.merge(self.install)
        kept = list(self.out.glob("capture.prev-*"))
        self.assertEqual(len(kept), 1)
        self.assertEqual((kept[0] / "actions.json").read_text(encoding="utf-8"), "{}")

    def test_duplicate_step_ids_fail_clearly(self):
        with self.assertRaises(common.PipelineError) as ctx:
            self.merge(self.install, self.install)
        self.assertIn("el paso 'tienda' está en dos tomas", str(ctx.exception))
        self.assertFalse((self.out / "capture").exists())

    def test_broken_or_mismatched_takes_fail(self):
        root = Path(self.tmp.name)
        failed = write_take(root, "rota", [{"file": "f000000.jpg", "t": 0.1}], [], failure="Paso x: no encontré #a")
        with self.assertRaises(common.PipelineError) as ctx:
            self.merge(self.install, failed)
        self.assertIn("la toma rota se cortó", str(ctx.exception))
        small = write_take(root, "chica", [{"file": "f000000.jpg", "t": 0.1}], [{"id": "otro", "t0": 0, "t1": 0.1, "events": []}],
                           viewport=(1280, 720))
        with self.assertRaises(common.PipelineError) as ctx:
            self.merge(self.install, small)
        self.assertIn("viewport", str(ctx.exception))
        with self.assertRaises(common.PipelineError) as ctx:
            self.merge(self.install, root / "no-existe")
        self.assertIn("no-existe", str(ctx.exception))
        with self.assertRaises(common.PipelineError) as ctx:
            merge_takes.merge_takes(self.install.parent, [self.install.parent / "capture"])
        self.assertIn("una toma no puede ser la salida", str(ctx.exception))

    def test_cli(self):
        ok = subprocess.run([PYTHON, str(TOOLS / "merge_takes.py"), str(self.out), str(self.install), str(self.v3)],
                            capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertIn("[merge] 2 tomas → ", ok.stdout)
        bad = subprocess.run([PYTHON, str(TOOLS / "merge_takes.py"), str(self.out), str(self.install), str(self.install)],
                             capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(bad.returncode, 1)
        self.assertIn("ERROR: ", bad.stderr)
        self.assertIn("está en dos tomas", bad.stderr)


if __name__ == "__main__":
    unittest.main()
