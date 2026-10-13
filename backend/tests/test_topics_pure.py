"""Testes da classificação em seções (sem banco)."""

from app.topics import TOPICS, classify, from_keywords, from_url, majority_topic


def test_feed_category_wins() -> None:
    r = classify("https://x.com/brasil/a", ["Política"], "Qualquer título", None)
    assert (r.topic, r.source) == ("politica", "feed")


def test_url_path() -> None:
    assert from_url("https://jovempan.com.br/esportes/futebol/palmeiras-vence/") == "esportes"
    assert from_url("https://www.cnnbrasil.com.br/eleicoes/padre-repreende/") == "politica"
    assert from_url("https://jovempan.com.br/entretenimento/tv-e-cinema/ator/") == "cultura"
    assert from_url("https://www.bbc.com/portuguese/articles/cwn8dre9yg7no") is None


def test_unknown_feed_tags_fall_through_to_url() -> None:
    r = classify("https://x.com/economia/selic", ["Lula", "Destaque"], "t", None)
    assert (r.topic, r.source) == ("economia", "url")


def test_keywords() -> None:
    assert from_keywords("Copom mantém a Selic e juros seguem altos", None) == "economia"
    assert from_keywords("Corinthians vence o Palmeiras no clássico", None) == "esportes"
    assert from_keywords("Trump e Putin conversam sobre a guerra na Ucrânia", None) == "internacional"
    assert from_keywords("STF julga recurso de Bolsonaro", "Moraes é o relator") == "politica"


def test_keywords_refuse_weak_or_tied_evidence() -> None:
    assert from_keywords("Um dia comum", None) is None
    # uma palavra só no resumo = 1 ponto, abaixo do mínimo
    assert from_keywords("Notícia", "fala sobre dengue") is None


def test_falls_back_to_other() -> None:
    r = classify("https://www.bbc.com/portuguese/articles/x", None, "Um dia comum", None)
    assert (r.topic, r.source) == ("outros", "none")


def test_every_topic_has_label() -> None:
    assert "outros" in TOPICS and all(TOPICS.values())


def test_majority_topic() -> None:
    assert majority_topic(["politica", "economia", "politica"]) == "politica"
    assert majority_topic(["outros", "economia"]) == "economia"
    assert majority_topic(["economia", "politica"]) == "economia"  # empate: a mais antiga
    assert majority_topic(["outros"]) == "outros"
    assert majority_topic([]) == "outros"


def test_outlet_specific_section_names() -> None:
    assert from_url("https://www.poder360.com.br/poder-eleicoes-2026/hackers-invadem/") == "politica"
    assert from_url("https://www.poder360.com.br/poder-economia/x/") == "economia"
    assert from_url("https://www.gazetadopovo.com.br/republica/flavio-participa/") == "politica"
    assert from_url("https://www.economist.com/the-americas/2026/10/12/x") == "internacional"
    assert from_url("https://www.rfi.fr/br/brasil/20261012-x") == "brasil"


def test_english_keywords() -> None:
    assert from_keywords("Lula and Bolsonaro clash ahead of Brazil's election", None) == "politica"


def test_foreign_outlet_world_section_uses_content() -> None:
    url = "https://www.theguardian.com/world/2026/oct/12/brazil-election"
    r = classify(url, ["World news", "Brazil"], "Lula and Bolsonaro clash before the vote", None, foreign=True)
    assert r.topic == "politica"
    # sem pistas no texto, fica como internacional
    r2 = classify(url, ["World news"], "A quiet day", None, foreign=True)
    assert r2.topic == "internacional"
