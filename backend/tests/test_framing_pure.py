"""Testes da análise observável e da comparação de manchetes (sem banco, sem IA)."""

from app.framing.compare import compare
from app.framing.observable import analyze


def test_observable_basics() -> None:
    r = analyze("Lula critica Banco Central e diz que juros são “absurdo”", "Presidente fala em escândalo")
    assert r["lead_actor"] == "Lula"
    assert [a["name"] for a in r["headline_actors"]] == ["Lula", "Banco Central"]
    assert r["attribution_verbs"] == ["critica", "diz"]
    assert r["has_quote"] is True
    assert r["loaded_terms"] == ["absurdo"]
    assert r["loaded_terms_summary"] == ["escândalo"]
    assert r["is_question"] is False


def test_observable_neutral_headline() -> None:
    r = analyze("Copom mantém Selic em 15% ao ano", None)
    assert r["attribution_verbs"] == [] and r["loaded_terms"] == []
    assert r["has_number"] is True and r["has_quote"] is False
    assert r["lead_actor"] == "Copom"


def test_question_and_apostrophe_not_quote() -> None:
    r = analyze("O que muda com a nova regra do Pix?", None)
    assert r["is_question"] is True
    assert analyze("Brazil's election heats up", None)["has_quote"] is False


def test_compare_shows_who_each_outlet_highlights() -> None:
    items = [
        {"outlet": "A", "observable": analyze("Moraes manda prender aliado de Bolsonaro", None)},
        {"outlet": "B", "observable": analyze("Bolsonaro critica prisão de aliado: 'perseguição'", None)},
        {"outlet": "C", "observable": analyze("STF determina prisão de ex-assessor de Bolsonaro", None)},
    ]
    c = compare(items)
    bolso = next(a for a in c["actors"] if a["key"] == "bolsonaro")
    assert bolso["in_all"] is True
    assert {a["name"] for a in c["partial_actors"]} >= {"Moraes", "STF"}
    assert c["lead_actor_by_outlet"] == {"A": ["Moraes"], "B": ["Bolsonaro"], "C": ["STF"]}
    assert c["different_leads"] is True
    assert c["attribution_outlets"] == ["B"]
    assert c["loaded_terms_by_outlet"] == {"B": ["perseguição"]}


def test_compare_single_outlet_has_no_partial_actors() -> None:
    c = compare([{"outlet": "A", "observable": analyze("Lula viaja à China", None)}])
    assert c["partial_actors"] == []


def test_country_name_is_not_an_actor() -> None:
    r = analyze("Brazil police arrest former Bolsonaro aide", None)
    assert r["lead_actor"] == "Bolsonaro"
