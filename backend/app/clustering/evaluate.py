"""Conjunto de teste do agrupamento: exportar amostra, rotular à mão e medir.

1) Exportar ~100 notícias recentes para rotular:
     docker compose exec api python -m app.clustering.evaluate export --n 100 -o data/gabarito.csv

2) Abrir data/gabarito.csv numa planilha e preencher a coluna "historia" com um
   rótulo livre por história (ex.: "stf-marco-temporal"). Notícias da mesma
   história recebem o mesmo rótulo; notícia isolada recebe um rótulo só dela.
   Dica: ordenar por título ajuda a achar as parecidas. Linhas sem rótulo são ignoradas.

3) Medir:
     docker compose exec api python -m app.clustering.evaluate run data/gabarito.csv
     docker compose exec api python -m app.clustering.evaluate run data/gabarito.csv --sweep

A avaliação reagrupa só as notícias do gabarito, do zero, com os parâmetros
dados; não mexe nas histórias do banco.
"""

import argparse
import csv
import sys
from dataclasses import replace
from pathlib import Path

from sqlalchemy import func, select

from app.clustering.core import Params, cluster_offline
from app.clustering.metrics import ClusterMetrics, evaluate
from app.clustering.pipeline import _features
from app.db import SessionLocal
from app.models import Article, Outlet

FIELDS = ["article_id", "veiculo", "publicado_em", "titulo", "resumo", "link", "historia"]


def export_sample(n: int, out: Path | None) -> None:
    """As N notícias mais recentes (sem duplicatas), em ordem de publicação.

    Notícias recentes e contíguas no tempo têm mais chance de cobrir os mesmos
    fatos em veículos diferentes, o que gera pares positivos para o teste.
    """
    with SessionLocal() as s:
        rows = s.execute(
            select(Article, Outlet.name)
            .join(Outlet, Outlet.id == Article.outlet_id)
            .where(Article.published_at.is_not(None), Article.duplicate_of_id.is_(None))
            .order_by(Article.published_at.desc())
            .limit(n)
        ).all()
    rows.reverse()

    fh = open(out, "w", newline="", encoding="utf-8") if out else sys.stdout
    try:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for a, outlet_name in rows:
            w.writerow({
                "article_id": a.id,
                "veiculo": outlet_name,
                "publicado_em": a.published_at.isoformat() if a.published_at else "",
                "titulo": a.headline,
                "resumo": (a.summary or "")[:200],
                "link": a.original_url,
                "historia": "",
            })
    finally:
        if out:
            fh.close()
    if out:
        print(f"{len(rows)} notícias exportadas para {out}. Preencha a coluna 'historia'.")


def load_gold(path: Path) -> dict[int, str]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        sample = fh.read(2048)
        fh.seek(0)
        # Planilhas em português costumam salvar CSV com ";".
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        gold = {}
        for row in csv.DictReader(fh, dialect=dialect):
            label = (row.get("historia") or "").strip()
            if label:
                gold[int(row["article_id"])] = label.lower()
    if not gold:
        raise SystemExit("Nenhuma linha com a coluna 'historia' preenchida.")
    return gold


def _print_metrics(m: ClusterMetrics) -> None:
    print(f"notícias avaliadas:      {m.n_articles}")
    print(f"histórias no gabarito:   {m.n_gold_stories}  ({m.gold_pairs} pares que deveriam estar juntos)")
    print(f"histórias do sistema:    {m.n_pred_stories}")
    print(f"B-cubed precisão:        {m.bcubed_precision:.3f}   (baixa = junta coisas diferentes)")
    print(f"B-cubed recall:          {m.bcubed_recall:.3f}   (baixo = separa a mesma história)")
    print(f"B-cubed F1:              {m.bcubed_f1:.3f}")
    print(f"junções erradas (pares): {m.wrong_merges}")
    print(f"separações erradas:      {m.wrong_splits}")


def run(gold_path: Path, params: Params, sweep: bool, use_embeddings: bool) -> None:
    gold = load_gold(gold_path)
    with SessionLocal() as s:
        articles = s.scalars(select(Article).where(Article.id.in_(gold))).all()
        n_emb = s.scalar(
            select(func.count()).select_from(Article)
            .where(Article.id.in_(gold), Article.embedding.is_not(None))
        )
        feats = [_features(a) for a in articles]

    missing = set(gold) - {a.id for a in articles}
    if missing:
        print(f"Aviso: {len(missing)} ids do gabarito não existem no banco e foram ignorados.")
    if not use_embeddings:
        feats = [replace(f, embedding=None) for f in feats]
        print("Modo: só léxico + entidades (sem embeddings).")
    else:
        print(f"Modo: com embeddings em {n_emb} de {len(feats)} notícias.")
        if n_emb < len(feats):
            print("  (rode o processamento com o Ollama ligado para gerar os que faltam)")
    print()

    if not sweep:
        print(f"limiar de junção = {params.assign_threshold:.2f}")
        _print_metrics(evaluate(gold, cluster_offline(feats, params)))
        return

    print("limiar  precisão  recall   F1     junções  separações  histórias")
    best = None
    t = 0.30
    while t <= 0.851:
        p = params.with_thresholds(round(t, 2), min(params.new_story_threshold, round(t, 2)))
        m = evaluate(gold, cluster_offline(feats, p))
        print(f" {t:.2f}    {m.bcubed_precision:.3f}    {m.bcubed_recall:.3f}   {m.bcubed_f1:.3f}"
              f"   {m.wrong_merges:6d}   {m.wrong_splits:9d}   {m.n_pred_stories:8d}")
        if best is None or m.bcubed_f1 > best[1]:
            best = (t, m.bcubed_f1)
        t += 0.05
    assert best is not None
    print(f"\nMelhor F1: {best[1]:.3f} com limiar de junção {best[0]:.2f}.")
    print("Para usar, mude assign_threshold em app/clustering/core.py (Params).")
    print("O limiar de 'nova história' só controla quantas notícias vão para a fila de revisão.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("export", help="exporta notícias recentes para rotular")
    e.add_argument("--n", type=int, default=100)
    e.add_argument("-o", "--out", type=Path)

    r = sub.add_parser("run", help="mede o agrupamento contra o gabarito")
    r.add_argument("gold", type=Path)
    r.add_argument("--assign", type=float, help="limiar de junção (padrão: o de Params)")
    r.add_argument("--sweep", action="store_true", help="testa vários limiares de junção")
    r.add_argument("--no-embeddings", action="store_true")

    args = parser.parse_args()
    if args.cmd == "export":
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
        export_sample(args.n, args.out)
    else:
        params = Params()
        if args.assign is not None:
            params = params.with_thresholds(args.assign, min(params.new_story_threshold, args.assign))
        run(args.gold, params, args.sweep, not args.no_embeddings)


if __name__ == "__main__":
    main()
