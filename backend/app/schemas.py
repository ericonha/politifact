from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class OutletOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    canonical_domain: str
    country: str
    language: str
    feed_urls: list[str]
    collection_notes: str | None
    active: bool


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    outlet_id: int
    headline: str
    summary: str | None
    canonical_url: str
    original_url: str
    published_at: datetime | None
    updated_at: datetime | None
    first_seen_at: datetime
    collected_at: datetime
    collection_provider: str
    processing_status: str


class CollectionRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    outlet_id: int | None
    started_at: datetime
    finished_at: datetime | None
    records_discovered: int
    records_inserted: int
    records_failed: int
    status: str
    error_summary: str | None


class EnqueuedOut(BaseModel):
    job_id: str


class OutletCoverage(BaseModel):
    outlet_id: int
    outlet_name: str
    article_count: int


class StoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    summary: str | None
    first_observed_at: datetime | None
    last_observed_at: datetime | None
    article_count: int = 0
    outlet_count: int = 0
    coverage: list[OutletCoverage] = []


class HealthOut(BaseModel):
    status: str
    database: str


class StoryArticleOut(BaseModel):
    article_id: int
    outlet_id: int
    outlet_name: str
    headline: str
    summary: str | None
    original_url: str
    published_at: datetime | None
    assignment_method: str  # seed | auto | syndicated | manual
    cluster_confidence: float | None


class StoryDetailOut(StoryOut):
    articles: list[StoryArticleOut] = []


class ReviewItemOut(BaseModel):
    decision_id: int
    score: float | None
    decided_at: datetime
    article_id: int
    outlet_name: str
    headline: str
    summary: str | None
    original_url: str
    published_at: datetime | None
    candidate_story_id: int | None
    candidate_story_title: str | None


class ReviewActionIn(BaseModel):
    action: Literal["assign", "new_story"]


class ReviewActionOut(BaseModel):
    decision_id: int
    story_id: int
