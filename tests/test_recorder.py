"""recorder.mjs helpers of reglas-ronda4 T1: verified targets (N13), surface `hide` (N23) and the censor of
pages reached with `follow: tab` (N25: regex flags, CDP regions through open shadow roots).

Run: .venv/Scripts/python.exe -m unittest tests.test_recorder -v
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

RECORDER = Path(__file__).resolve().parents[1] / "tools" / "capture" / "recorder.mjs"
VIEW = [1920, 1080]
SHOWN = {"display": "block", "visibility": "visible", "opacity": 1}


@unittest.skipUnless(shutil.which("node"), "node no está instalado")
class NodeCase(unittest.TestCase):
    def node(self, names: str, expr: str):
        script = (f"const {{ {names} }} = await import({json.dumps(RECORDER.as_uri())});\n"
                  "const logged = [];\n"
                  "for (const k of ['log', 'info', 'warn', 'error', 'debug']) console[k] = (...a) => logged.push(a.join(' '));\n"
                  f"const result = {expr};\n"
                  "process.stdout.write(JSON.stringify({ result: result === undefined ? null : result, logged }));")
        out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True,
                             encoding="utf-8", check=True)
        data = json.loads(out.stdout)
        self.assertEqual(data["logged"], [])
        return data["result"]


def target(box, style=SHOWN, rel="self", hit_box=None, hit_interactive=False):
    return {"box": box, "style": style, "viewport": VIEW,
            "hit": {"rel": rel, "box": hit_box or box, "interactive": hit_interactive}}


class TargetOkTest(NodeCase):
    """N13 "Hay resaltados sobre zonas vacías ... marcan el elemento equivocado": target_ok."""

    BOX = {"x": 300, "y": 200, "w": 240, "h": 32}

    def ok(self, t):
        return self.node("targetOk", f"targetOk({json.dumps(t)})")

    def test_visible_element_hit_at_its_center(self):
        self.assertTrue(self.ok(target(self.BOX)))
        self.assertTrue(self.ok(target(self.BOX, rel="descendant", hit_box={"x": 310, "y": 205, "w": 60, "h": 20})))

    def test_empty_or_tiny_box(self):
        for box in ({"x": 300, "y": 200, "w": 0, "h": 0}, {"x": 300, "y": 200, "w": 4, "h": 30},
                    {"x": 300, "y": 200, "w": 200, "h": 4}):
            with self.subTest(box=box):
                self.assertFalse(self.ok(target(box)))

    def test_hidden_styles(self):
        for style in ({**SHOWN, "display": "none"}, {**SHOWN, "visibility": "hidden"}, {**SHOWN, "opacity": 0},
                      {**SHOWN, "visibility": "collapse"}):
            with self.subTest(style=style):
                self.assertFalse(self.ok(target(self.BOX, style=style)))

    def test_outside_the_viewport(self):
        self.assertFalse(self.ok(target({"x": -400, "y": 200, "w": 240, "h": 32})))     # off-canvas side menu
        self.assertFalse(self.ok(target({"x": 300, "y": 1200, "w": 240, "h": 32})))

    def test_another_element_at_the_point(self):
        # The SRI case: the box of a hidden "Comprobantes ... emitidos" lies over "Certificados".
        self.assertFalse(self.ok(target(self.BOX, rel="other", hit_box={"x": 0, "y": 190, "w": 260, "h": 40})))
        self.assertFalse(self.ok(target(self.BOX, rel="none")))

    def test_ancestor_counts_only_when_it_is_tight_or_interactive(self):
        tight = {"x": 290, "y": 195, "w": 260, "h": 42}
        page = {"x": 0, "y": 0, "w": 1920, "h": 1080}
        self.assertTrue(self.ok(target(self.BOX, rel="ancestor", hit_box=tight)))
        self.assertTrue(self.ok(target(self.BOX, rel="ancestor", hit_box=page, hit_interactive=True)))
        self.assertFalse(self.ok(target(self.BOX, rel="ancestor", hit_box=page)))

    def test_hit_point_is_the_center_of_the_visible_part(self):
        tall = {"x": 300, "y": 600, "w": 800, "h": 1400}      # a long table: its center is below the fold
        self.assertEqual(self.node("hitPoint", f"hitPoint({json.dumps(tall)}, {json.dumps(VIEW)})"),
                         {"x": 700, "y": 840})
        self.assertIsNone(self.node("hitPoint", f"hitPoint({json.dumps({'x': -500, 'y': 0, 'w': 100, 'h': 50})},"
                                                f" {json.dumps(VIEW)})"))


class RankTargetsTest(NodeCase):
    """text= never returns hidden duplicates; visible, in-viewport, interactive matches first."""

    def rank(self, cands, by_area=False):
        return self.node("rankTargets", f"rankTargets({json.dumps(cands)}, {json.dumps(by_area)})")

    def test_hidden_duplicates_are_never_chosen(self):
        hidden = {"shown": False, "inView": True, "interactive": True, "box": {"x": 0, "y": 200, "w": 200, "h": 30}}
        shown = {"shown": True, "inView": True, "interactive": True, "box": {"x": 400, "y": 300, "w": 300, "h": 30}}
        self.assertEqual(self.rank([hidden, shown], True), [1])
        self.assertEqual(self.rank([hidden], True), [])

    def test_in_viewport_then_interactive_then_smaller(self):
        below = {"shown": True, "inView": False, "interactive": True, "box": {"x": 0, "y": 1500, "w": 100, "h": 20}}
        span = {"shown": True, "inView": True, "interactive": False, "box": {"x": 0, "y": 100, "w": 90, "h": 20}}
        link = {"shown": True, "inView": True, "interactive": True, "box": {"x": 0, "y": 100, "w": 120, "h": 24}}
        row = {"shown": True, "inView": True, "interactive": True, "box": {"x": 0, "y": 90, "w": 900, "h": 44}}
        self.assertEqual(self.rank([below, span, row, link], True), [3, 2, 1, 0])

    def test_css_and_xpath_keep_document_order(self):
        a = {"shown": True, "inView": True, "interactive": False, "box": {"x": 0, "y": 0, "w": 900, "h": 300}}
        b = {"shown": True, "inView": True, "interactive": False, "box": {"x": 0, "y": 0, "w": 10, "h": 10}}
        off = {"shown": True, "inView": False, "interactive": False, "box": {"x": 0, "y": 2000, "w": 10, "h": 10}}
        self.assertEqual(self.rank([off, a, b], False), [1, 2, 0])


class TargetTextTest(NodeCase):
    """target_text: visible text, trimmed, <= 60 chars; omitted when it matches a censor pattern."""

    def text(self, text, patterns=(), flags="i", censored=False):
        return self.node("targetText", f"targetText({json.dumps(text)}, {json.dumps(list(patterns))}, "
                                       f"{json.dumps(flags)}, {json.dumps(censored)})")

    def test_trimmed_and_collapsed(self):
        self.assertEqual(self.text("  Comprobantes electrónicos\n   emitidos "), "Comprobantes electrónicos emitidos")

    def test_at_most_60_chars(self):
        out = self.text("x" * 80)
        self.assertEqual(len(out), 60)
        self.assertEqual(self.text("y" * 60), "y" * 60)

    def test_omitted_when_censored(self):
        self.assertIsNone(self.text("RUC 1708334097001", [r"\b\d{13}\b"]))
        self.assertIsNone(self.text("Bienvenido NOMBRE DE PRUEBA", ["nombre de prueba"]))
        self.assertIsNone(self.text("Bienvenido", [], censored=True))   # inside a blurred element
        self.assertIsNone(self.text("   "))

    def test_case_sensitive_flags(self):
        self.assertEqual(self.text("Nombre de prueba", ["NOMBRE DE PRUEBA"], flags=""), "Nombre de prueba")


class TargetFailureTest(NodeCase):
    """The take fails with a Spanish message naming the step and the selector, never the text."""

    def message(self, ev, step="emitidos"):
        return self.node("targetFailure", f"targetFailure({json.dumps(step)}, {json.dumps(ev)})")

    def test_fails_for_marked_actions(self):
        for kind in ("click", "type", "select", "highlight", "result", "focus"):
            msg = self.message({"type": kind, "selector": 'text="Comprobantes electrónicos emitidos"',
                                "target_ok": False})
            with self.subTest(kind=kind):
                self.assertIn("Paso emitidos", msg)
                self.assertIn('text="Comprobantes electrónicos emitidos"', msg)
                self.assertIn("N13", msg)

    def test_ok_or_hover_pass(self):
        self.assertIsNone(self.message({"type": "click", "selector": "#a", "target_ok": True}))
        self.assertIsNone(self.message({"type": "hover", "selector": "#a", "target_ok": False}))

    def test_message_never_carries_the_target_text(self):
        msg = self.message({"type": "click", "selector": "#perfil", "target_ok": False,
                            "target_text": "NOMBRE DE PRUEBA"})
        self.assertNotIn("NOMBRE", msg)


class LocateSourceTest(NodeCase):
    def test_source_is_self_contained_and_silent(self):
        res = self.node("locateSource", "(() => { const src = locateSource('text=\"Consultar\"', { text: ['\\\\d{13}'],"
                                        " flags: 'i' }); let parses = true; try { new Function(src); } catch (e) {"
                                        " parses = String(e); } return { parses, console: /console\\./.test(src) }; })()")
        self.assertEqual(res, {"parses": True, "console": False})


class HideTest(NodeCase):
    """N23 surfaces.<name>.hide: a display:none !important rule per selector, before the first frame."""

    def test_one_rule_per_selector(self):
        css = self.node("hideCss", "hideCss(['.promo', '#club-perseo a'])")
        self.assertEqual(css, ".promo { display: none !important; }\n#club-perseo a { display: none !important; }")

    def test_source_parses_and_is_idempotent(self):
        res = self.node("hideSource", "(() => { const src = hideSource(['.promo']); let parses = true;"
                                      " try { new Function(src); } catch (e) { parses = String(e); }"
                                      " return { parses, mark: /data-tutorial-hide/.test(src) }; })()")
        self.assertEqual(res, {"parses": True, "mark": True})
        self.assertIsNone(self.node("hideSource", "hideSource([])"))


# A CDP DOM.getDocument({depth: -1, pierce: true}) tree: the downloads path inside nested shadow roots.
TREE = {"nodeId": 1, "nodeType": 9, "nodeName": "#document", "children": [
    {"nodeId": 2, "nodeType": 1, "nodeName": "HTML", "children": [
        {"nodeId": 3, "nodeType": 1, "nodeName": "BODY", "children": [
            {"nodeId": 4, "nodeType": 1, "nodeName": "SETTINGS-UI", "attributes": [], "shadowRoots": [
                {"nodeId": 5, "nodeType": 11, "nodeName": "#document-fragment", "children": [
                    {"nodeId": 6, "nodeType": 1, "nodeName": "SETTINGS-DOWNLOADS-PAGE", "shadowRoots": [
                        {"nodeId": 7, "nodeType": 11, "nodeName": "#document-fragment", "children": [
                            {"nodeId": 8, "nodeType": 1, "nodeName": "DIV", "attributes": ["id", "defaultDownloadPath"],
                             "children": [{"nodeId": 9, "nodeType": 3, "nodeName": "#text",
                                           "nodeValue": "C:\\Users\\NOMBRE DE PRUEBA\\Downloads"}]},
                            {"nodeId": 10, "nodeType": 1, "nodeName": "SPAN",
                             "attributes": ["data-tutorial-censor", "text"],
                             "children": [{"nodeId": 11, "nodeType": 3, "nodeName": "#text",
                                           "nodeValue": "NOMBRE DE PRUEBA"}]},
                            {"nodeId": 12, "nodeType": 1, "nodeName": "STYLE",
                             "children": [{"nodeId": 13, "nodeType": 3, "nodeName": "#text",
                                           "nodeValue": "/* NOMBRE DE PRUEBA */"}]}]}]}]}]},
            {"nodeId": 14, "nodeType": 1, "nodeName": "IFRAME", "contentDocument": {
                "nodeId": 15, "nodeType": 9, "nodeName": "#document", "children": [
                    {"nodeId": 16, "nodeType": 3, "nodeName": "#text", "nodeValue": "ruc 1708334097001"}]}},
            {"nodeId": 17, "nodeType": 3, "nodeName": "#text", "nodeValue": "Descargas"}]}]}]}


class CensorRegionsTest(NodeCase):
    """N25 fallback: matching text nodes through open shadow roots, for DOM.getBoxModel."""

    def test_text_nodes_through_shadow_roots_and_frames(self):
        patterns = json.dumps(["NOMBRE DE PRUEBA", r"\b\d{13}\b"])
        nodes = self.node("censorTextNodes", f"censorTextNodes({json.dumps(TREE)}, {patterns}, 'i')")
        self.assertEqual(nodes, [{"nodeId": 9, "parentId": 8}, {"nodeId": 16, "parentId": 15}])

    def test_no_patterns_no_nodes(self):
        self.assertEqual(self.node("censorTextNodes", f"censorTextNodes({json.dumps(TREE)}, [], 'i')"), [])

    def test_quad_box_clipped_to_the_viewport(self):
        self.assertEqual(self.node("quadBox", "quadBox([100.4, 50, 400.6, 50, 400.6, 80.2, 100.4, 80.2], [1920, 1080])"),
                         {"x": 100, "y": 50, "w": 301, "h": 30})
        self.assertIsNone(self.node("quadBox", "quadBox([0, 1200, 10, 1200, 10, 1300, 0, 1300], [1920, 1080])"))


class RegexFlagsTest(NodeCase):
    """censor.regex_flags: default case-insensitive; '' is case-sensitive."""

    def test_default_and_explicit_flags(self):
        self.assertEqual(self.node("censorRanges", "censorRanges('Nombre de Prueba', ['NOMBRE DE PRUEBA'])"), [[0, 16]])
        self.assertEqual(self.node("censorRanges", "censorRanges('Nombre de Prueba', ['NOMBRE DE PRUEBA'], '')"), [])
        self.assertEqual(self.node("censorRanges", "censorRanges('a\\nb', ['a.b'], 'is')"), [[0, 3]])

    def test_source_carries_the_flags(self):
        res = self.node("censorSource", "censorSource({ text: ['x'], flags: 's' })")
        self.assertIn('"flags":"s"', res)
        res = self.node("censorSource", "(() => { try { censorSource({ text: ['x'], flags: 'gq' }); return 'ok'; }"
                                        " catch (e) { return e.message; } })()")
        self.assertEqual(res, "censor.regex_flags no es válido")


if __name__ == "__main__":
    unittest.main()
