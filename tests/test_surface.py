"""recorder.mjs helpers for perseo-xml S3/S5: in-page censor (blur by selector and by text regex), the
chrome.tabs.query patch of an extension surface, and the tab adopted by `follow: tab`.

Run: .venv/Scripts/python.exe -m unittest tests.test_surface -v
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

RECORDER = Path(__file__).resolve().parents[1] / "tools" / "capture" / "recorder.mjs"
RUC = r"\b\d{13}\b"
HEADER = "RUC: 1708334097001 / NOMBRE DE PRUEBA"

# Minimal DOM for wrapTextNode: text nodes, elements with attributes/style, fragments.
FAKE_DOM = r"""
class N {
  constructor(type, value, tag) {
    this.nodeType = type; this.nodeValue = value ?? null; this.tagName = tag; this.childNodes = [];
    this.parentNode = null; this.attrs = {}; const props = {}; this.props = props;
    this.style = { setProperty(k, v, p) { props[k] = p ? `${v} !${p}` : v; } };
  }
  get parentElement() { return this.parentNode && this.parentNode.nodeType === 1 ? this.parentNode : null; }
  get textContent() { return this.nodeType === 3 ? this.nodeValue : this.childNodes.map((c) => c.textContent).join(""); }
  set textContent(t) { this.childNodes = []; this.appendChild(new N(3, t)); }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  hasAttribute(k) { return k in this.attrs; }
  appendChild(c) {
    const add = c.nodeType === 11 ? c.childNodes.splice(0) : [c];
    for (const x of add) { x.parentNode = this; this.childNodes.push(x); }
    return c;
  }
  replaceChild(n, old) {
    const add = n.nodeType === 11 ? n.childNodes.splice(0) : [n];
    add.forEach((x) => { x.parentNode = this; });
    this.childNodes.splice(this.childNodes.indexOf(old), 1, ...add);
    old.parentNode = null;
  }
}
const doc = {
  createDocumentFragment: () => new N(11),
  createElement: (tag) => new N(1, null, tag.toUpperCase()),
  createTextNode: (t) => new N(3, t),
};
const logged = [];
for (const k of ["log", "info", "warn", "error", "debug", "trace"]) console[k] = (...a) => logged.push(a.join(" "));
const out = (v) => process.stdout.write(JSON.stringify({ result: v, logged }));
"""


@unittest.skipUnless(shutil.which("node"), "node no está instalado")
class NodeCase(unittest.TestCase):
    def node(self, body: str, names: str):
        script = (f"const {{ {names} }} = await import({json.dumps(RECORDER.as_uri())});\n{FAKE_DOM}\n{body}")
        out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True,
                             encoding="utf-8", check=True)
        return json.loads(out.stdout)


class CensorMatchTest(NodeCase):
    """S3 "censura nombres y credenciales": RUC and the taxpayer name are found in any text, nothing logged."""

    def ranges(self, text, patterns):
        res = self.node(f"out(censorRanges({json.dumps(text)}, {json.dumps(patterns)}));", "censorRanges")
        self.assertEqual(res["logged"], [])
        return res["result"]

    def test_ruc_of_13_digits(self):
        self.assertEqual(self.ranges(HEADER, [RUC]), [[5, 18]])
        self.assertEqual(self.ranges("Clave 17083340970011 y 170833409700", [RUC]), [])   # 14 and 12 digits

    def test_literal_name_any_case(self):
        self.assertEqual(self.ranges(HEADER, ["NOMBRE DE PRUEBA"]), [[21, 37]])
        self.assertEqual(self.ranges("Contribuyente: Nombre de Prueba", ["NOMBRE DE PRUEBA"]), [[15, 31]])

    def test_overlapping_and_adjacent_matches_merge(self):
        self.assertEqual(self.ranges(HEADER, [RUC, r"1708334097001 / NOMBRE", " DE PRUEBA"]), [[5, 37]])
        self.assertEqual(self.ranges("aaa", ["a*", "x?"]), [[0, 3]])          # empty matches never loop

    def test_segments(self):
        res = self.node(f"out(censorSegments({json.dumps(HEADER)}, [[5, 18], [21, 37]]));", "censorSegments")
        self.assertEqual(res["result"], [{"text": "RUC: ", "censored": False},
                                         {"text": "1708334097001", "censored": True},
                                         {"text": " / ", "censored": False},
                                         {"text": "NOMBRE DE PRUEBA", "censored": True}])


class CensorWrapTest(NodeCase):
    def test_text_node_is_split_into_blurred_spans(self):
        body = (f"const p = new N(1, null, 'DIV'); const t = new N(3, {json.dumps(HEADER)}); p.appendChild(t);\n"
                f"const n = wrapTextNode(doc, t, {json.dumps([RUC, 'NOMBRE DE PRUEBA'])});\n"
                "out({ n, kids: p.childNodes.map((c) => ({ text: c.textContent, mark: c.nodeType === 1 ? c.getAttribute('data-tutorial-censor') : null,"
                " style: c.props })) });")
        res = self.node(body, "wrapTextNode")
        self.assertEqual(res["logged"], [])
        kids = res["result"]["kids"]
        self.assertEqual(res["result"]["n"], 2)
        self.assertEqual([k["text"] for k in kids], ["RUC: ", "1708334097001", " / ", "NOMBRE DE PRUEBA"])
        self.assertEqual([k["mark"] for k in kids], [None, "text", None, "text"])
        for k in (kids[1], kids[3]):
            self.assertEqual(k["style"]["filter"], "blur(8px) !important")
            self.assertEqual(k["style"]["user-select"], "none !important")

    def test_no_match_and_own_spans_are_left_alone(self):
        body = (f"const p = new N(1, null, 'DIV'); const t = new N(3, 'Comprobantes emitidos'); p.appendChild(t);\n"
                f"const s = new N(1, null, 'SPAN'); s.setAttribute('data-tutorial-censor', 'text');"
                f" const u = new N(3, '1708334097001'); s.appendChild(u);\n"
                f"const k = new N(1, null, 'SCRIPT'); const v = new N(3, 'var ruc = \"1708334097001\"'); k.appendChild(v);\n"
                f"out([wrapTextNode(doc, t, {json.dumps([RUC])}), wrapTextNode(doc, u, {json.dumps([RUC])}),"
                f" wrapTextNode(doc, v, {json.dumps([RUC])}), p.childNodes.length, s.childNodes.length]);")
        self.assertEqual(self.node(body, "wrapTextNode")["result"], [0, 0, 0, 1, 1])

    def test_injected_source_is_self_contained_and_silent(self):
        cfg = {"selectors": ["#cabecera"], "text": [RUC]}
        res = self.node(f"const src = censorSource({json.dumps(cfg)});\n"
                        "out({ console: /console\\./.test(src), parses: (() => { try { new Function(src); return true; }"
                        " catch (e) { return String(e); } })(), observer: /MutationObserver/.test(src) });",
                        "censorSource")
        self.assertEqual(res["result"], {"console": False, "parses": True, "observer": True})

    def test_invalid_pattern_error_does_not_echo_it(self):
        res = self.node("try { censorSource({ text: ['\\\\d{13}', 'JUAN PEREZ('] }); out('ok'); }"
                        " catch (e) { out(String(e.message)); }", "censorSource")
        self.assertEqual(res["result"], "censor.text[1] no es una expresión regular válida")


class TabsPatchTest(NodeCase):
    """S5: inside the surface, {active, currentWindow} resolves to the tab of target_tab."""

    TABS = r"""
const tabs = [
  { id: 1, url: "https://srienlinea.sri.gob.ec/a", lastAccessed: 10, active: false },
  { id: 2, url: "https://srienlinea.sri.gob.ec/b", lastAccessed: 30, active: false },
  { id: 9, url: "chrome-extension://x/popup.html", lastAccessed: 40, active: true },
];
const asked = [];
const match = (q) => tabs.filter((t) => (!q.url || t.url.startsWith(q.url.replace("*", ""))) && (!q.active || t.active));
const g = { chrome: { tabs: { query(q, cb) { asked.push(q); const r = match(q); if (cb) { cb(r); return undefined; } return Promise.resolve(r); } } } };
"""

    def run_patch(self, body):
        return self.node(self.TABS + body, "patchTabs, tabsPatchSource")["result"]

    def test_active_query_returns_the_target_tab(self):
        res = self.run_patch("patchTabs(g, 'https://srienlinea.sri.gob.ec/*');\n"
                             "const p = await g.chrome.tabs.query({ active: true, currentWindow: true });\n"
                             "const c = await new Promise((r) => g.chrome.tabs.query({ active: true, currentWindow: true }, r));\n"
                             "out({ p: p.map((t) => t.id), c: c.map((t) => t.id), asked });")
        self.assertEqual(res["p"], [2])
        self.assertEqual(res["c"], [2])

    def test_other_queries_pass_through_and_patch_is_idempotent(self):
        res = self.run_patch("const first = patchTabs(g, 'https://srienlinea.sri.gob.ec/*');\n"
                             "const again = patchTabs(g, 'https://srienlinea.sri.gob.ec/*');\n"
                             "const all = await g.chrome.tabs.query({});\n"
                             "out({ first, again, all: all.map((t) => t.id) });")
        self.assertEqual(res, {"first": True, "again": False, "all": [1, 2, 9]})

    def test_without_a_target_tab_the_active_query_falls_back(self):
        res = self.run_patch("patchTabs(g, 'https://otro.example/*');\n"
                             "const p = await g.chrome.tabs.query({ active: true, currentWindow: true });\n"
                             "out(p.map((t) => t.id));")
        self.assertEqual(res, [9])

    def test_source_runs_on_a_page_without_chrome_tabs(self):
        res = self.run_patch("const src = tabsPatchSource('https://srienlinea.sri.gob.ec/*');\n"
                             "new Function('globalThis', src)({});\n"
                             "new Function('globalThis', src)(g);\n"
                             "const p = await g.chrome.tabs.query({ active: true, currentWindow: true });\n"
                             "out(p.map((t) => t.id));")
        self.assertEqual(res, [2])

    def test_window_close_keeps_the_surface_open(self):
        # Perseo XML 1.2.1 closes its side panel with window.close() after "Llenar en el SRI": the recorded
        # surface page must survive it (the step closes the panel with `close: popup`).
        res = self.run_patch("let closed = 0;\n"
                             "g.close = () => { closed++; };\n"
                             "patchTabs(g, 'https://srienlinea.sri.gob.ec/*');\n"
                             "g.close();\n"
                             "out({ closed });")
        self.assertEqual(res, {"closed": 0})


class NewTabTest(NodeCase):
    """follow: tab adopts the tab the click opened (not the main tab, not a surface)."""

    def test_pick_new_tab(self):
        res = self.node("const tabs = [{ targetId: 'A', active: false }, { targetId: 'S', active: false },"
                        " { targetId: 'N1', active: false }, { targetId: 'N2', active: true }];\n"
                        "out([pickNewTab(tabs, ['A', 'S'])?.targetId, pickNewTab(tabs.slice(0, 3), ['A', 'S'])?.targetId,"
                        " pickNewTab(tabs.slice(0, 2), ['A', 'S']) ?? null]);", "pickNewTab")
        self.assertEqual(res["result"], ["N2", "N1", None])


if __name__ == "__main__":
    unittest.main()
