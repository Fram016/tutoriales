"""tools/lint.py: tutorial.yaml v2 against reglas/reglas-video.md before generating.

Run: .venv/Scripts/python.exe -m unittest discover -s tests -v
"""
import copy
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import yaml

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import common  # noqa: E402
import lint  # noqa: E402

BASE = {
    "title": "Cómo crear un contacto en Nexo CRM",
    "product": "Nexo CRM",
    "device": "desktop",
    "glossary": {"contacto": ["cliente", "prospecto", "registro"]},
    "steps": [
        {"id": "login", "narration": "Primero inicias sesión con tu correo y tu contraseña.",
         "actions": [{"type": {"into": "#login-email", "text": "env:NEXO_USER"}},
                     {"type": {"into": "#login-password", "text": "env:NEXO_PASSWORD"}},
                     {"click": "#btn-login"}, {"wait": "#nav"}]},
        {"id": "nuevo", "narration": "Haz clic en el botón Nuevo contacto para abrir el formulario.",
         "actions": [{"click": "#btn-nuevo"}, {"wait": "#c-nombre"}]},
        {"id": "datos", "narration": "Escribe el nombre, el apellido y el correo del contacto nuevo.",
         "actions": [{"type": {"into": "#c-nombre", "text": "Sofía"}},
                     {"type": {"into": "#c-email", "text": "sofia@cafe.com"}}]},
        {"id": "guardar", "narration": "Haz clic en Guardar y el contacto aparece primero en la lista.",
         "actions": [{"click": "#btn-guardar"}, {"result": "#toast"}, {"highlight": "tr.new"}]},
    ],
    "videos": [
        {"id": "tutorial", "type": "TUT", "format": "16:9", "steps": "all",
         "opening": {"narration": "Aquí aprendes a crear un contacto.",
                     "text": "Aprende a crear un contacto"},
         "closing": {"narration": "Siguiente video: registrar una oportunidad.",
                     "text": "Siguiente: registrar una oportunidad"}},
        {"id": "redes", "type": "RED", "format": "9:16", "steps": ["nuevo", "datos", "guardar"],
         "opening": {"narration": "¿Lo conociste en una feria?", "text": "¿Conociste a alguien en una feria?"},
         "closing": {"narration": "Mira el tutorial completo.", "text": "Mira el tutorial completo"},
         "narration": {"nuevo": "Abre Nuevo contacto y prepara el formulario de una vez sin perder tiempo.",
                       "datos": "Escribe el nombre y el correo que te dieron en la feria, nada más hace falta.",
                       "guardar": "Guarda y el contacto queda primero en la lista, listo para tu seguimiento."}},
    ],
}


def run_lint(mutate=None):
    data = copy.deepcopy(BASE)
    if mutate:
        mutate(data)
    return lint.lint_data(data)


def video(data, vid):
    return next(v for v in data["videos"] if v["id"] == vid)


class BaseTest(unittest.TestCase):
    def assertRule(self, messages, rule, needle=""):
        hits = [m for m in messages if m.startswith(f"[{rule}]") and needle in m]
        self.assertTrue(hits, f"no [{rule}] {needle!r} in {messages}")

    def assertNoRule(self, messages, rule):
        self.assertFalse([m for m in messages if m.startswith(f"[{rule}]")], messages)


class CleanTutorialTest(BaseTest):
    def test_base_has_no_errors_or_warnings(self):
        errors, warnings = run_lint()
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])


class LanguageTest(BaseTest):
    def test_L1_voseo_in_narration_is_an_error(self):
        errors, _ = run_lint(lambda d: d["steps"][1].update(narration="Ingresá al formulario y completá el nombre."))
        self.assertRule(errors, "L1", "«ingresá»")
        self.assertRule(errors, "L1", "«completá»")

    def test_L1_voseo_in_opening_text_and_typed_demo_data(self):
        def mutate(d):
            video(d, "tutorial")["opening"]["text"] = "Aprendé a crear un contacto"
            d["steps"][2]["actions"][0]["type"]["text"] = "Vos sos el contacto"
        errors, _ = run_lint(mutate)
        self.assertRule(errors, "L1", "videos.tutorial.opening.text: voseo «aprendé»")
        self.assertRule(errors, "L1", "steps.datos.type: voseo «vos»")
        self.assertRule(errors, "L1", "«sos»")

    def test_L1_second_person_vos_forms(self):
        errors, _ = run_lint(lambda d: d["steps"][1].update(narration="Si tenés permisos, podés seguir."))
        self.assertRule(errors, "L1", "«tenés» → usa tú («tienes»)")
        self.assertRule(errors, "L1", "«podés»")

    def test_L1_allowlist_and_proper_names_pass(self):
        text = "Así está aquí: ahora podrás ver a Sofía Ramírez de Café Montaña; además aparecerá en la lista."
        self.assertEqual(lint.language_issues(text), [])

    def test_L1_env_typed_text_is_not_checked(self):
        errors, _ = run_lint(lambda d: d["steps"][0]["actions"][0]["type"].update(text="env:INGRESÁ"))
        self.assertNoRule(errors, "L1")

    def test_L2_tocamos_on_desktop_is_an_error(self):
        errors, _ = run_lint(lambda d: d["steps"][1].update(narration="Tocamos el botón Nuevo contacto."))
        self.assertRule(errors, "L2", "«Tocamos» en escritorio")

    def test_L2_clic_on_mobile_is_an_error_and_toca_passes(self):
        errors, _ = run_lint(lambda d: d.update(device="mobile"))
        self.assertRule(errors, "L2", "«clic» en celular")
        def mobile(d):
            d["device"] = "mobile"
            for s in d["steps"]:
                s["narration"] = s["narration"].replace("Haz clic en", "Toca")
        errors, _ = run_lint(mobile)
        self.assertNoRule(errors, "L2")

    def test_L3_glossary_synonym_is_an_error(self):
        errors, _ = run_lint(lambda d: d["steps"][3].update(narration="Guarda y el cliente aparece en la lista."))
        self.assertRule(errors, "L3", "«cliente» → el glosario dice «contacto»")

    def test_L3_plural_synonym_is_an_error(self):
        errors, _ = run_lint(lambda d: d["steps"][3].update(narration="Así ves tus prospectos en la lista."))
        self.assertRule(errors, "L3", "«prospectos»")

    def test_L3_quoted_ui_option_is_allowed(self):
        for text in ("En Etapa eliges «Prospecto».", "En Etapa eliges “Prospecto”.", 'En Etapa eliges "Prospecto".'):
            errors, _ = run_lint(lambda d: d["steps"][2].update(narration=text))
            self.assertNoRule(errors, "L3")

    def test_L4_aca_is_an_error(self):
        errors, _ = run_lint(lambda d: d["steps"][1].update(narration="Acá abres el formulario."))
        self.assertRule(errors, "L4", "«Acá» → usa «aquí»")

    def test_L4_cargar_as_verb_is_an_error_but_the_noun_passes(self):
        errors, _ = run_lint(lambda d: d["steps"][1].update(narration="Para cargar un contacto, abre el formulario."))
        self.assertRule(errors, "L4", "«cargar» → usa «registrar»")
        errors, _ = run_lint(lambda d: d["steps"][1].update(narration="Espera la carga de la página."))
        self.assertNoRule(errors, "L4")

    def test_L4_more_idioms(self):
        for word in ("ahorita", "chévere", "platicamos", "allá"):
            errors, _ = run_lint(lambda d: d["steps"][1].update(narration=f"Esto es {word} con el formulario."))
            self.assertRule(errors, "L4", word)


class StructureTest(BaseTest):
    def test_E1_missing_opening_or_closing(self):
        errors, _ = run_lint(lambda d: video(d, "tutorial").pop("opening"))
        self.assertRule(errors, "E1", "videos.tutorial.opening: obligatorio")
        errors, _ = run_lint(lambda d: video(d, "redes").pop("closing"))
        self.assertRule(errors, "E1", "videos.redes.closing: obligatorio")

    def test_E1_only_title_or_listo(self):
        def mutate(d):
            video(d, "tutorial")["opening"] = {"text": d["title"]}
            video(d, "tutorial")["closing"] = {"narration": "¡Listo!", "text": "¡Listo!"}
        errors, _ = run_lint(mutate)
        self.assertRule(errors, "E1", "opening: no puede ser solo el título")
        self.assertRule(errors, "E1", "closing: no puede ser solo el título ni «¡Listo!»")

    def test_E1_old_intro_outro_keys_are_errors(self):
        errors, _ = run_lint(lambda d: d.update(intro={"seconds": 3}, outro={"text": "¡Listo!"}))
        self.assertRule(errors, "E1", "'intro' ya no existe")
        self.assertRule(errors, "E1", "'outro' ya no existe")

    def test_TUT1_opening_objective_and_next_video(self):
        def mutate(d):
            video(d, "tutorial")["opening"] = {"narration": "Bienvenido a Nexo CRM.", "text": "Contactos"}
            video(d, "tutorial")["closing"] = {"narration": "Ya puedes registrar contactos.", "text": "Fin del tutorial"}
        errors, _ = run_lint(mutate)
        self.assertRule(errors, "TUT1", "«En este video aprendes a…»")
        self.assertRule(errors, "TUT1", "siguiente video")

    def test_RED1_hook_and_call_to_action(self):
        def mutate(d):
            video(d, "redes")["opening"] = {"narration": "Crea contactos.", "text": "Nexo CRM"}
            video(d, "redes")["closing"] = {"narration": "Eso fue todo.", "text": "Nexo CRM"}
        errors, _ = run_lint(mutate)
        self.assertRule(errors, "RED1", "pregunta o un problema")
        self.assertRule(errors, "RED1", "llamado a la acción")

    def test_PRO6_and_NOV5_closings(self):
        def mutate(d):
            d["videos"].append({"id": "promo", "type": "PRO", "format": "16:9", "steps": ["guardar"],
                                "opening": {"narration": "¿Pierdes contactos?"},
                                "closing": {"narration": "Nexo CRM, para vender más."}})
            d["videos"].append({"id": "nov", "type": "NOV", "format": "16:9", "steps": ["guardar"],
                                "opening": {"narration": "Nuevo: el resaltado de filas."},
                                "closing": {"narration": "Hasta pronto."}})
        errors, _ = run_lint(mutate)
        self.assertRule(errors, "PRO6", "videos.promo.closing")
        self.assertRule(errors, "NOV5", "videos.nov.closing")
        def good(d):
            mutate(d)
            video(d, "promo")["closing"]["narration"] = "Pruébalo gratis en nexocrm.com."
            video(d, "nov")["closing"]["narration"] = "Mira el tutorial completo en el enlace."
        errors, _ = run_lint(good)
        self.assertNoRule(errors, "PRO6")
        self.assertNoRule(errors, "NOV5")

    def test_E2_subset_unknown_and_order(self):
        errors, _ = run_lint(lambda d: video(d, "redes").update(steps=["guardar", "nuevo", "nada"]))
        self.assertRule(errors, "E2", "pasos que no existen: nada")
        self.assertRule(errors, "E2", "respetar el orden")

    def test_E2_form_split_into_several_steps_warns(self):
        def mutate(d):
            d["steps"].insert(3, {"id": "empresa", "narration": "Escribe la empresa del contacto nuevo.",
                                  "actions": [{"type": {"into": "#c-empresa", "text": "Café Montaña"}},
                                              {"select": {"in": "#c-etapa", "option": "Prospecto"}}]})
        errors, warnings = run_lint(mutate)
        self.assertEqual(errors, [])
        self.assertRule(warnings, "E2", "'empresa' sigue llenando el mismo formulario")


class TypeRulesTest(BaseTest):
    def test_RED_must_be_vertical(self):
        errors, _ = run_lint(lambda d: video(d, "redes").update(format="16:9"))
        self.assertRule(errors, "RED5", "9:16")

    def test_RED3_login_is_an_error(self):
        errors, _ = run_lint(lambda d: video(d, "redes").update(steps=["login", "nuevo", "datos", "guardar"]))
        self.assertRule(errors, "RED3", "omite el login (login)")

    def test_TUT_vertical_warns(self):
        errors, warnings = run_lint(lambda d: video(d, "tutorial").update(format="9:16"))
        self.assertNoRule(errors, "TUT")
        self.assertRule(warnings, "TUT", "16:9")

    def test_RED1_step_count_warns(self):
        _, warnings = run_lint(lambda d: video(d, "redes").update(steps=["nuevo", "guardar"]))
        self.assertRule(warnings, "RED1", "2 pasos")

    def test_RED2_estimated_duration_warns(self):
        long = " ".join(["palabra"] * 60)
        _, warnings = run_lint(lambda d: video(d, "redes")["narration"].update(datos=long))
        self.assertRule(warnings, "RED2", "duración estimada")

    def test_RED1_hook_length_warns(self):
        _, warnings = run_lint(lambda d: video(d, "redes")["opening"].update(
            narration="¿Conociste a alguien en una feria y no sabes dónde anotar sus datos?"))
        self.assertRule(warnings, "RED1", "gancho de ~")

    def test_PRO3_and_NOV3_warn(self):
        def mutate(d):
            d["videos"].append({"id": "promo", "type": "PRO", "format": "16:9", "steps": ["nuevo", "datos", "guardar"],
                                "opening": {"narration": "¿Pierdes contactos?"},
                                "closing": {"narration": "Pruébalo gratis en nexocrm.com."}})
            d["videos"].append({"id": "nov", "type": "NOV", "format": "16:9", "steps": "all",
                                "opening": {"narration": "Nuevo: el resaltado de filas."},
                                "closing": {"narration": "Mira el tutorial completo."}})
        _, warnings = run_lint(mutate)
        self.assertRule(warnings, "PRO3", "más de 2 interacciones")
        self.assertRule(warnings, "NOV3", "4 pasos")

    def test_A2_closing_and_E1_opening_length_warn(self):
        def mutate(d):
            video(d, "tutorial")["closing"]["narration"] = ("En el siguiente video aprendes a registrar una "
                                                            "oportunidad de venta para este contacto nuevo.")
            video(d, "tutorial")["opening"]["narration"] = ("En este video aprendes a crear un contacto nuevo "
                                                            "con todos sus datos en Nexo CRM.")
        _, warnings = run_lint(mutate)
        self.assertRule(warnings, "A2", "videos.tutorial.closing")
        self.assertRule(warnings, "E1", "videos.tutorial.opening")

    def test_T3_long_title_warns(self):
        _, warnings = run_lint(lambda d: d.update(
            title="Cómo crear tu primer contacto en Nexo CRM con nombre, apellido, correo, empresa, cargo y teléfono"))
        self.assertRule(warnings, "T3", "2 líneas")

    def test_T3_wrap_never_splits_the_product(self):
        lines = lint.wrap("Cómo crear tu primer contacto en Nexo CRM", "Nexo CRM", 37)
        self.assertIn("Nexo CRM", lines[-1])


class LintEntryPointTest(BaseTest):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(setattr, common, "PROJECTS", common.PROJECTS)
        common.PROJECTS = Path(self.tmp.name)
        self.pdir = common.PROJECTS / "crm"
        self.pdir.mkdir()

    def write(self, data):
        (self.pdir / "tutorial.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")

    def test_lint_returns_warnings(self):
        data = copy.deepcopy(BASE)
        video(data, "tutorial")["format"] = "9:16"
        self.write(data)
        with redirect_stdout(io.StringIO()):
            warnings = lint.lint("crm")
        self.assertRule(warnings, "TUT", "16:9")

    def test_lint_raises_listing_every_error(self):
        data = copy.deepcopy(BASE)
        data["steps"][1]["narration"] = "Acá tocamos Nuevo contacto, ingresá los datos."
        self.write(data)
        with self.assertRaises(common.PipelineError) as ctx, redirect_stdout(io.StringIO()):
            lint.lint("crm")
        message = str(ctx.exception)
        for rule in ("[L1]", "[L2]", "[L4]"):
            self.assertIn(rule, message)

    def test_cli_exit_codes(self):
        self.write(BASE)
        script = (f"import sys; sys.path.insert(0, {str(TOOLS)!r}); import common, pathlib; "
                  f"common.PROJECTS = pathlib.Path({self.tmp.name!r}); import lint; "
                  "sys.argv = ['lint.py', 'crm']; common.main_guard(lint.main)")
        ok = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(ok.returncode, 0, ok.stderr)
        bad = copy.deepcopy(BASE)
        bad["steps"][1]["narration"] = "Ingresá al formulario."
        self.write(bad)
        fail = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(fail.returncode, 1)
        self.assertIn("[L1]", fail.stderr)


if __name__ == "__main__":
    unittest.main()
