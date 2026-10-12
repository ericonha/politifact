"""Esquema relacional da seção 9 do plano.

Princípios aplicados aqui:
- published_at, updated_at, first_seen_at e collected_at são campos separados
  (nunca substituir publicação por descoberta).
- Classificação política fica em tabela própria, sempre atribuída a um avaliador
  (fora do MVP, mas a tabela já existe para não exigir migração destrutiva).
- Fact-checks são versionados via supersedes_id; nada é sobrescrito.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now_col(**kw) -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), **kw)


class Outlet(Base):
    __tablename__ = "outlets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    canonical_domain: Mapped[str] = mapped_column(String(255), unique=True)
    country: Mapped[str] = mapped_column(String(2))
    language: Mapped[str] = mapped_column(String(10))
    feed_urls: Mapped[list[str]] = mapped_column(JSONB, default=list)
    collection_notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = _now_col()

    articles: Mapped[list["Article"]] = relationship(back_populates="outlet")
    bias_ratings: Mapped[list["OutletBiasRating"]] = relationship(back_populates="outlet")


class OutletBiasRating(Base):
    __tablename__ = "outlet_bias_ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    provider: Mapped[str] = mapped_column(String(200))
    rating: Mapped[str] = mapped_column(String(32))
    methodology_url: Mapped[str | None] = mapped_column(Text)
    reference_url: Mapped[str | None] = mapped_column(Text)
    assessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confidence: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)

    outlet: Mapped[Outlet] = relationship(back_populates="bias_ratings")


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint("canonical_url", name="uq_articles_canonical_url"),
        Index("ix_articles_outlet_published", "outlet_id", "published_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    canonical_url: Mapped[str] = mapped_column(Text)
    original_url: Mapped[str] = mapped_column(Text)
    feed_guid: Mapped[str | None] = mapped_column(Text)
    headline: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = _now_col()
    collected_at: Mapped[datetime] = _now_col()
    language: Mapped[str | None] = mapped_column(String(10))
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    content_reference: Mapped[str | None] = mapped_column(Text)
    collection_provider: Mapped[str] = mapped_column(String(64))
    # new -> processed | needs_review | duplicate
    processing_status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector())
    embedding_model: Mapped[str | None] = mapped_column(String(128))
    duplicate_of_id: Mapped[int | None] = mapped_column(ForeignKey("articles.id"), index=True)
    duplicate_method: Mapped[str | None] = mapped_column(String(32))

    outlet: Mapped[Outlet] = relationship(back_populates="articles")
    story_links: Mapped[list["StoryArticle"]] = relationship(back_populates="article")


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    first_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = _now_col()
    updated_at: Mapped[datetime] = _now_col(onupdate=func.now())

    article_links: Mapped[list["StoryArticle"]] = relationship(back_populates="story")


class StoryArticle(Base):
    __tablename__ = "story_articles"

    story_id: Mapped[int] = mapped_column(ForeignKey("stories.id"), primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), primary_key=True)
    cluster_confidence: Mapped[float | None] = mapped_column(Float)
    assignment_method: Mapped[str] = mapped_column(String(32))
    assigned_at: Mapped[datetime] = _now_col()

    story: Mapped[Story] = relationship(back_populates="article_links")
    article: Mapped[Article] = relationship(back_populates="story_links")


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    article_id: Mapped[int | None] = mapped_column(ForeignKey("articles.id"), index=True)
    story_id: Mapped[int | None] = mapped_column(ForeignKey("stories.id"), index=True)
    claim_text: Mapped[str] = mapped_column(Text)
    claim_type: Mapped[str | None] = mapped_column(String(32))
    context: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32), default="user")
    extraction_model: Mapped[str | None] = mapped_column(String(128))
    extraction_version: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = _now_col()


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), index=True)
    source_url: Mapped[str] = mapped_column(Text)
    source_title: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str | None] = mapped_column(String(32))
    relevant_passage: Mapped[str | None] = mapped_column(Text)
    evidence_relationship: Mapped[str] = mapped_column(String(16))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime] = _now_col()
    verification_status: Mapped[str] = mapped_column(String(32), default="unverified")


class FactCheck(Base):
    __tablename__ = "fact_checks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), index=True)
    assessment: Mapped[str] = mapped_column(String(32))
    explanation: Mapped[str] = mapped_column(Text)
    limitations: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(String(32), default="pending_review")
    model_name: Mapped[str | None] = mapped_column(String(128))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = _now_col()
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("fact_checks.id"))


class ArticleAnalysis(Base):
    __tablename__ = "article_analyses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), index=True)
    topics: Mapped[list | None] = mapped_column(JSONB)
    entities: Mapped[list | None] = mapped_column(JSONB)
    framing_summary: Mapped[str | None] = mapped_column(Text)
    language_characteristics: Mapped[dict | None] = mapped_column(JSONB)
    analysis_model: Mapped[str | None] = mapped_column(String(128))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = _now_col()


class CollectionRun(Base):
    __tablename__ = "collection_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    provider: Mapped[str] = mapped_column(String(64))
    outlet_id: Mapped[int | None] = mapped_column(ForeignKey("outlets.id"), index=True)
    started_at: Mapped[datetime] = _now_col(index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    records_discovered: Mapped[int] = mapped_column(Integer, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="running")
    error_summary: Mapped[str | None] = mapped_column(Text)


class ClusteringDecision(Base):
    """Registro de cada decisão de agrupamento (automática ou manual).

    Nada é apagado: uma correção manual cria uma nova decisão e marca a
    anterior como resolvida (resolved_by_id aponta para a correção).
    decision: assigned | new_story | ambiguous | duplicate | manual_assign | manual_new_story
    """

    __tablename__ = "clustering_decisions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), index=True)
    story_id: Mapped[int | None] = mapped_column(ForeignKey("stories.id"), index=True)
    candidate_story_id: Mapped[int | None] = mapped_column(ForeignKey("stories.id"))
    decision: Mapped[str] = mapped_column(String(16))
    score: Mapped[float | None] = mapped_column(Float)
    algorithm_version: Mapped[str] = mapped_column(String(64))
    details: Mapped[dict | None] = mapped_column(JSONB)
    decided_at: Mapped[datetime] = _now_col()
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by_id: Mapped[int | None] = mapped_column(ForeignKey("clustering_decisions.id"))
