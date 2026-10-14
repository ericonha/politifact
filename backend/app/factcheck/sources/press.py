"""Notícias já coletadas pelo sistema que falam do mesmo assunto: SÓ CONTEXTO.

Dez veículos repetindo uma frase não a tornam verdadeira: a imprensa nunca
produz "verdadeiro/falso". No máximo, quando vários veículos apontam para o mesmo
lado, o veredito é "provavelmente..." (ver press_verdict.py).
Busca por texto completo do PostgreSQL (português) em título e resumo.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, literal_column, select
from sqlalchemy.orm import Session

from app.factcheck.sources import EvidenceItem
from app.factcheck.terms import overlap_ok, query_terms
from app.models import Article, Outlet

LOOKBACK = timedelta(days=90)
MAX_RESULTS = 6

# Mesma expressão do índice GIN criado na migração 0009 (para o índice ser usado).
_PT = literal_column("'portuguese'::regconfig")
_DOC = func.to_tsvector(_PT, func.coalesce(Article.headline, "") + " " + func.coalesce(Article.summary, ""))


def build_query(claim: str) -> str | None:
    """Palavras-chave ligadas por "or" (sintaxe do websearch_to_tsquery).

    Exigir todas as palavras da frase quase nunca acha nada; o ranking põe as melhores no topo
    e `overlap_ok` descarta depois as que só tocam no assunto.
    """
    terms = query_terms(claim)
    return " or ".join(terms) if terms else None


def search(session: Session, query: str, exclude_article_id: int | None = None) -> list[EvidenceItem]:
    terms = query_terms(query)
    built = " or ".join(terms) if terms else None
    if built is None:
        return []
    q = func.websearch_to_tsquery(_PT, built)
    rank = func.ts_rank(_DOC, q)
    stmt = (
        select(Article, Outlet.name, rank.label("rank"))
        .join(Outlet, Outlet.id == Article.outlet_id)
        .where(_DOC.op("@@")(q), Article.duplicate_of_id.is_(None),
               Article.published_at >= datetime.now(UTC) - LOOKBACK)
        .order_by(rank.desc(), Article.published_at.desc())
        .limit(MAX_RESULTS * 5)
    )
    if exclude_article_id is not None:
        stmt = stmt.where(Article.id != exclude_article_id)
    items: list[EvidenceItem] = []
    seen_outlets: set[str] = set()
    for a, outlet, r in session.execute(stmt):
        if outlet in seen_outlets:  # um resultado por veículo
            continue
        if not overlap_ok(terms, f"{a.headline} {a.summary or ''}"):
            continue
        seen_outlets.add(outlet)
        items.append(EvidenceItem(
            provider="press", source_type="press", source_url=a.original_url,
            source_title=f"{outlet}: {a.headline}", relevant_passage=(a.summary or a.headline)[:500],
            relationship="context", verification_status="context_only",
            published_at=a.published_at.date() if a.published_at else None,
            data={"article_id": a.id, "outlet": outlet, "rank": float(r)},
        ))
        if len(items) >= MAX_RESULTS:
            break
    return items
