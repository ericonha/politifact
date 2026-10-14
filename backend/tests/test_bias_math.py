"""Medidas de viés de cobertura (puras, sem banco)."""

from datetime import datetime, timedelta

from app.coverage.bias_math import (
    classify_change,
    delay_stats,
    distinctive_terms,
    log_odds_z,
    omission_stats,
    revision_stats,
    tokens,
)

T0 = datetime(2026, 10, 1, 12, 0)


# --- omissões ---------------------------------------------------------------------

def _stories(n, outlets):
    return {i: set(outlets) for i in range(1, n + 1)}


def test_omission_counts_stories_covered_by_many_but_not_by_me() -> None:
    group = {1, 2, 3, 4, 5}
    so = {**_stories(10, {1, 2, 3, 4}), **{100 + i: {2, 3, 4, 5} for i in range(10)}, 500: {2}, 501: {3, 4}}
    r = omission_stats(so, group, outlet_id=1)
    assert r["eligible_stories"] == 20 and r["covered"] == 10 and r["missed"] == 10
    assert r["omission_rate"] == 0.5
    assert all(sid >= 100 for sid in r["blind_spot_ids"])  # só as que ele não cobriu
    assert 500 not in r["blind_spot_ids"] and 501 not in r["blind_spot_ids"]  # menos de 4 veículos: não conta


def test_omission_ignores_stories_before_outlet_was_monitored() -> None:
    group = {1, 2, 3, 4}
    so = {1: {2, 3, 4}, 2: {2, 3, 4}}
    starts = {1: T0, 2: T0 + timedelta(days=5)}
    r = omission_stats(so, group, 1, min_outlets=3,
                       eligible_since={1: T0 + timedelta(days=3)}, story_start=starts)
    assert r["eligible_stories"] == 1 and r["missed"] == 1


def test_omission_average_uses_only_peers_with_enough_stories() -> None:
    group = {1, 2, 3, 4, 5}
    so = {i: {1, 2, 3, 4} for i in range(1, 13)}  # o veículo 5 nunca cobre; 12 histórias
    r = omission_stats(so, group, outlet_id=1)
    assert r["omission_rate"] == 0.0
    # par 5 omitiu 12/12 = 100%; pares 2-4 cobriram tudo; média = 25%
    assert abs(r["average_rate"] - 0.25) < 1e-9


# --- atraso -----------------------------------------------------------------------

def test_delay_is_relative_to_first_outlet() -> None:
    group = {1, 2, 3}
    ft = {s: {1: T0 + timedelta(minutes=60), 2: T0, 3: T0 + timedelta(minutes=5)} for s in range(10)}
    r = delay_stats(ft, group, outlet_id=1)
    assert r["stories"] == 10 and r["median_minutes"] == 60 and r["first_share"] == 0.0 and r["enough"]
    r2 = delay_stats(ft, group, outlet_id=3)
    assert r2["median_minutes"] == 5 and r2["first_share"] == 1.0  # 5 min está dentro da tolerância
    assert delay_stats(ft, group, outlet_id=2)["median_minutes"] == 0


def test_delay_needs_two_outlets_and_few_stories_are_not_enough() -> None:
    group = {1, 2}
    r = delay_stats({1: {1: T0}, 2: {1: T0, 2: T0 + timedelta(minutes=30)}}, group, 1)
    assert r["stories"] == 1 and not r["enough"]


# --- vocabulário ------------------------------------------------------------------

def test_tokens_drop_stopwords_accents_and_short_words() -> None:
    assert tokens("O Ministro disse que a operação foi uma invasão!") == {"ministro", "operacao", "invasao"}


def test_log_odds_prefers_distinctive_words_and_shrinks_rare_ones() -> None:
    a = {"invasao": 30.0, "governo": 40.0, "rara": 1.0}
    b = {"ocupacao": 30.0, "governo": 40.0}
    z = log_odds_z(a, b, n_a=40, n_b=40)
    assert z["invasao"] > 1.96 and z["ocupacao"] < -1.96
    assert abs(z["governo"]) < 0.5
    assert z["rara"] < z["invasao"]  # uma ocorrência não vence uma palavra recorrente


def _docs(words, n, story_offset=0):
    return [(story_offset + i, set(words)) for i in range(n)]


def test_distinctive_terms_find_the_word_each_side_prefers() -> None:
    mine = _docs({"invasao", "governo"}, 30)
    others = _docs({"ocupacao", "governo"}, 30)
    r = distinctive_terms(mine, others)
    assert r["enough"]
    assert r["uses_more"][0]["term"] == "invasao" and r["uses_less"][0]["term"] == "ocupacao"
    assert "governo" not in [x["term"] for x in r["uses_more"] + r["uses_less"]]


def test_distinctive_terms_refuse_small_samples() -> None:
    r = distinctive_terms(_docs({"invasao"}, 5), _docs({"ocupacao"}, 40))
    assert not r["enough"] and r["uses_more"] == []


def test_story_specific_words_do_not_count_when_all_sides_cover_the_story() -> None:
    mine = [(i, {"flavio", "palavra"}) for i in range(30)]
    others = [(i, {"flavio"}) for i in range(30) for _ in range(3)]  # 3 outros por história
    r = distinctive_terms(mine, others)
    terms = [x["term"] for x in r["uses_more"]]
    assert "palavra" in terms and "flavio" not in terms


# --- edições ----------------------------------------------------------------------

def test_change_kinds() -> None:
    c = classify_change("Governo anuncia pacote de R$ 10 bilhões", None, "Governo anuncia pacote de R$ 12 bilhões", None)
    assert c["kind"] == "possivel_sentido" and c["numbers_changed"]
    c = classify_change("Ministro confirma demissão", None, "Ministro não confirma demissão", None)
    assert c["kind"] == "possivel_sentido" and c["negation_changed"]
    c = classify_change("Polícia faz operação contra quadrilha de fraudes em SP",
                        None, "Polícia faz operação contra quadrilha de fraudes na capital paulista", None)
    assert c["kind"] in ("ajuste", "reescrita")
    c = classify_change("Operação da PF prende ex-assessor", None, "Bolsonaro reage a prisão de aliado", None)
    assert c["kind"] == "reescrita" and c["similarity"] < 0.8
    c = classify_change("Selic cai a 13,25%", "Copom decide", "Selic cai a 13,25%", "Copom decide hoje à noite")
    assert c["kind"] == "resumo" and not c["headline_changed"] and c["summary_changed"]


def test_declared_correction_is_detected_only_when_new() -> None:
    c = classify_change("Prefeito é preso", None, "Prefeito é preso; texto corrigido", None)
    assert c["declared"]
    c = classify_change("Errata: prefeito é preso", None, "Errata: prefeito é detido", None)
    assert not c["declared"]


def test_punctuation_and_case_are_not_an_edit() -> None:
    assert not classify_change("Selic cai.", None, "SELIC CAI", None)["headline_changed"]


def test_revision_stats_and_peer_average() -> None:
    edited = {"headline_changed": True, "kind": "possivel_sentido", "declared": True}
    rewrite = {"headline_changed": True, "kind": "reescrita", "declared": False}
    summary_only = {"headline_changed": False, "kind": "resumo", "declared": False}
    r = revision_stats({1: 100, 2: 100, 3: 100}, {1: [edited, rewrite, summary_only], 2: [rewrite], 3: []}, 1)
    assert r["edited"] == 2 and r["edited_share"] == 0.02 and r["meaning_flagged"] == 1
    assert r["declared_share"] == 0.5
    assert abs(r["average_edited_share"] - 0.005) < 1e-9
