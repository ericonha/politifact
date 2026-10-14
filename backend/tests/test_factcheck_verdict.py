"""Veredito (sem banco, sem rede; LLM falso)."""

from datetime import date

from app.factcheck.parse import parse
from app.factcheck.sources import EvidenceItem
from app.factcheck.sources.bcb import Point, compare, plan, to_evidence
from app.factcheck.verdict import decide

TODAY = date(2026, 10, 13)


def official(text: str, points: list[tuple[date, float]]):
    p = parse(text)
    pl = plan(p, TODAY)
    return p, to_evidence(p, pl, compare(p, pl, [Point(d, v) for d, v in points], TODAY))


def test_rules_true_false_imprecise() -> None:
    pts = [(date(2025, 12, 1), 4.26)]
    for claim, expected in [("A inflação de 2025 foi de 4,26%", "verdadeiro"),
                            ("A inflação de 2025 foi de 4,5%", "impreciso"),
                            ("A inflação de 2025 foi de 7%", "falso")]:
        p, ev = official(claim, pts)
        v = decide(claim, "numero", p, ev, [])
        assert v.assessment == expected, claim
        assert "4,26%" in v.explanation and "13522" in v.explanation
        assert v.method == "rules"


def test_rules_no_data_is_no_evidence() -> None:
    p, ev = official("A inflação de 2025 foi de 4%", [])
    v = decide("x", "numero", p, ev, [])
    assert v.assessment == "sem_evidencia"


def test_opinion_and_prediction_not_checkable() -> None:
    p = parse("O governo é um desastre")
    assert decide("x", "opiniao", p, None, []).assessment == "nao_checavel"
    assert decide("x", "previsao", p, None, []).assessment == "nao_checavel"


def test_press_alone_never_decides() -> None:
    v = decide("Fulano foi preso ontem", "fato", parse("Fulano foi preso ontem"), None, [], llm=None)
    assert v.assessment == "sem_evidencia" and "não é prova" in v.explanation


FC = EvidenceItem("factcheck", "fact_check", "https://ex.org/1", "Checagem",
                  "Agência Exemplo checou: “O desemprego dobrou em 2025”. Classificação da agência: Falso.",
                  "related", "third_party")


class LLM:
    model = "fake"

    def __init__(self, out):
        self.out = out

    def complete_json(self, system, user, schema):
        assert "<evidencias>" in user and "DADO" in system
        return self.out


def test_llm_with_published_factcheck() -> None:
    c = "O desemprego dobrou em 2025"
    v = decide(c, "fato", parse(c), None, [(7, FC)], LLM({
        "assessment": "falso", "same_claim_ids": [7],
        "explanation": "A Agência Exemplo checou a afirmação e a classificou como falsa."}))
    assert v.assessment == "falso" and v.method == "llm"


def test_llm_verdict_without_citation_is_rejected() -> None:
    c = "O desemprego dobrou em 2025"
    v = decide(c, "fato", parse(c), None, [(7, FC)], LLM({
        "assessment": "falso", "same_claim_ids": [99], "explanation": "Falso."}))
    assert v.assessment == "sem_evidencia"


def test_llm_explanation_with_invented_name_is_rejected() -> None:
    c = "O desemprego dobrou em 2025"
    v = decide(c, "fato", parse(c), None, [(7, FC)], LLM({
        "assessment": "falso", "same_claim_ids": [7],
        "explanation": "O IBGE e a Lupa mostraram que é falso."}))
    assert v.assessment == "sem_evidencia"
    assert any("validação" in x for x in v.limitations)
