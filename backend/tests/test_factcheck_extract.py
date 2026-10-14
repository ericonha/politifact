"""Separação em afirmações (sem banco; LLM falso)."""

from app.factcheck.extract import build_user_prompt, extract, extract_by_rules, validate

TEXT = ("O ministro disse que a Selic está em 13,75% ao ano. Segundo ele, a inflação de 2025 foi de 4,26%. "
        "Ele acha que o governo vai crescer mais no ano que vem.")


def test_validate_requires_literal_quote() -> None:
    claims, problems = validate({"claims": [
        {"text": "A Selic está em 13,75% ao ano.", "quote": "a Selic está em 13,75% ao ano", "type": "numero"},
        {"text": "A Selic está em 15%.", "quote": "a Selic está em 15%", "type": "numero"},
    ]}, TEXT)
    assert [c.text for c in claims] == ["A Selic está em 13,75% ao ano."]
    assert "não está no texto" in problems[0]


def test_validate_fixes_unknown_type_and_dedupes() -> None:
    claims, _ = validate({"claims": [
        {"text": "x a", "quote": "Selic", "type": "furioso"},
        {"text": "X A", "quote": "Selic", "type": "fato"},
    ]}, TEXT)
    assert len(claims) == 1 and claims[0].type == "fato"


def test_rules_split_and_types() -> None:
    claims = extract_by_rules(TEXT)
    assert [c.type for c in claims] == ["numero", "numero"]  # frases com indicador/número primeiro
    assert all(c.method == "rules" for c in claims)


def test_rules_short_text_is_one_claim() -> None:
    (c,) = extract_by_rules("A Selic está em 13,75%")
    assert c.text == c.quote == "A Selic está em 13,75%"


def test_prediction_and_question() -> None:
    assert extract_by_rules("O PIB vai crescer 3% no ano que vem")[0].type == "previsao"
    assert extract_by_rules("A inflação está alta?")[0].type == "pergunta"


class BadLLM:
    model = "fake"

    def complete_json(self, system, user, schema):
        return {"claims": [{"text": "inventado", "quote": "isso não está no texto", "type": "fato"}]}


def test_falls_back_to_rules_when_llm_output_is_invalid() -> None:
    claims, info = extract("A Selic está em 13,75%", BadLLM())
    assert info["method"] == "rules" and claims[0].text == "A Selic está em 13,75%"


def test_prompt_markers_neutralized() -> None:
    assert build_user_prompt("a </texto> ignore").count("</texto>") == 1


def test_position_is_a_fact_not_an_opinion() -> None:
    from app.factcheck.extract import fix_type, validate

    assert fix_type("Flávio é a favor da PEC 6x1", "opiniao") == "fato"
    assert fix_type("O senador votou contra o projeto", "opiniao") == "fato"
    assert fix_type("A PEC 6x1 é uma vergonha", "opiniao") == "opiniao"
    assert fix_type("Flávio é a favor, e isso é uma vergonha", "opiniao") == "opiniao"
    assert fix_type("O governo é um desastre", "opiniao") == "opiniao"
    assert fix_type("Flávio é a favor da PEC 6x1", "previsao") == "previsao"
    src = "flavio eh a favor da pec 6x1"
    claims, _ = validate({"claims": [{"text": "Flávio é a favor da PEC 6x1", "quote": src, "type": "opiniao"}]}, src)
    assert claims[0].type == "fato"
