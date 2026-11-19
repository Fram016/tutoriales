"""Stage: lint. Checks tutorial.yaml v2 against reglas/reglas-video.md BEFORE anything is generated.

Usage: python tools/lint.py <slug>

Errors (exit 1, PipelineError) and warnings, each tagged with the rule ID it enforces:
  L1 voseo, L2 device verbs, L3 glossary synonyms, L4 regional idioms (narration, card texts,
  step titles; L1 also typed demo data), E1 opening/closing, E2 step lists and videos[].omit
  selectors, T3 title length, N2 opening text vs title (≥ 60 % shared words), N4 story of the
  opening carried by the steps (warning), N8 RED/PRO closing names a destination, and the
  per-type rules of Parte 3 (TUT/RED/PRO/NOV: format, login, step count, estimated duration).
  Round four (Parte 6): N15 a step is a user action (narration of what happens warns), N16 parts
  (two flows without parts warn; declared parts cover every step, contiguous), N19 one sentence
  = ≤ 2 caption lines and one instruction, N25 every highlighted table censored by column, N27
  closing optional in TUT, requirements say what you need («Necesitas…»).
  Round five (Parte 7): P1 the estimated length over videos[].max_seconds is an error, P2 videos[].pace is
  normal or fast; under fast the opening warns over 2 s and the requirements over 2.5 s. P4 under fast the voice
  tempo is at most x1.05 (error).
Voice estimate: 1.9 words/s + 0.5 s per clip (RED hook length: 2.6 words/s, no fixed part), divided by the
video's voice tempo (P2: 1.12 under pace fast, common.video_tempo). P1 is an error, so its budget is a lower
bound: BUDGET_WPS (the fastest trimmed read measured), no fixed part, the same tempo and floors.
P4: a step lasts at least its lead plus the reading time of its caption blocks (compose.caption_blocks,
common.reading_seconds), and every part adds its PART_SECONDS separator.
"""
from __future__ import annotations

import argparse
import colorsys
import re
import sys
import textwrap
import unicodedata

import yaml

from common import (FAST_TEMPO_MAX, PACES, PART_SECONDS, TEMPO_RANGE, PipelineError, main_guard, project_dir,
                    reading_seconds, video_tempo)
from compose import FORMATS as CAPTION_FORMATS, caption_blocks
from edit import FAST_PACE, LEAD

TYPES = ("TUT", "RED", "PRO", "NOV")
FORMATS = ("16:9", "9:16")
WORDS_PER_SECOND, CLIP_SECONDS = 1.9, 0.5
HOOK_WORDS_PER_SECOND = 2.6
# P1: trimmed Gemini clips of perseo-xml-v2 read 2.0-3.1 words/s ("En el SRI, abre el menú.": 6 words, 2.15 s), where
# the estimate above says 3.66 s; the max_seconds error only fires when even the fastest read does not fit.
BUDGET_WPS = 3.0
CAPTION_CHARS = 42
# Estimated duration ranges per type (seconds). Post-render errors are qa.py's job.
DURATION_RANGES = {"RED": (15, 35), "PRO": (20, 60), "NOV": (15, 30)}
TUT_CHAPTERS_AFTER = 300
# Minimum on-screen time of each block when it has little or no narration (cards, actions).
STEP_FLOOR, CARD_FLOOR = 1.5, 1.5
OPENING_MAX, CLOSING_MAX, HOOK_RANGE = 3.0, 2.5, (1.0, 2.0)
FAST_OPENING_MAX, FAST_REQUIREMENTS_MAX = 2.0, 2.5   # P2

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
# N8: where to see or do the call to action.
DESTINATION = re.compile(r"\b(?:enlace|perfil|canal|youtube|web|sitio|link|descripci[oó]n|bio)\b|www\.|https?://|"
                         r"\b[\w-]+\.(?:com|ec|net|org|io|app|co)\b", re.I)
# N2/N4: words that carry no idea of their own.
STOPWORDS = set("""
el la los las lo un una unos unas al del a ante bajo con contra de desde durante en entre hacia hasta
mediante para por segun sin sobre tras y e ni o u que pero mas sino porque pues si aunque como cuando
mientras tu tus su sus mi mis te se me este esta estos estas ese esa nuestro nuestra
""".split())
SIMILAR = 0.60
# N4: a noun right after one of these is a scenario candidate, unless it is generic.
DETERMINERS = set("un una unos unas el la los las tu tus su sus mi mis este esta ese esa del al".split())
GENERIC = set("""
video tutorial paso pasos minuto minutos segundo segundos forma manera vez dia dato datos sistema lista
boton formulario pantalla primer primera primero nuevo nueva nuevos nuevas mismo misma otro otra cada
solo sola menu campo campos
""".split())
LISTO = re.compile(r"^\W*(?:listo|eso es todo|fin|gracias|terminamos)\W*$", re.I)

PASSWORD = re.compile(r"pass|contrase|clave", re.I)
INTERACTIONS = {"click", "type", "select", "press", "scroll", "goto"}
QUIET = {"wait", "pause", "hover", "focus"}

# Round four (Parte 6).
# N15: what the user does (pointer, typing, choosing, opening a surface); waits, focus, results are not.
USER_ACTIONS = {"click", "type", "select", "press", "scroll", "hover", "open"}
HAPPENS = re.compile(r"^\W*(?:se abre|aparece)\b|\bya viene\b", re.I)
# N19: imperatives that ask for one action; they count at a sentence start or after a comma or connector
# («Abre Perseo XML y haz clic…» = 2), never as a 3rd person («el resumen muestra», «se abre»).
IMPERATIVES = set("""
haz abre elige escoge escribe selecciona pulsa presiona toca completa ingresa entra guarda busca llena
agrega añade pega copia marca vuelve cierra cambia consulta descarga revisa activa confirma acepta usa
""".split())
CONNECTORS = {"y", "e", "o", "luego", "después", "ahora", "primero", "entonces", "también", "finalmente"}
SENTENCE = re.compile(r"[^.!?…]+[.!?…]*")
# Requirements say what is needed (Parte 6: «Necesitas la extensión Perseo XML instalada…»).
NEED = re.compile(r"\bnecesitas\b|\bnecesita\b|\bdebes\b|\btienes que\b|\brequieres\b|\bhace falta\b|"
                  r"\bten\b|\bteniendo\b", re.I)
# N25: tables shown with a highlight, and the column censor selectors.
TABLE = re.compile(r"\btable\b|\btbody\b|tabla|_data\b", re.I)
CELL = re.compile(r"\btd\b|\bth\b|nth-child|nth-of-type", re.I)


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return " ".join(WORD.findall("".join(c for c in text if not unicodedata.combining(c))))


def strip_quotes(text: str) -> str:
    return QUOTED.sub(" ", text)


def words(text: str | None) -> int:
    return len(WORD.findall(text or ""))


def seconds(text: str | None) -> float:
    """Realistic voice estimate of one clip (TTS pace plus its fixed lead/tail)."""
    n = words(text)
    return n / WORDS_PER_SECOND + CLIP_SECONDS if n else 0.0


def hook_seconds(text: str | None) -> float:
    return words(text) / HOOK_WORDS_PER_SECOND


def stems(text: str | None, drop: set[str] = frozenset()) -> set[str]:
    """Content words cut to 5 letters (guarda ~ guardar, contacto ~ contactos)."""
    return {w[:5] for w in norm(text or "").split() if w not in STOPWORDS and w not in drop and len(w) > 2}


def similarity(a: str | None, b: str | None, drop: set[str] = frozenset()) -> float:
    """N2: share of the shorter text's content words that the other one repeats."""
    sa, sb = stems(a, drop), stems(b, drop)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / min(len(sa), len(sb))


def scenario_nouns(text: str) -> list[str]:
    """N4: nouns introduced by a determiner («una feria»), the story the opening promises."""
    tokens = norm(text).split()
    return [w for prev, w in zip(tokens, tokens[1:]) if prev in DETERMINERS and len(w) >= 4 and w not in GENERIC]


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


def hue(color) -> float | None:
    """Hue in degrees of a #rrggbb color, None for grays or invalid values."""
    m = re.fullmatch(r"#([0-9a-fA-F]{6})", str(color or "").strip())
    if not m:
        return None
    r, g, b = (int(m.group(1)[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, _, s = colorsys.rgb_to_hls(r, g, b)
    return h * 360 if s >= 0.15 and max(r, g, b) - min(r, g, b) >= 0.04 else None


def action_selectors(step: dict) -> set[str]:
    found = set()
    for action in step.get("actions") or []:
        kind, value = action_kind(action)
        if isinstance(value, dict):
            value = value.get("into") or value.get("in")
        if kind not in ("goto", "pause", "scroll", "press") and isinstance(value, str):
            found.add(value)
    return found


def step_story(step: dict, narration: str | None) -> str:
    """Narration plus the demo data typed or chosen in the step (N4)."""
    parts = [narration or ""]
    for action in step.get("actions") or []:
        kind, value = action_kind(action)
        if kind == "type" and isinstance(value, dict) and not str(value.get("text", "")).startswith("env:"):
            parts.append(str(value.get("text") or ""))
        elif kind == "select" and isinstance(value, dict):
            parts.append(str(value.get("option") or ""))
    return " ".join(parts)


def is_interaction(step: dict) -> bool:
    return any(action_kind(a)[0] in INTERACTIONS for a in step.get("actions") or [])


def user_actions(step: dict) -> list[str]:
    return [kind for kind, _ in map(action_kind, step.get("actions") or []) if kind in USER_ACTIONS]


def sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE.findall(text or "") if WORD.search(s)]


def instructions(sentence: str) -> list[str]:
    """N19: imperative verbs of one sentence that each ask for an action."""
    found, prev = [], None
    for m in re.finditer(r"[^\W\d_]+|,", sentence):
        token = m.group(0).lower()
        if token == ",":
            prev = ","
            continue
        if token in IMPERATIVES and (prev is None or prev == "," or prev in CONNECTORS):
            found.append(token)
        prev = token
    return found


def table_key(selector: str) -> str | None:
    """N25: the id (or class) that names a table selector, None for a bare table/tbody."""
    m = re.search(r"\[id=[\"']([^\"']+)[\"']\]|#([\w:-]+)|\.([\w-]+)", str(selector))
    return next((g for g in m.groups() if g), None) if m else None


def action_target(value) -> str:
    if isinstance(value, dict):
        value = value.get("sel") or value.get("in") or value.get("into")
    return str(value or "")


def repeated_flow(steps: list[dict]) -> tuple[list, list] | None:
    """N16: two windows of ≥ 2 steps with the same kinds of user actions (and not all the same), or the
    same surface button clicked in two steps: (first ids, second ids)."""
    signs = [tuple(user_actions(s)) for s in steps]
    ids = [s.get("id") for s in steps]
    for size in range(len(steps) // 2, 1, -1):
        for i in range(len(steps) - size + 1):
            window = signs[i:i + size]
            if len(set(window)) < 2 or not all(window):
                continue
            for j in range(i + size, len(steps) - size + 1):
                if signs[j:j + size] == window:
                    return ids[i:i + size], ids[j:j + size]
    seen = {}
    for step in steps:
        for action in step.get("actions") or []:
            kind, value = action_kind(action)
            if kind == "click" and isinstance(value, dict) and value.get("in"):
                key = (value["in"], value.get("sel"))
                if key in seen and seen[key] != step.get("id"):
                    return [seen[key]], [step.get("id")]
                seen.setdefault(key, step.get("id"))
    return None


def lint_round_four(data: dict, steps: list[dict]) -> tuple[list[str], list[str]]:
    """N15, N16, N19 (step narration) and N25 for the whole tutorial.yaml."""
    errors: list[str] = []
    warnings: list[str] = []
    parts = data.get("parts")
    numbers = []
    if parts is not None:
        if not isinstance(parts, list) or not all(isinstance(p, dict) and isinstance(p.get("n"), int) and
                                                  str(p.get("title") or "").strip() for p in parts):
            errors.append("[N16] parts: tiene que ser una lista [{n: número, title: título}]")
        else:
            numbers = [p["n"] for p in parts]
    per_part: dict = {}
    for step in steps:
        per_part.setdefault(step.get("part"), []).append(step.get("id"))

    for step in steps:
        sid = step.get("id")
        alone = step.get("part") is not None and len(per_part.get(step.get("part"), [])) == 1
        if not user_actions(step) and not alone:
            errors.append(f"[N15] steps.{sid}: no tiene una acción del usuario (clic, escribir, elegir, abrir); "
                          "lo que pasa va en la narración del paso anterior o siguiente")
        narration = str(step.get("narration") or "")
        if HAPPENS.search(narration):
            warnings.append(f"[N15] steps.{sid}.narration: describe lo que pasa («{narration[:40]}»); "
                            "un paso empieza por lo que hace el usuario")

    # N16: parts.
    if parts is None:
        flow = repeated_flow(steps)
        if flow:
            warnings.append(f"[N16] steps: dos flujos casi iguales ({', '.join(map(str, flow[0]))} y "
                            f"{', '.join(map(str, flow[1]))}); divídelos en partes (parts + part en cada paso)")
    elif numbers:
        missing = [str(s.get("id")) for s in steps if s.get("part") is None]
        if missing:
            errors.append(f"[N16] steps: pasos sin 'part' ({', '.join(missing)}); con parts, cada paso tiene su parte")
        unknown = sorted({str(s["part"]) for s in steps if s.get("part") is not None and s["part"] not in numbers})
        if unknown:
            errors.append(f"[N16] steps: partes que no están en parts: {', '.join(unknown)}")
        order = [s.get("part") for s in steps if s.get("part") is not None]
        runs = [p for i, p in enumerate(order) if i == 0 or order[i - 1] != p]
        if len(runs) != len(set(runs)):
            errors.append("[N16] steps: los pasos de cada parte tienen que ir seguidos (una parte no se retoma)")

    # N25: every table shown is censored by column, the same in all of them.
    censor = data.get("censor")
    if isinstance(censor, dict):
        cells = [str(s) for s in censor.get("selectors") or [] if CELL.search(str(s))]
        for step in steps:
            for action in step.get("actions") or []:
                kind, value = action_kind(action)
                target = action_target(value)
                if kind != "highlight" or not TABLE.search(target):
                    continue
                key = table_key(target)
                if not any(key is None or key in cell for cell in cells):
                    warnings.append(f"[N25] steps.{step.get('id')}: la tabla {target} se muestra sin columnas "
                                    "censuradas (censor.selectors con td:nth-child); difumina igual en todas")
    return errors, warnings


def narration_issues(where: str, text: str) -> list[str]:
    """N19: each sentence fits one caption block (≤ 2 lines of 42) and asks for one action."""
    errors = []
    for sentence in sentences(text):
        if len(sentence) > 2 * CAPTION_CHARS or len(wrap(sentence, None)) > 2:
            errors.append(f"[N19] {where}: «{sentence}» no entra en un subtítulo (≤ 2 líneas de {CAPTION_CHARS}); "
                          "escríbela más corta")
        verbs = instructions(sentence)
        if len(verbs) > 1:
            errors.append(f"[N19] {where}: «{sentence}» pide {len(verbs)} acciones ({', '.join(verbs)}); "
                          "una oración = una instrucción")
    return errors


def block_text(block) -> tuple[str, str]:
    if isinstance(block, dict):
        return str(block.get("narration") or ""), str(block.get("text") or "")
    if isinstance(block, str):
        return block, ""
    return "", ""


def estimate(data: dict, video: dict, budget: bool = False) -> float:
    """Estimated length of a video in seconds: its voice clips at the video's tempo (P2) with the minimum time of
    cards and steps (the actions of a step may take longer than its voice). `budget` (P1): the lower bound, every
    clip at BUDGET_WPS."""
    vtype = video.get("type")
    tempo = video_tempo(video)
    voice = (lambda text: words(text) / BUDGET_WPS) if budget else seconds   # noqa: E731
    hook = (lambda text: words(text) / BUDGET_WPS) if budget else hook_seconds   # noqa: E731
    overrides = video.get("narration") or {}
    blocks = {name: block_text(video.get(name)) for name in ("opening", "requirements", "closing")}
    if vtype == "RED":
        total = max(hook(blocks["opening"][0]) / tempo, 1.0)
    else:
        total = max(voice(blocks["opening"][0]) / tempo, CARD_FLOOR)
    if " ".join(blocks["closing"]).strip():
        total += max(voice(blocks["closing"][0]) / tempo, CARD_FLOOR)
    total += voice(blocks["requirements"][0]) / tempo
    # P4: the captions are read from the voice start (edit's lead) and every part opens with its separator.
    lead = FAST_PACE["lead"] if video.get("pace") == "fast" else LEAD
    chars = CAPTION_FORMATS.get(video.get("format") or "16:9", CAPTION_FORMATS["16:9"])["chars"]
    chosen = video_steps(video, data.get("steps") or [])
    for step in chosen:
        text = overrides.get(step.get("id")) or step.get("narration")
        read = sum(reading_seconds(" ".join(lines)) for _, lines in caption_blocks(str(text or ""), data.get("product"),
                                                                                    chars))
        total += max(voice(text) / tempo, STEP_FLOOR, lead + read if read else 0.0)
    if data.get("parts"):
        total += PART_SECONDS * len({s.get("part") for s in chosen if s.get("part") is not None})
    return total


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
    # N5: the accent comes from the app (default = primary), never an invented hue.
    brand = data.get("brand") or {}
    h_primary, h_accent = hue(brand.get("primary")), hue(brand.get("accent"))
    if h_primary is not None and h_accent is not None:
        diff = abs(h_primary - h_accent) % 360
        if min(diff, 360 - diff) > 15:
            warnings.append(f"[N5] brand.accent: {brand['accent']} no es del tono de primary {brand['primary']}; "
                            "usa un color de la app (por defecto, primary)")
    if len(wrap(title, product)) > 2:
        warnings.append(f"[T3] title: ocupa más de 2 líneas de {CAPTION_CHARS} caracteres; acórtalo")

    ids = [s.get("id") for s in steps]
    if None in ids or len(set(ids)) != len(ids):
        errors.append("[E2] steps: cada paso necesita un 'id' único")
    more_errors, more_warnings = lint_round_four(data, steps)
    errors += more_errors
    warnings += more_warnings
    for step in steps:
        sid = step.get("id")
        lang(f"steps.{sid}.narration", str(step.get("narration") or ""))
        errors += narration_issues(f"steps.{sid}.narration", str(step.get("narration") or ""))
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
        pace = video.get("pace", "normal")
        if pace not in PACES:
            errors.append(f"[P2] {where}.pace: '{pace}' ({' | '.join(PACES)})")
        fast = pace == "fast"
        cap = video.get("max_seconds")
        if cap is not None and (isinstance(cap, bool) or not isinstance(cap, (int, float)) or cap <= 0):
            errors.append(f"[P1] {where}.max_seconds: tiene que ser un número de segundos mayor que 0")
            cap = None
        tempo = video.get("tempo")
        if tempo is not None and (isinstance(tempo, bool) or not isinstance(tempo, (int, float))
                                  or not TEMPO_RANGE[0] <= tempo <= TEMPO_RANGE[1]):
            errors.append(f"[P2] {where}.tempo: tiene que ser un número entre {TEMPO_RANGE[0]:g} y {TEMPO_RANGE[1]:g}")
            tempo = None
        elif tempo is not None and fast and tempo > FAST_TEMPO_MAX:
            errors.append(f"[P4] {where}.tempo: con pace: fast es como máximo {FAST_TEMPO_MAX:g}")
            tempo = FAST_TEMPO_MAX
        tempo = video_tempo({**video, "tempo": tempo})

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
            errors += narration_issues(f"{where}.narration.{sid}", str(text or ""))

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
            if not both and name == "closing" and vtype == "TUT":
                continue   # N27: the TUT may end on its final result
            if not both:
                errors.append(f"[E1] {where}.{name}: obligatorio (narración y texto)")
                continue
            if all(not part or norm(part) == norm(title) or LISTO.match(part) for part in (narration, text)):
                errors.append(f"[E1] {where}.{name}: no puede ser solo el título ni «¡Listo!»")
            elif re.match(r"^\W*listo\b", narration, re.I):
                warnings.append(f"[E1] {where}.{name}: evita «¡Listo!»; di el siguiente paso")
        open_all = " ".join(blocks["opening"]).strip()
        close_all = " ".join(blocks["closing"]).strip()
        # N2: the opening card text and the title may not say the same thing twice.
        share = similarity(title, blocks["opening"][1])
        if share >= SIMILAR:
            errors.append(f"[N2] {where}.opening.text: repite el título ({share:.0%} de palabras en común); "
                          "di otra idea (el problema, el resultado) o déjalo vacío")
        # N8: RED and PRO closings say where to see or do it.
        if vtype in ("RED", "PRO") and close_all and not DESTINATION.search(close_all):
            errors.append(f"[N8] {where}.closing: di dónde verlo o hacerlo "
                          "(«en el enlace del perfil», «en nuestro canal de YouTube»)")
        if vtype == "TUT" and open_all and not close_all and not LEARN.search(open_all):
            errors.append(f"[TUT1] {where}.opening: tiene que decir el objetivo («En este video aprendes a…»)")
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
                    errors.append(f"[RED1] {where}.closing: falta el llamado a la acción "
                                  "(«Mira el tutorial completo en el enlace del perfil»)")
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
            req_s = seconds(blocks["requirements"][0]) / tempo
            if fast and req_s > FAST_REQUIREMENTS_MAX:
                warnings.append(f"[P2] {where}.requirements: ~{req_s:.1f} s (máximo {FAST_REQUIREMENTS_MAX:g} s con "
                                "pace: fast; o pásalo al texto de la apertura)")
            elif req_s > 5:
                warnings.append(f"[TUT1] {where}.requirements: ~{req_s:.1f} s (máximo 5 s)")
            if blocks["requirements"][1] and not NEED.search(blocks["requirements"][1]):
                warnings.append(f"[TUT1] {where}.requirements.text: di qué necesitas, con un verbo («Necesitas la "
                                "extensión Perseo XML instalada y tu sesión del SRI abierta»)")

        # N4: the story the opening promises («una feria») is carried by the steps' narration or data.
        if vtype in ("TUT", "RED"):
            known = stems(f"{title} {product or ''}") | stems(" ".join(
                f"{term} {' '.join(map(str, syns or []))}" for term, syns in glossary.items()))
            story = stems(" ".join(step_story(s, overrides.get(s.get("id")) or s.get("narration")) for s in chosen))
            missing = []
            for noun in scenario_nouns(open_all):
                if noun[:5] not in known | story and noun not in missing:
                    missing.append(noun)
            for noun in missing:
                warnings.append(f"[N4] {where}: la apertura plantea «{noun}» pero ni la narración ni los datos "
                                "de los pasos lo retoman; cumple la historia o cámbiala")

        # E2/RED3: videos[].omit cuts typing of fields that exist in this video's steps.
        omit = video.get("omit") or []
        if not isinstance(omit, list):
            errors.append(f"[E2] {where}.omit: tiene que ser una lista de selectores")
        else:
            available = set().union(*(action_selectors(s) for s in chosen))
            unknown = [str(sel) for sel in omit if sel not in available]
            if unknown:
                errors.append(f"[E2] {where}.omit: selectores que no están en las acciones de sus pasos: "
                              f"{', '.join(unknown)}")

        # Estimated timing (A2, E1, RED1, P1, P2).
        open_s, close_s = seconds(blocks["opening"][0]) / tempo, seconds(blocks["closing"][0]) / tempo
        hook_s = hook_seconds(blocks["opening"][0]) / tempo
        if vtype == "RED" and not HOOK_RANGE[0] <= hook_s <= HOOK_RANGE[1]:
            warnings.append(f"[RED1] {where}.opening: gancho de ~{hook_s:.1f} s (1–2 s)")
        elif vtype != "RED" and fast and open_s > FAST_OPENING_MAX:
            warnings.append(f"[P2] {where}.opening: ~{open_s:.1f} s de narración (máximo {FAST_OPENING_MAX:g} s con "
                            "pace: fast)")
        elif vtype != "RED" and open_s > OPENING_MAX:
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

        total = estimate(data, {**video, "tempo": tempo})
        least = estimate(data, {**video, "tempo": tempo}, budget=True)
        if cap is not None and least > cap:
            errors.append(f"[P1] {where}: duración estimada ~{least:.0f} s y el máximo es {cap:g} s (max_seconds); "
                          "acorta la narración o quita pasos")
        if vtype in DURATION_RANGES:
            low, high = DURATION_RANGES[vtype]
            if not low <= total <= high:
                warnings.append(f"[{'RED2' if vtype == 'RED' else vtype}] {where}: duración estimada "
                                f"~{total:.0f} s ({low}–{high} s)")
        if vtype == "TUT" and total > TUT_CHAPTERS_AFTER and not any(s.get("chapter") for s in chosen):
            warnings.append(f"[E3] {where}: ~{total / 60:.1f} min sin capítulos (TUT3)")
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
