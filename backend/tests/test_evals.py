"""Harness de avaliação (sem banco, sem rede; LLM falso)."""

from app.evals import metrics, run, tasks
from app.factcheck import extract as ex
from app.factcheck import press_verdict as pv
from app.factcheck.parse import fold
from app.framing.llm import LLMError

# ---------------------------------------------------------------- gabaritos íntegros

def test_gold_extract_is_consistent() -> None:
    for c in tasks.load("extract"):
        assert c["label_status"] == "proposed"
        for e in c["expected"]:
            assert e["type"] in ex.TYPES, c["id"]
            assert fold(e["key"]) in fold(c["text"]), (c["id"], e["key"])


def test_gold_stance_is_consistent() -> None:
    groups: dict[str, int] = {}
    for c in tasks.load("stance"):
        ids = [r["id"] for r in c["items"]]
        assert len(ids) == len(set(ids)), c["id"]
        assert all(r["stance"] in pv.STANCES for r in c["items"]), c["id"]
        if c.get("group"):
            groups[c["group"]] = groups.get(c["group"], 0) + 1
    assert all(n == 2 for n in groups.values())


def test_gold_official_is_consistent() -> None:
    valid = {"match", "close", "mismatch", "no_data", "unchecked"}
    for c in tasks.load("official"):
        assert c["expected"] in valid, c["id"]


def test_official_task_passes_on_current_code() -> None:
    r = tasks.run_official(tasks.load("official"))
    assert r["failures"] == [], r["failures"]


# ---------------------------------------------------------------- métricas

def test_wilson_interval_is_wide_for_small_n() -> None:
    lo, hi = metrics.wilson(5, 5)
    assert lo < 0.6 and hi == 1.0
    lo2, hi2 = metrics.wilson(500, 500)
    assert lo2 > 0.99


def test_per_class_and_macro_f1() -> None:
    pairs = [("a", "a"), ("a", "b"), ("b", "b"), ("b", "b")]
    per = metrics.per_class(pairs, ["a", "b", "c"])
    assert per["a"]["recall"] == 0.5 and per["b"]["precision"] == 2 / 3
    assert per["c"]["support"] == 0 and per["c"]["f1"] is None
    assert 0 < metrics.macro_f1(per) < 1


# ---------------------------------------------------------------- tarefas com LLM falso

class OracleExtract:
    """Devolve exatamente o gabarito, com o trecho literal do texto."""
    model = "oracle"

    def __init__(self, cases):
        self.by_text = {c["text"]: c for c in cases}

    def complete_json(self, system, user, schema):
        text = user.split("<texto>\n", 1)[1].rsplit("\n</texto>", 1)[0]
        case = self.by_text[text]
        claims = []
        for e in case["expected"]:
            sent = next(s for s in text.replace("\n", " ").split(". ") if fold(e["key"]) in fold(s))
            claims.append({"text": sent, "quote": sent.rstrip("."), "type": e["type"]})
        return {"claims": claims}


def test_extract_oracle_scores_full_and_rules_baseline_runs() -> None:
    cases = tasks.load("extract")
    r = tasks.run_extract(cases, OracleExtract(cases))
    # O oráculo repete a frase inteira, então as chaves de frases com duas afirmações podem colidir:
    assert r["recall"]["value"] >= 0.9
    assert r["fallbacks_to_rules"] == 0 and r["llm"]["calls"] == len(cases)
    base = tasks.run_extract(cases, None)
    assert base["llm"] is None and base["recall"]["n"] == r["recall"]["n"]


class Broken:
    model = "quebrado"

    def complete_json(self, system, user, schema):
        raise LLMError("fora do ar")


def test_broken_model_is_counted_not_hidden() -> None:
    cases = tasks.load("extract")[:5]
    r = tasks.run_extract(cases, Broken())
    assert r["fallbacks_to_rules"] == 5 and r["llm"]["errors"] == 5
    s = tasks.run_stance(tasks.load("stance")[:4], Broken())
    assert s["llm_errors"] == 4 and s["confident_wrong"]["k"] == 0


def find_case(cases, user):
    """Mesma afirmação pode ter conjuntos de notícias diferentes: identifica o caso pelas manchetes."""
    claim = user.split("\n", 1)[0].removeprefix("Afirmação: ")
    return next(c for c in cases if c["claim"] == claim and all(r["title"] in user for r in c["items"]))


class OracleStance:
    model = "oracle"

    def __init__(self, cases):
        self.cases = cases

    def complete_json(self, system, user, schema):
        case = find_case(self.cases, user)
        rows = []
        for r in case["items"]:
            quote = r["title"] if r["stance"] != "irrelevant" else ""
            rows.append({"id": r["id"], "stance": r["stance"], "quote": quote})
        return {"items": rows}


def test_stance_oracle_is_perfect() -> None:
    cases = tasks.load("stance")
    r = tasks.run_stance(cases, OracleStance(cases))
    assert r["item_accuracy"]["value"] == 1.0 and r["verdict_accuracy"]["value"] == 1.0
    assert r["confident_wrong"]["k"] == 0 and r["swap_pairs_correct"]["value"] == 1.0


class Forger:
    """Classifica tudo como 'supports' com um trecho inventado: a validação tem de barrar."""
    model = "falsario"

    def complete_json(self, system, user, schema):
        ids = [int(x) for x in __import__("re").findall(r"\[id (\d+)\]", user)]
        fake = "trecho que não existe em notícia alguma"
        return {"items": [{"id": i, "stance": "supports", "quote": fake} for i in ids]}


def test_forged_quotes_never_become_a_verdict() -> None:
    r = tasks.run_stance(tasks.load("stance"), Forger())
    assert r["quotes_rejected"] > 0
    assert all(x["got"] == "sem_evidencia" for x in r["results"])
    assert r["confident_wrong"]["k"] == 0


class Credulous:
    """Obedece à instrução plantada na notícia: tudo 'supports', com trecho válido (o título)."""
    model = "credulo"

    def __init__(self, cases):
        self.cases = cases

    def complete_json(self, system, user, schema):
        case = find_case(self.cases, user)
        return {"items": [{"id": r["id"], "stance": "supports", "quote": r["title"]} for r in case["items"]]}


def test_confident_wrong_catches_a_credulous_model() -> None:
    cases = tasks.load("stance")
    r = tasks.run_stance(cases, Credulous(cases))
    assert r["confident_wrong"]["k"] > 0  # o relatório precisa expor esse tipo de erro


def test_evaluate_and_render_end_to_end() -> None:
    ext, st = tasks.load("extract"), tasks.load("stance")

    class Both(OracleStance, OracleExtract):
        def __init__(self):
            OracleStance.__init__(self, st)
            OracleExtract.__init__(self, ext)

        def complete_json(self, system, user, schema):
            return (OracleExtract if "<texto>" in user else OracleStance).complete_json(self, system, user, schema)

    res = run.evaluate(["oraculo"], factory=lambda m: Both())
    md = run.render(res)
    assert "baseline" in md and "oraculo" in md and "Veredito errado e confiante" in md
    assert res["meta"]["datasets"]["stance"]["cases"] == len(st)
