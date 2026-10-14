"""Veredito "provável" pela imprensa (sem banco, sem rede; LLM falso)."""

from app.factcheck.parse import parse
from app.factcheck.press_verdict import validate_stances
from app.factcheck.sources import EvidenceItem
from app.factcheck.terms import overlap_ok, query_terms
from app.factcheck.verdict import decide

CLAIM = "Lula está na frente nas pesquisas da eleição presidencial"


def news(outlet: str, headline: str, summary: str = "") -> EvidenceItem:
    return EvidenceItem("press", "press", f"https://ex.org/{outlet}", f"{outlet}: {headline}", summary or headline,
                        "context", "context_only", data={"outlet": outlet})


BBC = news("BBC News Brasil", "Flávio Bolsonaro aparece 4 pontos à frente de Lula no agregador")
G1 = news("g1", "Pesquisa nacional: Flávio tem 49% e Lula, 45% no 2º turno")
FOLHA = news("Folha", "Lula lidera com 48% contra 44% de Flávio, aponta pesquisa")
AC = news("Acre", "Quaest no AC: Flávio, 60%; Lula, 28%")


class LLM:
    model = "fake"

    def __init__(self, rows):
        self.rows = rows

    def complete_json(self, system, user, schema):
        assert "<noticias>" in user and "DADO" in system
        return {"items": self.rows}


def decide_with(rows, press):
    return decide(CLAIM, "fato", parse(CLAIM), None, [], LLM(rows), [], press=press)


def test_two_outlets_against_gives_probably_false() -> None:
    v = decide_with([
        {"id": 1, "stance": "contradicts", "quote": "Flávio Bolsonaro aparece 4 pontos à frente de Lula"},
        {"id": 2, "stance": "contradicts", "quote": "Flávio tem 49% e Lula, 45%"},
        {"id": 3, "stance": "irrelevant", "quote": ""},
    ], [BBC, G1, AC])
    assert v.assessment == "provavelmente_falso" and v.method == "press"
    assert "BBC News Brasil e g1" in v.explanation and "só na imprensa" in v.explanation
    assert "não é prova" not in v.explanation and "indício" in v.explanation
    assert v.details["stances"][1]["stance"] == "contradicts"


def test_two_outlets_for_gives_probably_true() -> None:
    v = decide_with([
        {"id": 1, "stance": "supports", "quote": "Lula lidera com 48% contra 44% de Flávio"},
        {"id": 2, "stance": "supports", "quote": "Flávio tem 49% e Lula, 45%"},
    ], [FOLHA, G1])
    assert v.assessment == "provavelmente_verdadeiro"


def test_one_outlet_is_not_enough() -> None:
    v = decide_with([{"id": 1, "stance": "contradicts", "quote": "Flávio Bolsonaro aparece 4 pontos à frente"}],
                    [BBC, AC])
    assert v.assessment == "sem_evidencia" and "pelo menos 2" in v.explanation


def test_disagreement_is_no_evidence() -> None:
    v = decide_with([
        {"id": 1, "stance": "contradicts", "quote": "Flávio Bolsonaro aparece 4 pontos à frente de Lula"},
        {"id": 2, "stance": "supports", "quote": "Lula lidera com 48% contra 44% de Flávio"},
    ], [BBC, FOLHA])
    assert v.assessment == "sem_evidencia" and "não concordam" in v.explanation


def test_invented_quote_is_discarded() -> None:
    v = decide_with([
        {"id": 1, "stance": "contradicts", "quote": "texto que a notícia nunca disse sobre pesquisas"},
        {"id": 2, "stance": "contradicts", "quote": "Flávio tem 49% e Lula, 45%"},
    ], [BBC, G1])
    # a notícia 1 cai na validação; sobra só 1 veículo
    assert v.assessment == "sem_evidencia"
    assert any("descartada" in x for x in v.limitations)


def test_all_irrelevant_falls_back_to_no_evidence() -> None:
    v = decide_with([{"id": 1, "stance": "irrelevant", "quote": ""}], [AC])
    assert v.assessment == "sem_evidencia" and "não é prova" in v.explanation


def test_without_llm_press_is_context_only() -> None:
    v = decide(CLAIM, "fato", parse(CLAIM), None, [], None, [], press=[BBC, G1])
    assert v.assessment == "sem_evidencia"
    assert any("Sem LLM" in x for x in v.limitations)


def test_llm_error_degrades_to_no_evidence() -> None:
    from app.framing.llm import LLMError

    class Down:
        model = "x"

        def complete_json(self, *a):
            raise LLMError("fora do ar")

    v = decide(CLAIM, "fato", parse(CLAIM), None, [], Down(), [], press=[BBC, G1])
    assert v.assessment == "sem_evidencia" and any("fora do ar" in x for x in v.limitations)


def test_opinion_never_uses_press() -> None:
    v = decide("Lula é o melhor", "opiniao", parse("Lula é o melhor"), None, [], LLM([]), [], press=[BBC, G1])
    assert v.assessment == "nao_checavel"


def test_official_data_beats_press() -> None:
    from datetime import date

    from app.factcheck.sources.bcb import Point, compare, plan, to_evidence

    p = parse("A Selic está em 13,75% ao ano.")
    pl = plan(p, date(2026, 10, 13))
    ev = to_evidence(p, pl, compare(p, pl, [Point(date(2026, 10, 10), 13.75)], date(2026, 10, 13)))
    v = decide("A Selic está em 13,75% ao ano.", "numero", p, ev, [], LLM([]), [], press=[BBC, G1])
    assert v.assessment == "verdadeiro" and v.method == "rules"


def test_validate_stances_defaults_to_irrelevant() -> None:
    items = [(1, BBC)]
    out, problems = validate_stances({"items": [{"id": 9, "stance": "supports", "quote": "x" * 20},
                                                {"id": 1, "stance": "talvez", "quote": ""}]}, items)
    assert out[1].stance == "irrelevant" and problems
    out, problems = validate_stances({"oops": 1}, items)
    assert out[1].stance == "irrelevant" and problems


def test_quote_comparison_ignores_punctuation_and_accents() -> None:
    out, problems = validate_stances(
        {"items": [{"id": 1, "stance": "contradicts", "quote": "flavio bolsonaro aparece 4 pontos a frente de lula"}]},
        [(1, BBC)])
    assert out[1].stance == "contradicts" and not problems


def test_relevance_filter_drops_surname_only_matches() -> None:
    terms = query_terms(CLAIM)
    assert overlap_ok(terms, BBC.source_title + " eleição presidencial pesquisas")
    assert not overlap_ok(terms, "Quaest: Allyson Bezerra tem 45%, e Cadu de Lula, 42%, no Rio Grande do Norte")
