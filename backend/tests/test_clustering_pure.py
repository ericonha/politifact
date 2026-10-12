"""Testes do núcleo de agrupamento e das métricas (sem banco, sem rede)."""

from datetime import UTC, datetime, timedelta

from app.clustering.core import (
    DedupCandidate,
    Params,
    StoryState,
    cluster_offline,
    decide,
    entities,
    find_duplicate,
    headline_tokens,
    make_features,
    pair_score,
    tokens,
)
from app.clustering.metrics import evaluate

T0 = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
P = Params()


def f(i: int, headline: str, summary: str = "", hours: float = 0, outlet: int = 1, emb=None):
    return make_features(i, outlet, T0 + timedelta(hours=hours), headline, summary, emb)


def test_tokens_stem_and_drop_stopwords() -> None:
    t = tokens("Câmara aprova a reforma; aprovação segue para o Senado")
    assert "aprova" in t and "camara" in t and "senado" in t
    assert "para" not in t and "a" not in t


def test_entities_finds_names_and_acronyms() -> None:
    e = entities("Alexandre de Moraes manda PF investigar deputado do PL em São Paulo")
    assert "alexandre de moraes" in e
    assert "pf" in e and "pl" in e
    assert "sao paulo" in e


def test_same_story_scores_higher_than_unrelated() -> None:
    a = f(1, "STF julga marco temporal das terras indígenas", "Supremo retoma julgamento nesta quarta")
    b = f(2, "Supremo retoma julgamento do marco temporal", "STF analisa terras indígenas", outlet=2)
    c = f(3, "Corinthians vence o Palmeiras no Itaquerão", "Clássico termina 2 a 1", outlet=3)
    assert pair_score(a, b, P) > pair_score(a, c, P) + 0.3


def test_embeddings_dominate_when_present() -> None:
    a = f(1, "Texto qualquer", emb=(1.0, 0.0, 0.0))
    b = f(2, "Outro assunto", emb=(0.99, 0.05, 0.0))
    c = f(3, "Texto qualquer", emb=(0.0, 1.0, 0.0))
    assert pair_score(a, b, P) > pair_score(a, c, P)


def test_decide_respects_time_window() -> None:
    old = StoryState(7, [f(1, "STF julga marco temporal", hours=-100)])
    new = f(2, "STF julga marco temporal")
    assert decide(new, [old], P).kind == "new_story"


def test_decide_three_outcomes() -> None:
    story = StoryState(1, [f(1, "x", emb=(1.0, 0.0))])
    params = P.with_thresholds(0.6, 0.3)
    assert decide(f(2, "y", emb=(1.0, 0.0)), [story], params).kind == "assigned"
    # cos = 0.8 -> emb reescalado ~0.86 -> score ~0.56: entre os limiares
    assert decide(f(3, "y", emb=(0.8, 0.6)), [story], params).kind == "ambiguous"
    assert decide(f(4, "y", emb=(0.0, 1.0)), [story], params).kind == "new_story"


def test_cluster_offline_groups_related_articles() -> None:
    items = [
        f(1, "STF julga marco temporal das terras indígenas", "Supremo retoma julgamento"),
        f(2, "Corinthians vence o Palmeiras no clássico", "Jogo termina 2 a 1", hours=1),
        f(3, "Supremo retoma julgamento do marco temporal", "STF e terras indígenas", hours=2, outlet=2),
        f(4, "Palmeiras perde clássico para o Corinthians", "Corinthians vence por 2 a 1", hours=3, outlet=2),
    ]
    labels = cluster_offline(items, P.with_thresholds(0.45, 0.3))
    assert labels[1] == labels[3]
    assert labels[2] == labels[4]
    assert labels[1] != labels[2]


def test_find_duplicate_exact_and_near() -> None:
    def c(i, headline, outlet=1, h="x", hours=0):
        return DedupCandidate(i, outlet, T0 + timedelta(hours=hours), h, headline_tokens(headline))

    original = c(1, "Governo anuncia novo programa de habitação", h="aaa")
    syndicated = c(2, "Título diferente", outlet=2, h="aaa")
    assert find_duplicate(syndicated, [original]) == (1, "exact")

    edited = c(3, "Governo anuncia novo programa de habitação", h="bbb", hours=2)
    assert find_duplicate(edited, [original]) == (1, "near_headline")

    other_outlet = c(4, "Governo anuncia novo programa de habitação", outlet=3, h="ccc")
    assert find_duplicate(other_outlet, [original]) is None

    too_late = c(5, "Governo anuncia novo programa de habitação", h="ddd", hours=100)
    assert find_duplicate(too_late, [original]) is None


def test_metrics_perfect_and_merged() -> None:
    gold = {1: "a", 2: "a", 3: "b", 4: "b"}
    m = evaluate(gold, {1: 10, 2: 10, 3: 20, 4: 20})
    assert m.bcubed_f1 == 1.0 and m.wrong_merges == 0 and m.wrong_splits == 0

    merged = evaluate(gold, {1: 1, 2: 1, 3: 1, 4: 1})
    assert merged.bcubed_recall == 1.0
    assert merged.bcubed_precision == 0.5
    assert merged.wrong_merges == 4

    split = evaluate(gold, {1: 1, 2: 2, 3: 3, 4: 4})
    assert split.bcubed_precision == 1.0
    assert split.wrong_splits == 2
