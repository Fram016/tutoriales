"""tutorial.yaml v2 schema (odd/tasks/reglas-video.md L2) and the normalized videos() view.

Run: .venv/Scripts/python.exe -m unittest discover -s tests -v
"""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import common  # noqa: E402

BASE = {
    "title": "Cómo crear un contacto en Nexo CRM",
    "product": "Nexo CRM",
    "steps": [
        {"id": "login", "narration": "Entra con tu correo.", "actions": [{"click": "#a"}]},
        {"id": "nuevo", "narration": "Haz clic en Nuevo contacto.", "actions": [{"focus": "#b"}]},
        {"id": "guardar", "narration": "Guarda el contacto.", "actions": [{"result": "#toast"}, {"highlight": "tr.new"}]},
    ],
    "videos": [
        {"id": "tutorial", "type": "TUT", "format": "16:9", "steps": "all",
         "opening": {"narration": "En este video aprendes a crear un contacto.", "text": "Crea un contacto"},
         "requirements": {"narration": "Necesitas una cuenta.", "text": "Necesitas una cuenta"},
         "closing": {"narration": "En el siguiente video registras una oportunidad.", "text": "Siguiente"}},
        {"id": "redes", "type": "RED", "format": "9:16", "steps": ["nuevo", "guardar"],
         "opening": {"narration": "¿Conociste a alguien en una feria?", "text": "¿Una feria?"},
         "closing": {"narration": "Mira el tutorial completo.", "text": "Mira el tutorial completo"},
         "narration": {"guardar": "Listo, guardado."}},
    ],
}


class YamlCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(setattr, common, "PROJECTS", common.PROJECTS)
        common.PROJECTS = Path(self.tmp.name)
        (common.PROJECTS / "crm").mkdir()

    def load(self, data):
        (common.PROJECTS / "crm" / "tutorial.yaml").write_text(
            yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        return common.load_tutorial("crm")

    def assertRejects(self, data, fragment):
        with self.assertRaises(common.PipelineError) as ctx:
            self.load(data)
        self.assertIn(fragment, str(ctx.exception))


class SchemaTest(YamlCase):
    def test_valid_v2_loads(self):
        self.assertEqual(self.load(BASE)["title"], BASE["title"])

    def test_missing_title_and_steps(self):
        for key in ("title", "steps"):
            data = copy.deepcopy(BASE)
            del data[key]
            with self.subTest(key=key):
                self.assertRejects(data, f"falta la clave '{key}'")

    def test_removed_v1_keys(self):
        data = copy.deepcopy(BASE)
        data["intro"] = {"seconds": 3}
        self.assertRejects(data, "'intro' ya no existe en v2")
        data = copy.deepcopy(BASE)
        data["steps"][0]["summary"] = True
        self.assertRejects(data, "'summary' ya no existe en v2")

    def test_duplicate_ids(self):
        data = copy.deepcopy(BASE)
        data["steps"][1]["id"] = "login"
        self.assertRejects(data, "cada paso necesita un 'id' único")
        data = copy.deepcopy(BASE)
        data["videos"][1]["id"] = "tutorial"
        self.assertRejects(data, "video tutorial: el 'id' está repetido")

    def test_video_steps_must_exist_and_keep_order(self):
        data = copy.deepcopy(BASE)
        data["videos"][1]["steps"] = ["nuevo", "fantasma"]
        self.assertRejects(data, "pasos que no existen en 'steps': fantasma")
        data = copy.deepcopy(BASE)
        data["videos"][1]["steps"] = ["guardar", "nuevo"]
        self.assertRejects(data, "orden de la lista principal (E2)")

    def test_type_and_format_enums(self):
        data = copy.deepcopy(BASE)
        data["videos"][0]["type"] = "VLOG"
        self.assertRejects(data, "'type' tiene que ser uno de TUT, RED, PRO, NOV")
        data = copy.deepcopy(BASE)
        data["videos"][0]["format"] = "4:3"
        self.assertRejects(data, "'format' tiene que ser \"16:9\" o \"9:16\"")

    def test_opening_and_closing_required(self):
        for card in ("opening", "closing"):
            data = copy.deepcopy(BASE)
            del data["videos"][1][card]
            with self.subTest(card=card):
                self.assertRejects(data, f"video redes: {card}: falta")
        data = copy.deepcopy(BASE)
        data["videos"][0]["closing"]["narration"] = " "
        self.assertRejects(data, "video tutorial: closing: falta 'narration' (E1)")

    def test_requirements_only_in_tut(self):
        data = copy.deepcopy(BASE)
        data["videos"][1]["requirements"] = {"narration": "x", "text": "x"}
        self.assertRejects(data, "'requirements' solo existe en videos TUT")

    def test_unknown_action(self):
        data = copy.deepcopy(BASE)
        data["steps"][0]["actions"] = [{"teleport": "#x"}]
        self.assertRejects(data, "acción desconocida 'teleport'")

    def test_narration_override_must_name_used_steps(self):
        data = copy.deepcopy(BASE)
        data["videos"][1]["narration"] = {"login": "x"}
        self.assertRejects(data, "'narration' nombra pasos que este video no usa: login")

    def test_videos_normalized(self):
        tut = self.load(BASE)
        full, short = common.videos(tut)
        self.assertEqual([s["id"] for s in full["steps"]], ["login", "nuevo", "guardar"])
        self.assertEqual([s["number"] for s in short["steps"]], [2, 3])
        self.assertEqual(short["steps"][1]["narration"], "Listo, guardado.")
        self.assertEqual(short["steps"][0]["narration"], "Haz clic en Nuevo contacto.")
        self.assertIsNone(short["requirements"])
        self.assertEqual(full["requirements"]["text"], "Necesitas una cuenta")
        self.assertEqual([v["id"] for v in common.videos(tut, "redes")], ["redes"])

    def test_videos_unknown_or_missing(self):
        tut = self.load(BASE)
        with self.assertRaises(common.PipelineError) as ctx:
            common.videos(tut, "otro")
        self.assertIn("No existe el video 'otro'", str(ctx.exception))
        data = copy.deepcopy(BASE)
        del data["videos"]
        with self.assertRaises(common.PipelineError) as ctx:
            common.videos(self.load(data))
        self.assertIn("falta la clave 'videos'", str(ctx.exception))


    def test_omit_is_a_list_of_selectors(self):
        for bad in ("#c-email", [3], [""]):
            data = copy.deepcopy(BASE)
            data["videos"][1]["omit"] = bad
            with self.subTest(omit=bad):
                self.assertRejects(data, "video redes: 'omit' tiene que ser una lista de selectores")
        data = copy.deepcopy(BASE)
        data["videos"][1]["omit"] = ["#c-email", "#c-stage"]
        full, short = common.videos(self.load(data))
        self.assertEqual(short["omit"], ["#c-email", "#c-stage"])
        self.assertEqual(full["omit"], [])
        self.assertEqual([s["number"] for s in short["steps"]], [2, 3])   # numbering unchanged

    def test_opening_text_is_optional(self):
        data = copy.deepcopy(BASE)
        del data["videos"][0]["opening"]["text"]
        tut = self.load(data)
        self.assertNotIn("text", common.videos(tut, "tutorial")[0]["opening"])
        data["videos"][0]["opening"]["text"] = 3
        self.assertRejects(data, "video tutorial: opening: 'text' tiene que ser texto")
        data = copy.deepcopy(BASE)
        del data["videos"][0]["closing"]["text"]
        self.assertRejects(data, "video tutorial: closing: falta 'text' (E1)")

    def test_brand_accent_defaults_to_primary(self):
        data = copy.deepcopy(BASE)
        data["brand"] = {"primary": "#6d28d9", "background": "#1e1b4b"}
        brand = self.load(data)["brand"]
        self.assertEqual(brand["accent"], "#6d28d9")
        self.assertEqual(brand["on_surface"], "#ffffff")
        self.assertNotIn("surface", brand)
        data["brand"] = {"primary": "#6d28d9", "accent": "#a78bfa", "surface": "#2e1065", "on_surface": "#f5f3ff"}
        brand = self.load(data)["brand"]
        self.assertEqual((brand["accent"], brand["surface"], brand["on_surface"]),
                         ("#a78bfa", "#2e1065", "#f5f3ff"))

    def test_brand_colors_are_strings(self):
        for key in ("surface", "on_surface", "accent"):
            data = copy.deepcopy(BASE)
            data["brand"] = {"primary": "#6d28d9", key: 12}
            with self.subTest(key=key):
                self.assertRejects(data, f"'brand.{key}' tiene que ser texto")
        data = copy.deepcopy(BASE)
        data["brand"] = ["#6d28d9"]
        self.assertRejects(data, "'brand' tiene que ser un mapa")


POPUP = {"url": "chrome-extension://jakigokhcbfpebeiolidapdkeooiapeb/popup.html", "size": [420, 640], "dpr": 2,
         "anchor": "top-right", "target_tab": "https://srienlinea.sri.gob.ec/*", "icon": "brand/icon48.png"}


def with_popup(actions_by_step):
    """BASE with surfaces.popup and the given actions per step id."""
    data = copy.deepcopy(BASE)
    data["surfaces"] = {"popup": dict(POPUP)}
    for step in data["steps"]:
        if step["id"] in actions_by_step:
            step["actions"] = actions_by_step[step["id"]]
    return data


class CensorSchemaTest(YamlCase):
    """perseo-xml S3: censor {selectors, text} is validated without echoing the patterns."""

    def test_valid_censor_loads(self):
        data = copy.deepcopy(BASE)
        data["censor"] = {"selectors": ["#cabecera .ruc"], "text": [r"\b\d{13}\b", "NOMBRE DE PRUEBA", "env:CENSOR_NOMBRE"]}
        self.assertEqual(self.load(data)["censor"]["selectors"], ["#cabecera .ruc"])

    def test_censor_shape(self):
        cases = [(["#a"], "'censor' tiene que ser un mapa {selectors: [...], text: [...]}"),
                 ({"selectors": "#a"}, "'censor.selectors' tiene que ser una lista de selectores CSS"),
                 ({"selectors": [""]}, "'censor.selectors' tiene que ser una lista de selectores CSS"),
                 ({"text": r"\d{13}"}, "'censor.text' tiene que ser una lista de expresiones regulares"),
                 ({"text": [13]}, "'censor.text' tiene que ser una lista de expresiones regulares"),
                 ({"selectors": [], "text": [], "blur": 3}, "'censor' solo admite selectors, text y regex_flags")]
        for censor, message in cases:
            data = copy.deepcopy(BASE)
            data["censor"] = censor
            with self.subTest(censor=censor):
                self.assertRejects(data, message)

    def test_bad_regex_is_rejected_without_echoing_it(self):
        data = copy.deepcopy(BASE)
        data["censor"] = {"text": [r"\d{13}", "JUAN PEREZ("]}
        with self.assertRaises(common.PipelineError) as ctx:
            self.load(data)
        self.assertIn("'censor.text[1]' no es una expresión regular válida", str(ctx.exception))
        self.assertNotIn("JUAN", str(ctx.exception))

    def test_regex_flags(self):
        # N25: optional flags for the censor patterns (default "i", case-insensitive).
        for flags in ("i", "", "is", "imsu"):
            data = copy.deepcopy(BASE)
            data["censor"] = {"text": [r"C:\\Users\\[^\\]+"], "regex_flags": flags}
            with self.subTest(flags=flags):
                self.assertEqual(self.load(data)["censor"]["regex_flags"], flags)
        for flags in ("g", "ii", "x", 3):
            data = copy.deepcopy(BASE)
            data["censor"] = {"text": ["x"], "regex_flags": flags}
            with self.subTest(flags=flags):
                self.assertRejects(data, "'censor.regex_flags' solo admite las letras i, m, s, u (sin repetir)")

    def test_capture_passes_flags_and_hide_to_the_recorder(self):
        import capture
        self.assertEqual(capture.resolve_censor({"text": ["x"]}), {"selectors": [], "text": ["x"], "flags": "i"})
        self.assertEqual(capture.resolve_censor({"text": ["x"], "regex_flags": ""})["flags"], "")
        surfaces = capture.resolve_surfaces({"popup": {**POPUP, "hide": [".promo"]}})
        self.assertEqual(surfaces["popup"]["hide"], [".promo"])
        self.assertEqual(capture.resolve_surfaces({"popup": dict(POPUP)})["popup"]["hide"], [])


class SurfaceSchemaTest(YamlCase):
    """perseo-xml S5: surfaces + open/close, {in: surface} actions, follow: tab / back: main."""

    FLOW = {"login": [{"click": "#a"}, {"open": "popup"}, {"click": {"in": "popup", "sel": "#boton4"}},
                      {"hover": {"in": "popup", "sel": "#boton1"}}, {"scroll": {"in": "popup", "px": 200}},
                      {"result": {"in": "popup", "sel": "#estado"}}],
            "nuevo": [{"click": {"in": "popup", "sel": "#configure-folder"}}, {"follow": "tab"},
                      {"focus": "#b"}, {"back": "main"}, {"close": "popup"}]}

    def test_valid_surface_flow_loads(self):
        tut = self.load(with_popup(self.FLOW))
        self.assertEqual(tut["surfaces"]["popup"]["size"], [420, 640])
        self.assertEqual(tut["steps"][1]["actions"][1], {"follow": "tab"})

    def test_type_into_an_open_surface(self):
        # perseo-xml-v5: the side panel has its own login and client forms.
        flow = {"login": [{"open": "popup"},
                           {"type": {"in": "popup", "into": "#usuario", "text": "Prueba"}},
                           {"type": {"into": "#a", "text": "x"}}]}
        tut = self.load(with_popup(flow))
        self.assertEqual(tut["steps"][0]["actions"][1]["type"]["in"], "popup")
        self.assertRejects(with_popup({"login": [{"type": {"in": "popup", "into": "#u", "text": "a"}}]}),
                           "paso login: 'type' en 'popup' pero no está abierta (usa open: popup antes)")
        self.assertRejects(with_popup({"login": [{"open": "popup"}, {"type": {"in": "popup", "text": "a"}}]}),
                           "paso login: 'type' necesita {into: SELECTOR, text: TEXTO}")

    def test_surface_definition(self):
        cases = [({"url": None}, "surfaces.popup: falta 'url' (p.ej. chrome-extension://<id>/popup.html)"),
                 ({"size": [420]}, "surfaces.popup: 'size' tiene que ser [ancho, alto] en píxeles"),
                 ({"size": [420, "640"]}, "surfaces.popup: 'size' tiene que ser [ancho, alto] en píxeles"),
                 ({"size": [420, 1100]}, "surfaces.popup: 'size' no entra debajo de la barra (máximo 1888x1016)"),
                 ({"dpr": 0}, "surfaces.popup: 'dpr' tiene que ser un número entre 1 y 3"),
                 ({"anchor": "bottom"}, "surfaces.popup: 'anchor' tiene que ser top-right o top-left"),
                 ({"target_tab": 3}, "surfaces.popup: 'target_tab' tiene que ser un patrón de URL (texto)"),
                 ({"icon": ["a"]}, "surfaces.popup: 'icon' tiene que ser una ruta (texto)")]
        for change, message in cases:
            data = with_popup({})
            data["surfaces"]["popup"].update(change)
            with self.subTest(change=change):
                self.assertRejects(data, message)

    def test_surface_names(self):
        data = with_popup({})
        data["surfaces"] = [POPUP]
        self.assertRejects(data, "'surfaces' tiene que ser un mapa {nombre: {url, size, ...}}")
        data = with_popup({})
        data["surfaces"] = {"main": dict(POPUP)}
        self.assertRejects(data, "surfaces: 'main' está reservado para la pestaña principal")
        data = with_popup({})
        data["surfaces"] = {"Pop Up": dict(POPUP)}
        self.assertRejects(data, "surfaces: el nombre 'Pop Up' tiene que ir en minúsculas (letras, números, - o _)")

    def test_open_and_close_order(self):
        cases = [({"login": [{"open": "panel"}]}, "paso login: 'open' nombra una superficie que no existe en 'surfaces': panel"),
                 ({"login": [{"open": "popup"}, {"open": "popup"}]}, "paso login: 'open: popup' pero ya está abierta"),
                 ({"login": [{"close": "popup"}]}, "paso login: 'close: popup' pero no está abierta"),
                 ({"login": [{"open": "popup"}, {"close": "popup"}], "nuevo": [{"close": "popup"}]},
                  "paso nuevo: 'close: popup' pero no está abierta")]
        for flow, message in cases:
            with self.subTest(message=message):
                self.assertRejects(with_popup(flow), message)

    def test_actions_in_a_surface(self):
        cases = [({"login": [{"click": {"in": "popup", "sel": "#boton4"}}]},
                  "paso login: 'click' en 'popup' pero no está abierta (usa open: popup antes)"),
                 ({"login": [{"open": "popup"}, {"hover": {"in": "panel", "sel": "#x"}}]},
                  "paso login: 'hover' nombra una superficie que no existe en 'surfaces': panel"),
                 ({"login": [{"open": "popup"}, {"click": {"in": "popup"}}]},
                  "paso login: 'click' en una superficie necesita {in: SUPERFICIE, sel: SELECTOR}"),
                 ({"login": [{"open": "popup"}, {"scroll": {"in": "popup", "sel": "#x"}}]},
                  "paso login: 'scroll' en una superficie necesita {in: SUPERFICIE, px: PÍXELES}"),
                 ({"login": [{"click": {"sel": "#a"}}]},
                  "paso login: 'click' en una superficie necesita {in: SUPERFICIE, sel: SELECTOR}")]
        for flow, message in cases:
            with self.subTest(message=message):
                self.assertRejects(with_popup(flow), message)

    def test_follow_and_back(self):
        cases = [({"login": [{"follow": "window"}]}, "paso login: 'follow' solo admite 'tab'"),
                 ({"login": [{"follow": "tab"}, {"back": "popup"}]}, "paso login: 'back' solo admite 'main'"),
                 ({"login": [{"back": "main"}]}, "paso login: 'back: main' sin una pestaña seguida antes (follow: tab)"),
                 ({"login": [{"follow": "tab"}], "nuevo": [{"follow": "tab"}]},
                  "paso nuevo: 'follow: tab' con otra pestaña ya seguida (usa back: main antes)")]
        for flow, message in cases:
            with self.subTest(message=message):
                self.assertRejects(with_popup(flow), message)

    def test_hide_is_a_list_of_selectors(self):
        # N23: promotions of the extension window hidden in the take.
        data = with_popup({})
        data["surfaces"]["popup"]["hide"] = [".club-perseo", "#facturito"]
        self.assertEqual(self.load(data)["surfaces"]["popup"]["hide"], [".club-perseo", "#facturito"])
        for bad in (".promo", [""], [3]):
            data = with_popup({})
            data["surfaces"]["popup"]["hide"] = bad
            with self.subTest(hide=bad):
                self.assertRejects(data, "surfaces.popup: 'hide' tiene que ser una lista de selectores CSS (N23)")

    def test_ext_demo_example_is_valid(self):
        example = Path(__file__).resolve().parents[1] / "demo-apps" / "ext-demo" / "tutorial.example.yaml"
        data = yaml.safe_load(example.read_text(encoding="utf-8"))
        common.validate_tutorial(data)
        self.assertEqual(data["surfaces"]["popup"]["target_tab"], "http://127.0.0.1:8767/*")

    def test_plain_actions_are_unchanged(self):
        # PRESERVE: string selectors, type and select keep their shapes and messages.
        data = with_popup({"login": [{"click": "#a"}, {"scroll": 300}, {"type": {"into": "#n", "text": "x"}},
                                     {"select": {"in": "#etapa", "option": "Cliente"}}]})
        self.assertEqual(len(self.load(data)["steps"][0]["actions"]), 4)
        self.assertRejects(with_popup({"login": [{"select": {"in": "#etapa"}}]}),
                           "'select' necesita {in: SELECTOR, option: VALOR}")


PARTS = [{"n": 1, "title": "Configurar la carpeta"}, {"n": 2, "title": "Comprobantes emitidos"}]


def with_parts(parts_by_step, parts=PARTS):
    data = copy.deepcopy(BASE)
    data["parts"] = copy.deepcopy(parts)
    for step in data["steps"]:
        if step["id"] in parts_by_step:
            step["part"] = parts_by_step[step["id"]]
    return data


class RoundFourSchemaTest(YamlCase):
    """reglas-ronda4: parts (N16), step context (N17), optional TUT closing (N27)."""

    def test_parts_and_step_part_load(self):
        tut = self.load(with_parts({"login": 1, "nuevo": 2, "guardar": 2}))
        self.assertEqual(tut["parts"], PARTS)
        self.assertEqual([s["part"] for s in common.videos(tut, "tutorial")[0]["steps"]], [1, 2, 2])

    def test_parts_shape(self):
        cases = [({"n": 1}, "'parts' tiene que ser una lista de {n: NÚMERO, title: TÍTULO} (N16)"),
                 ([], "'parts' tiene que ser una lista de {n: NÚMERO, title: TÍTULO} (N16)"),
                 ([{"n": 0, "title": "A"}], "parts[0]: 'n' tiene que ser un número entero mayor que 0"),
                 ([{"n": True, "title": "A"}], "parts[0]: 'n' tiene que ser un número entero mayor que 0"),
                 ([{"n": 1, "title": " "}], "parts[0]: falta 'title'"),
                 ([{"n": 1, "title": "A"}, {"n": 1, "title": "B"}], "parts: la parte 1 está repetida")]
        for parts, message in cases:
            with self.subTest(parts=parts):
                self.assertRejects(with_parts({}, parts), message)

    def test_every_step_names_a_declared_part_in_order(self):
        self.assertRejects(with_parts({"login": 1, "nuevo": 2}),
                           "paso guardar: 'part' tiene que ser un número de 'parts' (N16)")
        self.assertRejects(with_parts({"login": 1, "nuevo": 3, "guardar": 3}),
                           "paso nuevo: 'part' tiene que ser un número de 'parts' (N16)")
        self.assertRejects(with_parts({"login": 2, "nuevo": 1, "guardar": 2}),
                           "paso nuevo: la parte 1 va después de la parte 2 (N16)")
        data = copy.deepcopy(BASE)
        data["steps"][0]["part"] = 1
        self.assertRejects(data, "paso login: 'part' tiene que ser un número de 'parts' (N16)")

    def test_step_context(self):
        data = copy.deepcopy(BASE)
        for step, ctx in zip(data["steps"], ("sri", "extension", "page")):
            step["context"] = ctx
        self.assertEqual([s["context"] for s in self.load(data)["steps"]], ["sri", "extension", "page"])
        data["steps"][1]["context"] = "perseo"
        self.assertRejects(data, "paso nuevo: 'context' tiene que ser sri, extension, page, chrome o computer (N17)")

    def test_tut_closing_is_optional(self):
        data = copy.deepcopy(BASE)
        del data["videos"][0]["closing"]
        full, short = common.videos(self.load(data))
        self.assertIsNone(full["closing"])
        self.assertEqual(short["closing"]["narration"], "Mira el tutorial completo.")
        # PRESERVE: a TUT closing that is present is still validated; RED keeps it required.
        data["videos"][0]["closing"] = {"narration": " ", "text": "x"}
        self.assertRejects(data, "video tutorial: closing: falta 'narration' (E1)")
        data = copy.deepcopy(BASE)
        del data["videos"][1]["closing"]
        self.assertRejects(data, "video redes: closing: falta")


if __name__ == "__main__":
    unittest.main()


class ManualFallbackSchemaTest(unittest.TestCase):
    """'Necesito el tutorial': when SRI's invisible captcha refuses the automated Consultar, a person repeats the
    click; the action is validated like the others."""

    def load(self, arg):
        import tempfile, yaml, common
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        old = common.PROJECTS; self.addCleanup(setattr, common, "PROJECTS", old)
        common.PROJECTS = Path(tmp.name)
        (common.PROJECTS / "p").mkdir()
        data = {"title": "T", "videos": [{"id": "tutorial", "type": "TUT", "format": "16:9", "steps": "all",
                                          "opening": {"narration": "Aprendes a consultar."}}],
                "steps": [{"id": "a", "narration": "Haz clic en Consultar.",
                           "actions": [{"click": "#b"}, {"manual_fallback": arg}]}]}
        (common.PROJECTS / "p" / "tutorial.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        return common.load_tutorial("p")

    def test_valid_manual_fallback(self):
        self.load({"until": "#tabla tr", "blocked": "Captcha incorrecta"})

    def test_manual_fallback_needs_until_and_blocked(self):
        import common
        with self.assertRaises(common.PipelineError):
            self.load({"until": "#tabla tr"})
