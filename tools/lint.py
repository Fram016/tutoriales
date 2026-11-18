"""Stage: lint. Checks tutorial.yaml v2 against reglas/reglas-video.md BEFORE anything is generated.

Usage: python tools/lint.py <slug>

Errors (exit 1, PipelineError) and warnings, each tagged with the rule ID it enforces:
  L1 voseo, L2 device verbs, L3 glossary synonyms, L4 regional idioms (narration, card texts,
  step titles; L1 also typed demo data), E1 opening/closing, E2 step lists, T3 title length,
  and the per-type rules of Parte 3 (TUT/RED/PRO/NOV: format, login, step count, estimated
  duration from narration at 2.6 words/s).
"""
from __future__ import annotations

import argparse
import re
import sys
import textwrap
import unicodedata

import yaml

from common import PipelineError, main_guard, project_dir

TYPES = ("TUT", "RED", "PRO", "NOV")
FORMATS = ("16:9", "9:16")
WORDS_PER_SECOND = 2.6
CAPTION_CHARS = 42
# Estimated duration ranges per type (seconds). Post-render errors are qa.py's job.
DURATION_RANGES = {"RED": (15, 35), "PRO": (20, 60), "NOV": (15, 30)}
TUT_CHAPTERS_AFTER = 300
# Minimum on-screen time of each block when it has little or no narration (cards, actions).
STEP_FLOOR, CARD_FLOOR = 1.5, 1.5
OPENING_MAX, CLOSING_MAX, HOOK_RANGE = 3.0, 2.5, (1.0, 2.0)

WORD = re.compile(r"[^\W\d_]+", re.UNICODE)

# L1: explicit voseo forms (hint = the tú form).
VOSEO = {
    "vos": "tú", "sos": "eres", "tenés": "tienes", "podés": "puedes", "sabés": "sabes",
    "querés": "quieres", "hacés": "haces", "ponés": "pones", "venís": "vienes", "decís": "dices",
    "elegís": "eliges", "seguís": "sigues", "pedís": "pides", "salís": "sales", "vivís": "vives",
    "hacé": "haz", "poné": "pon", "tené": "ten", "vení": "ven", "decí": "di", "salí": "sal",
    "elegí": "elige", "seguí": "sigue", "pedí": "pide", "escribí": "escribe", "abrí": "abre",
    "ingresá": "ingresa", "tocá": "toca", "completá": "completa", "mirá": "mira", "cerrá": "cierra",
    "borrá": "borra", "guardá": "guarda", "cargá": "registra", "andá": "ve", "fijate": "fíjate",
    "mirás": "miras", "contás": "cuentas", "probá": "prueba", "buscá": "busca",
}
# L1: words that end like a voseo form but are fine in tú Spanish.
VOSEO_ALLOW = {
    "está", "estás", "esté", "estés", "quizá", "quizás", "cafés", "bebés", "sofás", "mamás", "papás", "aquí", "allí", "ahí", "acá", "allá", "más", "jamás", "además", "atrás",
    "detrás", "demás", "sí", "así", "mí", "qué", "porqué", "sé", "dé", "té", "fe", "café", "bebé",
    "mamá", "papá", "sofá", "menú", "país", "maíz", "raíz", "anís", "después", "través", "inglés",
    "francés", "portugués", "japonés", "interés", "estrés", "cortés", "ciprés", "revés", "marqués",
    "será", "podrá", "tendrá", "habrá", "hará", "dirá", "sabrá", "querrá", "vendrá", "saldrá",
    "pondrá", "valdrá", "cabrá", "podrás", "tendrás", "habrás", "harás", "dirás", "sabrás",
    "querrás", "vendrás", "saldrás", "pondrás", "valdrás", "cabrás", "verás", "darás", "irás",
    "panamá", "canadá", "bogotá", "perú", "josé", "jesús",
}
# General voseo shape: stressed -á/-é/-í imperatives and -ás/-és/-ís present (2+ syllables).
VOSEO_SHAPE = re.compile(r"^[a-zñ]{2,}[aei]?(?:[áéí]|[áéí]s)$")
# Future tú/él forms (-arás, -erá, -irás...) look like voseo but are standard.
FUTURE = re.compile(r"(?:ar|er|ir|dr|br|rr)[áa]s?$|(?:ar|er|ir)á$")
TONIC = str.maketrans("áéí", "aei")

# L2: device verbs.
TOUCH = re.compile(r"\b(?:toc(?:a|as|amos|an|ar|ad|á|ando|ó|aste|ado|ará|arás)|toqu(?:e|es|emos|en|é))\b", re.I)
CLICK = re.compile(r"\b(?:clic|click|clics|clicks|cliquea\w*|clickea\w*|cliqu\w*)\b", re.I)

# L4: regional idioms -> neutral Ecuadorian Spanish (first: the rulebook's own examples).
IDIOMS = [
    (re.compile(r"\bacá\b", re.I), "acá", "aquí"),
    (re.compile(r"\bcarg(?:ar|amos|as|ás|á|an|ue|ues|uemos|uen|ando|ado|ada|ados|adas)\b", re.I),
     "cargar", "registrar"),
    (re.compile(r"(?<!\bla )(?<!\buna )(?<!\besta )(?<!\bsu )\bcarga\b", re.I), "carga", "registra"),
    (re.compile(r"\ballá\b", re.I), "allá", "allí"),
    (re.compile(r"\bahorita\b", re.I), "ahorita", "ahora"),
    (re.compile(r"\bchévere\b", re.I), "chévere", "genial"),
    (re.compile(r"\bplatic(?:ar|amos|as|a|an|ando|ado)\b|\bplatiqu\w*", re.I), "platicar", "conversar"),
    (re.compile(r"\bbacán\b", re.I), "bacán", "genial"),
    (re.compile(r"\bchido\b", re.I), "chido", "genial"),
    (re.compile(r"\blaburo\b", re.I), "laburo", "trabajo"),
    (re.compile(r"\bche\b", re.I), "che", "(quitar)"),
]

QUOTED = re.compile(r"“[^”]*”|\"[^\"]*\"|«[^»]*»|‘[^’]*’|(?<!\w)'[^']*'(?!\w)")

# E1 cues.
LEARN = re.compile(r"\baprend(?:es|erás) a\b|\bvas a aprender\b", re.I)
PROBLEM = re.compile(r"\?|\bno (?:sabes|puedes|encuentras|tienes)\b|\bte cuesta\b|\bpierdes\b|\bproblema\b|"
                     r"\bolvidas\b|\bse te\b|\bcansad[oa]\b|\bdifícil\b|\bsin perder\b|\bnunca más\b", re.I)
NEWS = re.compile(r"\bnuev[oa]s?\b|\bnovedad\b|\bahora (?:puedes|tienes|hay)\b|\bcambi[óo]\b|\bllega\b", re.I)
NEXT = re.compile(r"\bsiguiente\b|\bpróximo video\b", re.I)
RED_CTA = re.compile(r"\b(?:mira|guarda|sigue|comparte|visita|suscríbete|descubre|ve)\b", re.I)
PRO_CTA = re.compile(r"\bprueba gratis\b|\bpruébalo\b|\bgratis\b|\bcontáct\w*|\bcontacto\b|\bescríbenos\b|"
                     r"\benlace\b|\blink\b|\bvisita\b|\bwww\.|https?://|\.com\b|\bregístrate\b|\bagenda\b|"
                     r"\bsolicita\b|\bdescarga\b", re.I)
NOV_CTA = re.compile(r"\btutorial\b|\benlace\b|\blink\b", re.I)
LISTO = re.compile(r"^\W*(?:listo|eso es todo|fin|gracias|terminamos)\W*$", re.I)

PASSWORD = re.compile(r"pass|contrase|clave", re.I)
INTERACTIONS = {"click", "type", "select", "press", "scroll", "goto"}
QUIET = {"wait", "pause", "hover", "focus"}


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return " ".join(WORD.findall("".join(c for c in text if not unicodedata.combining(c))))


def strip_quotes(text: str) -> str:
    return QUOTED.sub(" ", text)


def words(text: str | None) -> int:
    return len(WORD.findall(text or ""))


def seconds(text: str | None) -> float:
    return words(text) / WORDS_PER_SECOND


def voseo_hint(word: str) -> str:
    return VOSEO.get(word, word.translate(TONIC))


def voseo_hits(text: str) -> list[str]:
    hits = []
    for m in WORD.finditer(text):
        raw = m.group(0)
        word = raw.lower()
        if word in VOSEO:
            hits.append(word)
            continue
        if word in VOSEO_ALLOW or not VOSEO_SHAPE.match(word) or FUTURE.search(word):
            continue
        # Capitalised mid-sentence words are proper names (Ramírez, José...).
        before = text[:m.start()].rstrip()
        if raw[0].isupper() and before and before[-1] not in ".!?¡¿:;\"“«-—":
            continue
        hits.append(word)
    return hits


def language_issues(text: str, device: str = "desktop", glossary: dict | None = None,
                    voseo_only: bool = False) -> list[tuple[str, str]]:
    """(rule, message) for L1-L4 problems in one piece of text."""
    if not text:
        return []
    issues = [("L1", f"voseo «{w}» → usa tú («{voseo_hint(w)}»)") for w in voseo_hits(text)]
    if voseo_only:
        return issues
    if device == "mobile":
        issues += [("L2", f"«{m.group(0)}» en celular → usa «tocar»") for m in CLICK.finditer(text)]
    else:
        issues += [("L2", f"«{m.group(0)}» en escritorio → usa «hacer clic»") for m in TOUCH.finditer(text)]
    unquoted = strip_quotes(text)
    for term, synonyms in (glossary or {}).items():
        for syn in synonyms or []:
            pattern = re.compile(rf"\b{re.escape(str(syn))}(?:s|es)?\b", re.I)
            for m in pattern.finditer(unquoted):
                issues.append(("L3", f"«{m.group(0)}» → el glosario dice «{term}»"))
    for pattern, name, fix in IDIOMS:
        for m in pattern.finditer(unquoted):
            issues.append(("L4", f"modismo «{m.group(0)}» → usa «{fix}»"))
    return issues


def wrap(text: str, product: str | None, width: int = CAPTION_CHARS) -> list[str]:
    """Lines of a title/caption wrapped at width, never splitting the product name (T3)."""
    nbsp = "\u00a0"
    if product:
        text = text.replace(product, product.replace(" ", nbsp))
    return [line.replace(nbsp, " ") for line in textwrap.wrap(text, width, break_long_words=False)]


def video_steps(video: dict, steps: list[dict]) -> list[dict]:
    wanted = video.get("steps", "all")
    if wanted in (None, "all"):
        return list(steps)
    by_id = {s.get("id"): s for s in steps}
    return [by_id[i] for i in wanted if i in by_id]


def action_kind(action) -> tuple[str, object]:
    if isinstance(action, dict) and len(action) == 1:
        return next(iter(action.items()))
    return ("?", action)


def form_prefix(selector: str) -> str:
    token = re.split(r"[\s>]+", str(selector).strip())[0]
    return re.split(r"[-_]", token)[0] if re.search(r"[-_]", token) else token


def fill_prefix(step: dict) -> str | None:
    """Form prefix when every action of the step fills a field (type/select) of one form."""
    prefixes = set()
    for action in step.get("actions") or []:
        kind, value = action_kind(action)
        if kind in QUIET:
            continue
        if kind not in ("type", "select") or not isinstance(value, dict):
            return None
        prefixes.add(form_prefix(value.get("into") or value.get("in") or ""))
    return prefixes.pop() if len(prefixes) == 1 else None


def is_login(step: dict) -> bool:
    kinds, password = [], False
    for action in step.get("actions") or []:
        kind, value = action_kind(action)
        if kind in QUIET or kind == "goto":
            continue
        kinds.append(kind)
        if kind == "type" and isinstance(value, dict):
            text = str(value.get("text", ""))
            if PASSWORD.search(str(value.get("into", ""))) or (text.startswith("env:") and PASSWORD.search(text)):
                password = True
    return password and set(kinds) <= {"type", "click", "press"}


def is_interaction(step: dict) -> bool:
    return any(action_kind(a)[0] in INTERACTIONS for a in step.get("actions") or [])


def block_text(block) -> tuple[str, str]:
    if isinstance(block, dict):
        return str(block.get("narration") or ""), str(block.get("text") or "")
    if isinstance(block, str):
        return block, ""
    return "", ""


def lint_data(data: dict) -> tuple[list[str], list[str]]:
    """(errors, warnings) for a parsed tutorial.yaml v2."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(data, dict):
        return ["[E2] tutorial.yaml: tiene que ser un mapa"], []
    title = str(data.get("title") or "")
    product = data.get("product")
    device = str(data.get("device") or "desktop")
    glossary = data.get("glossary") or {}
    steps = data.get("steps") or []
    videos = data.get("videos") or []

    def lang(where: str, text: str, voseo_only: bool = False) -> None:
        for rule, msg in language_issues(text, device, glossary, voseo_only):
            errors.append(f"[{rule}] {where}: {msg}")

    for key in ("title", "steps", "videos"):
        if not data.get(key):
            errors.append(f"[S3] tutorial.yaml: falta la clave '{key}'")
    for old in ("intro", "outro"):
        if old in data:
            errors.append(f"[E1] tutorial.yaml: '{old}' ya no existe; usa videos[].opening/closing")
    if device not in ("desktop", "mobile"):
        errors.append(f"[L2] device: '{device}' (desktop | mobile)")

    lang("title", title)
    if len(wrap(title, product)) > 2:
        warnings.append(f"[T3] title: ocupa más de 2 líneas de {CAPTION_CHARS} caracteres; acórtalo")

    ids = [s.get("id") for s in steps]
    if None in ids or len(set(ids)) != len(ids):
        errors.append("[E2] steps: cada paso necesita un 'id' único")
    for step in steps:
        sid = step.get("id")
        lang(f"steps.{sid}.narration", str(step.get("narration") or ""))
        lang(f"steps.{sid}.title", str(step.get("title") or ""))
        for action in step.get("actions") or []:
            kind, value = action_kind(action)
            if kind == "type" and isinstance(value, dict):
                text = str(value.get("text") or "")
                if not text.startswith("env:"):
                    lang(f"steps.{sid}.type", text, voseo_only=True)

    for vi, video in enumerate(videos):
        vid = video.get("id", vi)
        where = f"videos.{vid}"
        vtype, fmt = video.get("type"), video.get("format")
        if vtype not in TYPES:
            errors.append(f"[S3] {where}.type: '{vtype}' ({' | '.join(TYPES)})")
        if fmt not in FORMATS:
            errors.append(f"[S3] {where}.format: '{fmt}' ({' | '.join(FORMATS)})")

        wanted = video.get("steps", "all")
        if wanted not in (None, "all"):
            unknown = [i for i in wanted if i not in ids]
            if unknown:
                errors.append(f"[E2] {where}.steps: pasos que no existen: {', '.join(map(str, unknown))}")
            known = [ids.index(i) for i in wanted if i in ids]
            if known != sorted(known) or len(set(known)) != len(known):
                errors.append(f"[E2] {where}.steps: tiene que respetar el orden de steps sin repetir")
        chosen = video_steps(video, steps)
        overrides = video.get("narration") or {}
        for sid, text in overrides.items():
            if sid not in [s.get("id") for s in chosen]:
                warnings.append(f"[E2] {where}.narration.{sid}: ese paso no está en el video")
            lang(f"{where}.narration.{sid}", str(text or ""))

        # E1: opening and closing.
        blocks = {}
        for name in ("opening", "requirements", "closing"):
            narration, text = block_text(video.get(name))
            blocks[name] = (narration, text)
            lang(f"{where}.{name}.narration", narration)
            lang(f"{where}.{name}.text", text)
        for name in ("opening", "closing"):
            narration, text = blocks[name]
            both = f"{narration} {text}".strip()
            if not both:
                errors.append(f"[E1] {where}.{name}: obligatorio (narración y texto)")
                continue
            if all(not part or norm(part) == norm(title) or LISTO.match(part) for part in (narration, text)):
                errors.append(f"[E1] {where}.{name}: no puede ser solo el título ni «¡Listo!»")
            elif re.match(r"^\W*listo\b", narration, re.I):
                warnings.append(f"[E1] {where}.{name}: evita «¡Listo!»; di el siguiente paso")
        open_all = " ".join(blocks["opening"]).strip()
        close_all = " ".join(blocks["closing"]).strip()
        if open_all and close_all:
            if vtype == "TUT":
                if not LEARN.search(open_all):
                    errors.append(f"[TUT1] {where}.opening: tiene que decir el objetivo («En este video aprendes a…»)")
                if not NEXT.search(close_all):
                    errors.append(f"[TUT1] {where}.closing: tiene que anunciar el siguiente video")
            elif vtype == "RED":
                if not PROBLEM.search(open_all):
                    errors.append(f"[RED1] {where}.opening: el gancho tiene que ser una pregunta o un problema")
                if not RED_CTA.search(close_all):
                    errors.append(f"[RED1] {where}.closing: falta el llamado a la acción («Mira el tutorial completo»)")
            elif vtype == "PRO":
                if not PROBLEM.search(open_all):
                    warnings.append(f"[PRO1] {where}.opening: abre con el problema")
                if not PRO_CTA.search(close_all):
                    errors.append(f"[PRO6] {where}.closing: falta un llamado a la acción concreto (prueba gratis, contacto o enlace)")
            elif vtype == "NOV":
                if not NEWS.search(open_all):
                    warnings.append(f"[NOV1] {where}.opening: di qué cambió")
                if not NOV_CTA.search(close_all):
                    errors.append(f"[NOV5] {where}.closing: enlaza el tutorial completo")
        if blocks["requirements"][0] or blocks["requirements"][1]:
            if vtype != "TUT":
                warnings.append(f"[TUT1] {where}.requirements: solo para TUT")
            if seconds(blocks["requirements"][0]) > 5:
                warnings.append(f"[TUT1] {where}.requirements: ~{seconds(blocks['requirements'][0]):.1f} s (máximo 5 s)")

        # Estimated timing (A2, E1, RED1).
        open_s, close_s = seconds(blocks["opening"][0]), seconds(blocks["closing"][0])
        if vtype == "RED" and not HOOK_RANGE[0] <= open_s <= HOOK_RANGE[1]:
            warnings.append(f"[RED1] {where}.opening: gancho de ~{open_s:.1f} s (1–2 s)")
        elif open_s > OPENING_MAX:
            warnings.append(f"[E1] {where}.opening: ~{open_s:.1f} s de narración (máximo {OPENING_MAX:g} s)")
        if close_s > CLOSING_MAX:
            warnings.append(f"[A2] {where}.closing: ~{close_s:.1f} s de narración (tarjeta de cierre ≤ {CLOSING_MAX:g} s)")

        # E2: one action per step (warn on a form split into several steps).
        prev = None
        for step in chosen:
            prefix = fill_prefix(step)
            if prefix and prefix == prev:
                warnings.append(f"[E2] {where}: el paso '{step.get('id')}' sigue llenando el mismo formulario "
                                f"que el anterior; un paso = una acción con resultado visible")
            prev = prefix

        # Parte 3 per type.
        if vtype == "TUT" and fmt != "16:9":
            warnings.append(f"[TUT] {where}.format: el tutorial va en 16:9")
        if vtype == "RED":
            if fmt != "9:16":
                errors.append(f"[RED5] {where}.format: RED va en 9:16 (reencuadre real, no el horizontal)")
            if not 3 <= len(chosen) <= 4:
                warnings.append(f"[RED1] {where}.steps: {len(chosen)} pasos (3 o 4 acciones clave)")
        logins = [s.get("id") for s in chosen if is_login(s)]
        if logins and vtype == "RED":
            errors.append(f"[RED3] {where}.steps: omite el login ({', '.join(logins)}) (V5)")
        elif logins and vtype in ("PRO", "NOV"):
            warnings.append(f"[{vtype}] {where}.steps: sin login ({', '.join(logins)})")
        if vtype == "PRO":
            run = 0
            for step in chosen:
                run = run + 1 if is_interaction(step) else 0
                if run > 2:
                    warnings.append(f"[PRO3] {where}.steps: más de 2 interacciones seguidas (muestra resultados)")
                    break
        if vtype == "NOV" and len(chosen) > 3:
            warnings.append(f"[NOV3] {where}.steps: {len(chosen)} pasos; un solo cambio por video")

        estimate = max(open_s, 1.0 if vtype == "RED" else CARD_FLOOR) + max(close_s, CARD_FLOOR)
        estimate += seconds(blocks["requirements"][0])
        for step in chosen:
            estimate += max(seconds(overrides.get(step.get("id")) or step.get("narration")), STEP_FLOOR)
        if vtype in DURATION_RANGES:
            low, high = DURATION_RANGES[vtype]
            if not low <= estimate <= high:
                warnings.append(f"[{'RED2' if vtype == 'RED' else vtype}] {where}: duración estimada "
                                f"~{estimate:.0f} s ({low}–{high} s)")
        if vtype == "TUT" and estimate > TUT_CHAPTERS_AFTER and not any(s.get("chapter") for s in chosen):
            warnings.append(f"[E3] {where}: ~{estimate / 60:.1f} min sin capítulos (TUT3)")
    return errors, warnings


def lint(slug: str) -> list[str]:
    """Warnings for proyectos/<slug>/tutorial.yaml; raises PipelineError listing every error."""
    path = project_dir(slug) / "tutorial.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    errors, warnings = lint_data(data)
    for warning in warnings:
        print(f"[lint] AVISO {warning}")
    if errors:
        raise PipelineError(f"tutorial.yaml no cumple las reglas ({len(errors)} errores):\n"
                            + "\n".join(f"  {e}" for e in errors))
    print(f"[lint] {slug}: OK ({len(warnings)} avisos)")
    return warnings


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug")
    lint(ap.parse_args().slug)


if __name__ == "__main__":
    main_guard(main)
