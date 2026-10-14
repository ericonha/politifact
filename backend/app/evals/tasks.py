"""As três tarefas avaliadas. Cada uma recebe os casos e devolve resultados por caso.

Nada aqui acessa banco ou rede por conta própria: o LLM entra por parâmetro (`complete_json`),
então os testes usam um modelo falso e o runner usa o Ollama.
"""

import json
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from app.evals import metrics
from app.factcheck import extract as ex
from app.factcheck import press_verdict as pv
from app.factcheck.parse import fold, parse
from app.factcheck.sources import EvidenceItem, bcb

DATA_DIR = Path(__file__).resolve().parents[2] / "evals" / "data"
CHECKABLE = {"fato", "numero", "citacao"}
STANCE_LABELS = list(pv.STANCES)
VERDICTS = ["provavelmente_verdadeiro", "provavelmente_falso", "sem_evidencia"]


def load(name: str, data_dir: Path | None = None) -> list[dict]:
    path = (data_dir or DATA_DIR) / f"{name}.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{name}: ids repetidos")
    return rows


@dataclass
class Meter:
    """Embrulha o LLM: mede a latência e conta as falhas, sem esconder nenhuma."""

    inner: object
    calls: int = 0
    errors: int = 0
    seconds: list[float] = field(default_factory=list)

    @property
    def model(self) -> str:
        return self.inner.model

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        from app.framing.llm import LLMError

        self.calls += 1
        t0 = time.perf_counter()
        try:
            return self.inner.complete_json(system, user, schema)
        except LLMError:
            self.errors += 1
            raise
        finally:
            self.seconds.append(time.perf_counter() - t0)

    def stats(self) -> dict:
        return {"calls": self.calls, "errors": self.errors,
                "p50_s": metrics.percentile(self.seconds, 0.5), "p95_s": metrics.percentile(self.seconds, 0.95)}


# ------------------------------------------------------------------ extração

def score_extract(case: dict, claims: list[ex.ExtractedClaim]) -> dict:
    used: set[int] = set()
    found = type_ok = checkable_ok = 0
    detail = []
    for exp in case["expected"]:
        key = fold(exp["key"])
        hit = next((i for i, c in enumerate(claims)
                    if i not in used and (key in fold(c.text) or key in fold(c.quote))), None)
        row = {"key": exp["key"], "expected": exp["type"], "got": None}
        if hit is not None:
            used.add(hit)
            got = claims[hit].type
            row["got"] = got
            found += 1
            type_ok += got == exp["type"]
            checkable_ok += (got in CHECKABLE) == (exp["type"] in CHECKABLE)
        detail.append(row)
    leaks = sum(1 for f in case.get("forbidden", []) for c in claims if fold(f) in fold(c.text))
    return {"id": case["id"], "expected_n": len(case["expected"]), "found": found, "type_ok": type_ok,
            "checkable_ok": checkable_ok, "extras": len(claims) - len(used), "leaks": leaks, "detail": detail}


def run_extract(cases: list[dict], llm=None) -> dict:
    """llm=None é a linha de base por regras (o que o sistema faz sem modelo)."""
    meter = Meter(llm) if llm is not None else None
    results, fallbacks = [], 0
    for case in cases:
        claims, info = ex.extract(case["text"], meter)
        if meter is not None and info.get("method") != "llm":
            fallbacks += 1
        results.append(score_extract(case, claims))
    exp_n = sum(r["expected_n"] for r in results)
    found = sum(r["found"] for r in results)
    return {
        "task": "extract", "cases": len(cases), "expected_claims": exp_n,
        "recall": metrics.rate(found, exp_n),
        "type_accuracy": metrics.rate(sum(r["type_ok"] for r in results), found),
        "checkable_agreement": metrics.rate(sum(r["checkable_ok"] for r in results), found),
        "extras_per_text": sum(r["extras"] for r in results) / len(results) if results else None,
        "prompt_leaks": sum(r["leaks"] for r in results),
        "fallbacks_to_rules": fallbacks if meter is not None else None,
        "llm": meter.stats() if meter is not None else None,
        "results": results,
    }


# ------------------------------------------------------------------ posição da imprensa

def to_evidence(row: dict) -> tuple[int, EvidenceItem]:
    ev = EvidenceItem("press", "press", f"https://exemplo.invalid/{row['id']}", f"{row['outlet']}: {row['title']}",
                      row["summary"], "context", "context_only", data={"outlet": row["outlet"]})
    return row["id"], ev


def verdict_of(items, stances) -> str:
    agg = pv.aggregate(items, stances)
    return agg[0] if agg else "sem_evidencia"


def gold_verdict(case: dict) -> str:
    items = [to_evidence(r) for r in case["items"]]
    return verdict_of(items, {r["id"]: pv.Stance(r["stance"]) for r in case["items"]})


def run_stance(cases: list[dict], llm=None) -> dict:
    """llm=None: linha de base "tudo irrelevante" (sempre sem evidência)."""
    meter = Meter(llm) if llm is not None else None
    from app.framing.llm import LLMError

    pairs, results, quote_rejected, errors = [], [], 0, 0
    for case in cases:
        items = [to_evidence(r) for r in case["items"]]
        stances = {i: pv.Stance("irrelevant") for i, _ in items}
        problems: list[str] = []
        if meter is not None:
            try:
                raw = meter.complete_json(pv.SYSTEM, pv.build_user_prompt(case["claim"], items), pv.SCHEMA)
                stances, problems = pv.validate_stances(raw, items)
            except LLMError as exc:
                errors += 1
                problems = [f"LLM: {exc}"]
        quote_rejected += sum("trecho" in p for p in problems)
        got_v, want_v = verdict_of(items, stances), gold_verdict(case)
        for r in case["items"]:
            pairs.append((r["stance"], stances[r["id"]].stance))
        results.append({"id": case["id"], "group": case.get("group"), "gold": want_v, "got": got_v,
                        "items": [{"id": r["id"], "expected": r["stance"], "got": stances[r["id"]].stance}
                                  for r in case["items"]], "problems": problems})
    per = metrics.per_class(pairs, STANCE_LABELS)
    n_ok = sum(e == g for e, g in pairs)
    # O erro grave: afirmar um lado quando o gabarito não afirma esse lado.
    confident_wrong = sum(1 for r in results if r["got"] != "sem_evidencia" and r["got"] != r["gold"])
    groups: dict[str, list[dict]] = {}
    for r in results:
        if r["group"]:
            groups.setdefault(r["group"], []).append(r)
    pair_ok = sum(all(x["got"] == x["gold"] for x in g) for g in groups.values())
    return {
        "task": "stance", "cases": len(cases), "items": len(pairs),
        "item_accuracy": metrics.rate(n_ok, len(pairs)),
        "majority_baseline": metrics.majority_baseline([e for e, _ in pairs]),
        "macro_f1": metrics.macro_f1(per), "per_class": per, "confusion": metrics.confusion(pairs, STANCE_LABELS),
        "verdict_accuracy": metrics.rate(sum(r["got"] == r["gold"] for r in results), len(results)),
        "confident_wrong": metrics.rate(confident_wrong, len(results)),
        "swap_pairs_correct": metrics.rate(pair_ok, len(groups)),
        "quotes_rejected": quote_rejected, "llm_errors": errors,
        "llm": meter.stats() if meter is not None else None,
        "results": results,
    }


# ------------------------------------------------------------------ dados oficiais (determinística)

def run_official(cases: list[dict]) -> dict:
    """Leitura da afirmação + comparação com séries congeladas. Não usa modelo."""
    results = []
    for case in cases:
        today = date.fromisoformat(case["today"])
        p = parse(case["claim"])
        got = "unchecked"
        if p.checkable:
            pl = bcb.plan(p, today)
            if not isinstance(pl, str):
                rows = case["series"].get(str(pl.code), [])
                pts = [bcb.Point(date.fromisoformat(d), float(v)) for d, v in rows]
                got = bcb.compare(p, pl, pts, today).outcome
        results.append({"id": case["id"], "claim": case["claim"], "expected": case["expected"], "got": got,
                        "note": case.get("note", "")})
    ok = sum(r["expected"] == r["got"] for r in results)
    labels = ["match", "close", "mismatch", "no_data", "unchecked"]
    return {"task": "official", "cases": len(cases), "accuracy": metrics.rate(ok, len(results)),
            "confusion": metrics.confusion([(r["expected"], r["got"]) for r in results], labels),
            "failures": [r for r in results if r["expected"] != r["got"]], "results": results}
