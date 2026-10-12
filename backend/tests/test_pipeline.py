"""Testes de integração do pipeline de agrupamento (precisam do Postgres do compose).

Usam um embedder falso, então não precisam do Ollama. Cada teste cria seu
próprio veículo e notícias e apaga tudo no fim.
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.clustering.core import Params
from app.clustering.pipeline import process_new_articles
from app.db import SessionLocal
from app.ingestion.normalize import content_hash
from app.models import Article, ClusteringDecision, Outlet, Story, StoryArticle

# Data bem no passado: nenhuma história real fica na janela de comparação.
T0 = datetime(2001, 1, 1, 12, 0, tzinfo=UTC)


class FakeEmbedder:
    """Vetor = presença de palavras-chave; textos do mesmo tema ficam próximos."""

    model = "fake"
    topics = ["marco temporal", "corinthians", "selic"]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0 if t in x.lower() else 0.0 for t in self.topics] + [0.01] for x in texts]


@pytest.fixture
def outlets() -> Iterator[list[int]]:
    tag = uuid.uuid4().hex[:8]
    with SessionLocal() as s:
        os_ = [
            Outlet(slug=f"t{i}-{tag}", name=f"Teste {i}", canonical_domain=f"t{i}-{tag}.example",
                   country="BR", language="pt-BR", feed_urls=[], active=False)
            for i in range(2)
        ]
        s.add_all(os_)
        s.commit()
        ids = [o.id for o in os_]
    yield ids
    with SessionLocal() as s:
        art_ids = list(s.scalars(select(Article.id).where(Article.outlet_id.in_(ids))))
        story_ids = list(s.scalars(
            select(StoryArticle.story_id).where(StoryArticle.article_id.in_(art_ids))))
        s.execute(delete(ClusteringDecision).where(ClusteringDecision.article_id.in_(art_ids)))
        s.execute(delete(StoryArticle).where(StoryArticle.article_id.in_(art_ids)))
        s.execute(delete(Story).where(Story.id.in_(story_ids)))
        s.execute(update_dups_none(art_ids))
        s.execute(delete(Article).where(Article.id.in_(art_ids)))
        s.execute(delete(Outlet).where(Outlet.id.in_(ids)))
        s.commit()


def update_dups_none(ids):
    return Article.__table__.update().where(Article.id.in_(ids)).values(duplicate_of_id=None)


def add(s, outlet_id: int, headline: str, summary: str = "", hours: float = 0) -> Article:
    a = Article(
        outlet_id=outlet_id, canonical_url=f"https://x.example/{uuid.uuid4().hex}",
        original_url="https://x.example/", headline=headline, summary=summary,
        published_at=T0 + timedelta(hours=hours), first_seen_at=T0 + timedelta(hours=hours),
        collected_at=T0, collection_provider="test", content_hash=content_hash(headline, summary),
        processing_status="new",
    )
    s.add(a)
    s.flush()
    return a


def test_groups_dedups_and_logs(outlets: list[int]) -> None:
    o1, o2 = outlets
    with SessionLocal() as s:
        a1 = add(s, o1, "STF retoma julgamento do marco temporal", "Supremo analisa terras")
        a2 = add(s, o2, "Marco temporal volta à pauta do STF", "Julgamento no Supremo", hours=1)
        a3 = add(s, o1, "Corinthians vence clássico", "Vitória por 2 a 1", hours=2)
        dup_same = add(s, o1, "STF retoma julgamento do marco temporal", "Supremo analisa terras", hours=3)
        s.commit()
        ids = [a1.id, a2.id, a3.id, dup_same.id]

        process_new_articles(s, FakeEmbedder(), Params().with_thresholds(0.55, 0.40), only_ids=ids)

        arts = {a.id: a for a in s.scalars(select(Article).where(Article.id.in_(ids)))}
        story_of = dict(s.execute(
            select(StoryArticle.article_id, StoryArticle.story_id).where(StoryArticle.article_id.in_(ids))
        ).all())

    assert story_of[a1.id] == story_of[a2.id]
    assert story_of[a3.id] != story_of[a1.id]
    assert arts[dup_same.id].duplicate_of_id == a1.id
    assert arts[dup_same.id].processing_status == "duplicate"
    assert dup_same.id not in story_of  # mesma fonte: não conta duas vezes
    assert all(arts[i].embedding_model == "fake" for i in (a1.id, a2.id, a3.id))


def test_syndicated_copy_joins_original_story(outlets: list[int]) -> None:
    o1, o2 = outlets
    with SessionLocal() as s:
        orig = add(s, o1, "Copom mantém a Selic", "Decisão unânime")
        copy = add(s, o2, "Copom mantém a Selic", "Decisão unânime", hours=1)
        s.commit()
        process_new_articles(s, FakeEmbedder(), only_ids=[orig.id, copy.id])
        links = dict(s.execute(
            select(StoryArticle.article_id, StoryArticle.assignment_method)
            .where(StoryArticle.article_id.in_([orig.id, copy.id]))
        ).all())
    assert links[copy.id] == "syndicated"


def test_runs_without_embedder(outlets: list[int]) -> None:
    o1, _ = outlets
    with SessionLocal() as s:
        a = add(s, o1, "Notícia isolada sobre outro tema qualquer")
        s.commit()
        stats = process_new_articles(s, None, only_ids=[a.id])
        s.refresh(a)
    assert stats.processed == 1
    assert a.processing_status == "processed"
    assert a.embedding is None
