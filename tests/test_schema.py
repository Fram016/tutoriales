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


class SchemaTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
