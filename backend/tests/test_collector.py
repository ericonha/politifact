"""Testes de integração do coletor: exigem o Postgres do docker compose.

Usam um veículo temporário e um "fetcher" falso, então não acessam a internet.
Rodar com:  docker compose exec api pytest
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select

from app.db import SessionLocal
from app.ingestion.collector import collect_outlet
from app.models import Article, ClusteringDecision, CollectionRun, Outlet, StoryArticle

RSS = (Path(__file__).parent / "fixtures" / "rss2.xml").read_bytes()
NOW = datetime(2026, 10, 12, 20, 0, tzinfo=UTC)


@pytest.fixture
def outlet() -> Iterator[Outlet]:
    slug = f"teste-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as s:
        o = Outlet(
            slug=slug, name="Teste", canonical_domain=f"{slug}.example",
            country="BR", language="pt-BR", feed_urls=["https://feed.example/a"],
        )
        s.add(o)
        s.commit()
        yield o
        # O worker pode ter agrupado os artigos de teste no meio do caminho.
        ids = select(Article.id).where(Article.outlet_id == o.id).scalar_subquery()
        s.execute(delete(ClusteringDecision).where(ClusteringDecision.article_id.in_(ids)))
        s.execute(delete(StoryArticle).where(StoryArticle.article_id.in_(ids)))
        s.execute(delete(Article).where(Article.outlet_id == o.id))
        s.execute(delete(CollectionRun).where(CollectionRun.outlet_id == o.id))
        s.execute(delete(Outlet).where(Outlet.id == o.id))
        s.commit()


def _count(outlet_id: int) -> int:
    with SessionLocal() as s:
        return s.scalar(select(func.count()).select_from(Article).where(Article.outlet_id == outlet_id))


def test_collect_is_idempotent(outlet: Outlet) -> None:
    # As URLs do fixture são fixas; para não colidir com outros testes, troca o domínio.
    feed = RSS.replace(b"exemplo.com.br", outlet.canonical_domain.encode())
    with SessionLocal() as s:
        o = s.get(Outlet, outlet.id)
        run1 = collect_outlet(s, o, fetcher=lambda _: feed, now=NOW)
        run2 = collect_outlet(s, o, fetcher=lambda _: feed, now=NOW)

    # Se falhar com "partial", veja a mensagem: costuma ser migração não aplicada
    # (rode `docker compose up -d --build` para a API aplicar as migrações).
    assert run1.status == "success", run1.error_summary
    assert (run1.records_discovered, run1.records_inserted) == (3, 3)
    assert (run2.records_discovered, run2.records_inserted) == (3, 0)
    assert _count(outlet.id) == 3


def test_tracking_params_stripped_and_dates_kept_separate(outlet: Outlet) -> None:
    feed = RSS.replace(b"exemplo.com.br", outlet.canonical_domain.encode())
    with SessionLocal() as s:
        collect_outlet(s, s.get(Outlet, outlet.id), fetcher=lambda _: feed, now=NOW)
        articles = {a.headline: a for a in s.scalars(select(Article).where(Article.outlet_id == outlet.id))}

    first = articles["Câmara aprova projeto & segue ao Senado"]
    assert "utm_" not in first.canonical_url
    assert "utm_source" in first.original_url
    assert first.published_at == datetime(2026, 10, 12, 15, 59, 37, tzinfo=UTC)
    assert first.first_seen_at == NOW
    # Sem data no feed: published_at fica vazio, nunca vira a data de descoberta.
    assert articles["Notícia sem data"].published_at is None


def test_failed_feed_is_recorded(outlet: Outlet) -> None:
    def boom(_: str) -> bytes:
        raise RuntimeError("timeout simulado")

    with SessionLocal() as s:
        run = collect_outlet(s, s.get(Outlet, outlet.id), fetcher=boom, now=NOW)

    assert run.status == "failed"
    assert "timeout simulado" in (run.error_summary or "")
    assert run.finished_at is not None
