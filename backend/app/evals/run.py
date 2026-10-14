"""Executa a avaliação e compara modelos.

    python -m app.evals.run                                  # linhas de base + dados oficiais (sem Ollama)
    python -m app.evals.run --models qwen2.5:7b,llama3.1:8b  # compara modelos no Ollama

Escreve evals/results/<data>.json e evals/results/latest.md. Os rótulos dos gabaritos são
"proposed": só valem como medida depois de revisados por uma pessoa.
"""

import argparse
import hashlib
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.evals import tasks
from app.factcheck import extract as ex
from app.factcheck import press_verdict as pv

RESULTS_DIR = tasks.DATA_DIR.parent / "results"
BASELINE = "baseline"


def _pct(r: dict | None) -> str:
    if not r or r.get("value") is None:
        return "—"
    return f"{100 * r['value']:.0f}% [{100 * r['low']:.0f}–{100 * r['high']:.0f}] ({r['k']}/{r['n']})"


def _num(v, fmt="{:.2f}") -> str:
    return "—" if v is None else fmt.format(v)


def dataset_info(data_dir: Path | None = None) -> dict:
    out = {}
    for name in ("extract", "stance", "official"):
        path = (data_dir or tasks.DATA_DIR) / f"{name}.jsonl"
        rows = tasks.load(name, data_dir)
        status = sorted({r.get("label_status", "?") for r in rows})
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        out[name] = {"cases": len(rows), "label_status": status, "sha256": digest}
    return out


def make_llm(model: str, url: str | None):
    from app.framing.llm import OllamaChat

    if url is None:
        from app.config import get_settings

        url = get_settings().embeddings_url
    return OllamaChat(url, model, timeout=180.0)


def evaluate(models: list[str], url: str | None = None, data_dir: Path | None = None, factory=None) -> dict:
    """`factory(model)` permite injetar um modelo falso nos testes."""
    factory = factory or (lambda m: make_llm(m, url))
    ext, st = tasks.load("extract", data_dir), tasks.load("stance", data_dir)
    out: dict = {
        "meta": {
            "when": datetime.now(UTC).isoformat(timespec="seconds"), "python": platform.python_version(),
            "prompts": {"extract": ex.PROMPT_VERSION, "stance": pv.PROMPT_VERSION},
            "datasets": dataset_info(data_dir), "models": [BASELINE, *models],
        },
        "official": tasks.run_official(tasks.load("official", data_dir)),
        "extract": {BASELINE: tasks.run_extract(ext, None)},
        "stance": {BASELINE: tasks.run_stance(st, None)},
    }
    for m in models:
        llm = factory(m)
        out["extract"][m] = tasks.run_extract(ext, llm)
        out["stance"][m] = tasks.run_stance(st, llm)
    return out


def _secs(llm: dict) -> str:
    return f"{_num(llm.get('p50_s'), '{:.1f}')} / {_num(llm.get('p95_s'), '{:.1f}')}"


def render(res: dict) -> str:
    meta, out = res["meta"], []
    out += ["# Avaliação", "",
            f"Gerada em {meta['when']} · prompts: extração `{meta['prompts']['extract']}`, "
            f"posição da imprensa `{meta['prompts']['stance']}`", "",
            "| Conjunto | Casos | Rótulos | Versão |", "|---|---|---|---|"]
    for k, d in meta["datasets"].items():
        out.append(f"| {k} | {d['cases']} | {', '.join(d['label_status'])} | `{d['sha256']}` |")
    out += ["", "Intervalos: Wilson 95%. Com poucos casos o intervalo é largo; "
            "diferenças menores que ele não são evidência.", ""]

    o = res["official"]
    out += ["## Dados oficiais (determinístico, séries sintéticas congeladas)", "",
            f"Acerto: {_pct(o['accuracy'])}", ""]
    out += [f"- falha `{f['id']}`: esperado **{f['expected']}**, obtido **{f['got']}** — {f['claim']}"
            for f in o["failures"]]
    if o["failures"]:
        out.append("")

    out += ["## Extração de afirmações", "",
            "| Modelo | Recall | Tipo correto | Checável × não | Extras/texto | Vazamentos | Fallback "
            "| p50 / p95 (s) |",
            "|---|---|---|---|---|---|---|---|"]
    for m, r in res["extract"].items():
        fb = "—" if r["fallbacks_to_rules"] is None else r["fallbacks_to_rules"]
        out.append(f"| {m} | {_pct(r['recall'])} | {_pct(r['type_accuracy'])} | {_pct(r['checkable_agreement'])} | "
                   f"{_num(r['extras_per_text'])} | {r['prompt_leaks']} | {fb} | {_secs(r['llm'] or {})} |")
    out += ["", "“Extras” são afirmações a mais que o gabarito não lista (podem ser legítimas). "
            "“Vazamentos” contam afirmações que repetem uma ordem plantada no texto.", ""]

    out += ["## Posição da imprensa (apoia / contradiz / irrelevante)", "",
            "| Modelo | Acerto por notícia | F1 macro | Veredito certo | Veredito errado e confiante | "
            "Pares de troca de nome | Trechos rejeitados | Erros do LLM | p50 / p95 (s) |",
            "|---|---|---|---|---|---|---|---|---|"]
    for m, r in res["stance"].items():
        out.append(f"| {m} | {_pct(r['item_accuracy'])} | {_num(r['macro_f1'])} | {_pct(r['verdict_accuracy'])} | "
                   f"{_pct(r['confident_wrong'])} | {_pct(r['swap_pairs_correct'])} | {r['quotes_rejected']} | "
                   f"{r['llm_errors']} | {_secs(r['llm'] or {})} |")
    major = next(iter(res["stance"].values()))["majority_baseline"]
    out += ["", f"Referência: responder sempre a classe mais comum acerta {_num(100 * major, '{:.0f}')}% das notícias. "
            "“Veredito errado e confiante” é a métrica que mais importa: o sistema afirmou "
            "“provavelmente verdadeiro/falso” quando o gabarito não afirma esse lado.", ""]
    for m, r in res["stance"].items():
        bad = [x for x in r["results"] if x["got"] != x["gold"]]
        if bad and m != BASELINE:
            diffs = ", ".join(f"`{x['id']}` ({x['got']} ≠ {x['gold']})" for x in bad)
            out.append(f"**{m}** — vereditos diferentes do gabarito: {diffs}")
    return "\n".join(out).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default="", help="modelos do Ollama separados por vírgula")
    ap.add_argument("--url", default=None, help="URL do Ollama (padrão: EMBEDDINGS_URL das configurações)")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    models = [m.strip() for m in a.models.split(",") if m.strip()]
    res = evaluate(models, a.url)
    text = render(res)
    print(text)
    if not a.no_write:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        (RESULTS_DIR / f"{stamp}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        (RESULTS_DIR / "latest.md").write_text(text, encoding="utf-8")
        print(f"\nResultados em {RESULTS_DIR}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
