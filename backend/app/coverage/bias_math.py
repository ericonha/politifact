"""Medidas de viés de cobertura de um veículo (cálculos puros, sem banco).

Nenhuma dessas medidas é um rótulo político. São diferenças OBSERVÁVEIS entre um veículo e
os demais monitorados do mesmo grupo e idioma, sempre com o tamanho da amostra:

1. Omissões: histórias que vários veículos cobriram e este não.
2. Atraso: quanto tempo depois do primeiro veículo ele publicou a mesma história.
3. Vocabulário: palavras que ele usa mais (ou menos) que os outros na MESMA história.
4. Edições: manchetes alteradas depois de publicadas.

Limites que valem para todas: o sistema só vê o que aparece nos feeds RSS, no que foi coletado
(a cada 30 min) e agrupado em histórias. Ausência no feed não prova ausência na redação.
"""

import math
import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import datetime

from app.clustering.core import _STOPWORDS

# --- Omissões -------------------------------------------------------------------

MIN_OUTLETS_FOR_OMISSION = 4  # só compara histórias cobertas por pelo menos 4 veículos do grupo
MIN_STORIES = 10  # abaixo disso o veículo fica fora da média dos pares
MAX_BLIND_SPOTS = 8


def omission_stats(
    story_outlets: dict[int, set[int]],
    group: set[int],
    outlet_id: int,
    *,
    eligible_since: dict[int, datetime] | None = None,
    story_start: dict[int, datetime] | None = None,
    min_outlets: int = MIN_OUTLETS_FOR_OMISSION,
) -> dict:
    """Histórias que ≥ min_outlets veículos do grupo cobriram, e quantas este veículo cobriu.

    `eligible_since[outlet]`: data da matéria mais antiga que temos do veículo; histórias anteriores
    a isso não contam como omissão dele (o feed nem mostraria).
    """
    def counted(sid: int, oid: int) -> bool:
        if eligible_since is None or story_start is None:
            return True
        since, start = eligible_since.get(oid), story_start.get(sid)
        return since is None or start is None or start >= since

    def one(oid: int) -> tuple[list[int], list[int]]:
        covered, missed = [], []
        for sid, outs in story_outlets.items():
            in_group = outs & group
            if len(in_group) < min_outlets or not counted(sid, oid):
                continue
            (covered if oid in in_group else missed).append(sid)
        return covered, missed

    covered_ids, missed = one(outlet_id)
    covered = len(covered_ids)
    total = covered + len(missed)
    peer_rates = []
    for oid in group - {outlet_id}:
        c, m = one(oid)
        if len(c) + len(m) >= MIN_STORIES:
            peer_rates.append(len(m) / (len(c) + len(m)))
    missed.sort(key=lambda sid: -len(story_outlets[sid] & group))
    return {
        "covered_ids": covered_ids,
        "missed_ids": list(missed),
        "eligible_stories": total,
        "covered": covered,
        "missed": len(missed),
        "omission_rate": (len(missed) / total) if total else None,
        "average_rate": (sum(peer_rates) / len(peer_rates)) if peer_rates else None,
        "blind_spot_ids": missed[:MAX_BLIND_SPOTS],
        "min_outlets": min_outlets,
    }


# --- Atraso ---------------------------------------------------------------------

FIRST_TOLERANCE_MIN = 10  # até 10 min depois do primeiro conta como "junto com o primeiro"
MIN_DELAY_STORIES = 8


def _minutes(a: datetime, b: datetime) -> float:
    return (a - b).total_seconds() / 60


def delay_stats(first_times: dict[int, dict[int, datetime]], group: set[int], outlet_id: int) -> dict:
    """first_times[story][outlet] = hora da primeira publicação do veículo na história.

    Atraso = hora do veículo − hora do primeiro veículo do grupo (≥ 0). Só histórias com 2+ veículos.
    """
    def delays(oid: int) -> list[float]:
        out = []
        for times in first_times.values():
            t = {o: x for o, x in times.items() if o in group}
            if len(t) < 2 or oid not in t:
                continue
            out.append(max(0.0, _minutes(t[oid], min(t.values()))))
        return out

    mine = delays(outlet_id)
    peer_medians = []
    for oid in group - {outlet_id}:
        d = delays(oid)
        if len(d) >= MIN_DELAY_STORIES:
            peer_medians.append(statistics.median(d))
    return {
        "stories": len(mine),
        "median_minutes": statistics.median(mine) if mine else None,
        "first_share": (sum(1 for x in mine if x <= FIRST_TOLERANCE_MIN) / len(mine)) if mine else None,
        "average_median_minutes": (sum(peer_medians) / len(peer_medians)) if peer_medians else None,
        "enough": len(mine) >= MIN_DELAY_STORIES,
        "tolerance_minutes": FIRST_TOLERANCE_MIN,
    }


# --- Vocabulário ----------------------------------------------------------------

_EN_STOP = set(
    """the and for with that from this have has had will would says said say after over into about
    their there which been were was are not but they you your more than its his her him she
    new news live watch what when where who why how can could may amid also just out all""".split()
)
_STOP = _STOPWORDS | _EN_STOP
_WORD = re.compile(r"[a-z]{4,}")

MIN_DOCS = 25  # documentos mínimos de cada lado
MIN_TERM_DOCS = 3
Z_MIN = 1.96
TOP_TERMS = 10


def tokens(text: str) -> set[str]:
    """Palavras distintas (sem acento, ≥ 4 letras, sem palavras vazias). Presença, não repetição."""
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return {w for w in _WORD.findall(t) if w not in _STOP}


def log_odds_z(
    a: dict[str, float], b: dict[str, float], n_a: float, n_b: float, prior_docs: float = 10.0
) -> dict[str, float]:
    """Razão de chances log da PRESENÇA de cada palavra por documento, com prior informativo.

    a[w], b[w]: em quantos documentos (ponderados) a palavra aparece de cada lado; n_a, n_b: total de
    documentos de cada lado. Positivo = a palavra aparece em proporção maior dos documentos de `a`.
    O prior (taxa geral de presença) encolhe palavras raras, que de outro modo dominariam o ranking
    (ideia de "Fightin' Words", Monroe, Colaresi & Quinn, adaptada para presença por documento).
    """
    if n_a <= 0 or n_b <= 0:
        return {}
    out: dict[str, float] = {}
    for w in set(a) | set(b):
        ya, yb = a.get(w, 0.0), b.get(w, 0.0)
        p = (ya + yb) / (n_a + n_b)
        yes_a, no_a = ya + prior_docs * p + 0.5, (n_a - ya) + prior_docs * (1 - p) + 0.5
        yes_b, no_b = yb + prior_docs * p + 0.5, (n_b - yb) + prior_docs * (1 - p) + 0.5
        delta = math.log(yes_a / no_a) - math.log(yes_b / no_b)
        var = 1 / yes_a + 1 / no_a + 1 / yes_b + 1 / no_b
        out[w] = delta / math.sqrt(var)
    return out


def distinctive_terms(
    mine: Iterable[tuple[int, set[str]]], others: Iterable[tuple[int, set[str]]]
) -> dict:
    """mine/others: (id da história, palavras do artigo). Cada história pesa o mesmo dos dois lados.

    Dentro de cada história, os artigos de um lado pesam 1/(quantos): o "tamanho da amostra" de cada
    lado é o número de histórias, e histórias muito cobertas não definam sozinhas o vocabulário.
    """
    mine = list(mine)
    others = list(others)
    n_mine, n_others = len(mine), len(others)
    base = {"docs_outlet": n_mine, "docs_others": n_others, "min_docs": MIN_DOCS}
    if n_mine < MIN_DOCS or n_others < MIN_DOCS:
        return {**base, "enough": False, "uses_more": [], "uses_less": []}

    per_story_mine = Counter(s for s, _ in mine)
    per_story_others = Counter(s for s, _ in others)
    a: dict[str, float] = defaultdict(float)
    b: dict[str, float] = defaultdict(float)
    raw_a: Counter = Counter()
    for sid, words in mine:
        w = 1 / per_story_mine[sid]
        for t in words:
            a[t] += w
            raw_a[t] += 1
    for sid, words in others:
        w = 1 / per_story_others[sid]
        for t in words:
            b[t] += w
    z = log_odds_z(a, b, n_a=len(per_story_mine), n_b=len(per_story_others))

    n_stories_others = len(per_story_others)
    more = sorted((t for t in z if z[t] >= Z_MIN and raw_a.get(t, 0) >= MIN_TERM_DOCS), key=lambda t: -z[t])
    less = sorted((t for t in z if z[t] <= -Z_MIN and b.get(t, 0.0) >= MIN_TERM_DOCS / 2), key=lambda t: z[t])

    def fmt(t: str) -> dict:
        return {"term": t, "z": round(z[t], 2), "docs_outlet": raw_a.get(t, 0),
                "outlet_share": raw_a.get(t, 0) / n_mine,
                "others_share": (b.get(t, 0.0) / n_stories_others) if n_stories_others else 0.0}

    return {**base, "enough": True, "stories": len(per_story_mine),
            "uses_more": [fmt(t) for t in more[:TOP_TERMS]], "uses_less": [fmt(t) for t in less[:TOP_TERMS]]}


# --- Edições de manchete --------------------------------------------------------

_NUM = re.compile(r"\d+(?:[.,]\d+)?")
_NEGATION = {"nao", "nunca", "nem", "sem", "jamais", "nenhum", "nenhuma", "ninguem", "negou", "nega", "desmente"}
_DECLARED = re.compile(r"\b(corrig\w*|correcao|errata|retific\w*|atualiz\w*)\b")
SIMILARITY_ADJUST = 0.8


def _fold(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def _raw(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", _fold(text)))


def _words(text: str) -> set[str]:
    return _raw(text) - _STOPWORDS


def _same(a: str, b: str) -> bool:
    return re.sub(r"[^a-z0-9]+", " ", _fold(a)).strip() == re.sub(r"[^a-z0-9]+", " ", _fold(b)).strip()


def classify_change(old_headline: str, old_summary: str | None, new_headline: str, new_summary: str | None) -> dict:
    """Descreve a diferença entre duas versões de título+resumo. Só marcadores objetivos.

    kind:
      "resumo"          só o resumo mudou
      "ajuste"          manchete trocou poucas palavras (≥ 80% das palavras em comum)
      "reescrita"       manchete bem diferente
      "possivel_sentido" número ou negação mudou: vale ler as duas versões
    """
    headline_changed = not _same(old_headline, new_headline)
    summary_changed = not _same(old_summary or "", new_summary or "")
    wo, wn = _words(old_headline), _words(new_headline)
    sim = (len(wo & wn) / len(wo | wn)) if (wo | wn) else 1.0
    numbers = set(_NUM.findall(old_headline)) != set(_NUM.findall(new_headline))
    negation = (bool(_raw(old_headline) & _NEGATION) != bool(_raw(new_headline) & _NEGATION)) if headline_changed else False
    old_all, new_all = _fold(f"{old_headline} {old_summary or ''}"), _fold(f"{new_headline} {new_summary or ''}")
    declared = bool(_DECLARED.search(new_all)) and not _DECLARED.search(old_all)
    if not headline_changed:
        kind = "resumo"
    elif numbers or negation:
        kind = "possivel_sentido"
    elif sim >= SIMILARITY_ADJUST:
        kind = "ajuste"
    else:
        kind = "reescrita"
    return {"headline_changed": headline_changed, "summary_changed": summary_changed,
            "similarity": round(sim, 3), "numbers_changed": numbers and headline_changed,
            "negation_changed": negation, "declared": declared, "kind": kind}


def revision_stats(
    articles_by_outlet: dict[int, int], revisions_by_outlet: dict[int, list[dict]], outlet_id: int
) -> dict:
    """articles_by_outlet: nº de artigos elegíveis; revisions: uma lista de classificações por artigo
    alterado (a ÚLTIMA mudança de manchete de cada artigo)."""
    def rates(oid: int) -> dict:
        n = articles_by_outlet.get(oid, 0)
        revs = [r for r in revisions_by_outlet.get(oid, []) if r["headline_changed"]]
        k = len(revs)
        return {
            "articles": n,
            "edited": k,
            "edited_share": (k / n) if n else None,
            "meaning_flagged": sum(1 for r in revs if r["kind"] == "possivel_sentido"),
            "rewritten": sum(1 for r in revs if r["kind"] == "reescrita"),
            "declared": sum(1 for r in revs if r["declared"]),
        }

    mine = rates(outlet_id)
    peers = [rates(o) for o in articles_by_outlet if o != outlet_id and articles_by_outlet[o] >= MIN_STORIES * 2]
    peer_shares = [p["edited_share"] for p in peers if p["edited_share"] is not None]
    mine["average_edited_share"] = (sum(peer_shares) / len(peer_shares)) if peer_shares else None
    mine["declared_share"] = (mine["declared"] / mine["edited"]) if mine["edited"] else None
    return mine
