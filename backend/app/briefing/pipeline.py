"""Gera o resumo de cada seção a partir das histórias mais relevantes das últimas 24 h.

Só regera uma seção quando o conjunto de histórias muda (impressão digital das
histórias e do número de notícias). Cada geração é uma linha nova (histórico).
"""

import hashlib
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.briefing import core
from app.framing.llm import LLM, LLMError
from app.models import Article, Briefing, Outlet, StoryArticle
from app.topics import OTHER, TOPICS

log = logging.getLogger(__name__)

WINDOW = "24h"
WINDOW_DELTA = timedelta(hours=24)
MIN_STORIES = 2


@dataclass
class BriefingStats:
    generated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    skipped_few_stories: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    error: str | None = None


def _fingerprint(stories: list[core.StoryInput]) -> str:
    basis = json.dumps([(s.id, len(s.headlines)) for s in stories])
    return hashlib.sha256(basis.encode()).hexdigest()


def collect_inputs(session: Session, topic: str, since: datetime) -> list[core.StoryInput]:
    from app.main import stories_in_window  # reaproveita a mesma relevância da API

    stories = stories_in_window(session, since, topic)[: core.MAX_STORIES]
    if not stories:
        return []
    ids = [s.id for s in stories]
    rows = session.execute(
        select(StoryArticle.story_id, Outlet.name, Article.headline, Article.summary)
        .join(Article, Article.id == StoryArticle.article_id)
        .join(Outlet, Outlet.id == Article.outlet_id)
        .where(StoryArticle.story_id.in_(ids), Article.published_at >= since, Article.duplicate_of_id.is_(None))
        .order_by(StoryArticle.story_id, Article.published_at)
    ).all()
    heads: dict[int, list[tuple[str, str, str | None]]] = defaultdict(list)
    seen_outlets: dict[int, set[str]] = defaultdict(set)
    for story_id, outlet, headline, summary in rows:
        # Uma manchete por veículo, para o modelo ver a variedade de veículos.
        if outlet in seen_outlets[story_id]:
            continue
        seen_outlets[story_id].add(outlet)
        heads[story_id].append((outlet, headline, summary))
    return [
        core.StoryInput(id=s.id, title=s.title, outlet_count=s.outlet_count, relevance=s.relevance,
                        headlines=heads.get(s.id, []))
        for s in stories
    ]


def generate(session: Session, llm: LLM, topics: list[str] | None = None, force: bool = False) -> BriefingStats:
    stats = BriefingStats()
    now = datetime.now(UTC)
    since = now - WINDOW_DELTA
    for topic in topics or [t for t in TOPICS if t != OTHER]:
        inputs = collect_inputs(session, topic, since)
        if len(inputs) < MIN_STORIES:
            stats.skipped_few_stories.append(topic)
            continue
        fp = _fingerprint(inputs)
        last = session.scalars(
            select(Briefing).where(Briefing.topic == topic, Briefing.window == WINDOW, Briefing.error.is_(None))
            .order_by(Briefing.generated_at.desc()).limit(1)
        ).first()
        if not force and last and last.input_fingerprint == fp and last.model == llm.model \
                and last.prompt_version == core.PROMPT_VERSION:
            stats.unchanged.append(topic)
            continue
        try:
            raw = llm.complete_json(core.SYSTEM, core.build_user_prompt(TOPICS[topic], inputs), core.SCHEMA)
        except LLMError as exc:
            stats.error = str(exc)
            log.warning("LLM indisponível; resumo não gerado: %s", exc)
            break
        result = core.validate(raw, inputs)
        session.add(Briefing(
            topic=topic, window=WINDOW, period_start=since, period_end=now, model=llm.model,
            prompt_version=core.PROMPT_VERSION, input_fingerprint=fp, story_ids=[s.id for s in inputs],
            result={"overview": result.overview, "points": result.points}, validation=result.validation,
        ))
        session.commit()
        (stats.generated if result.usable else stats.rejected).append(topic)
    log.info("resumos: %s", stats)
    return stats


def latest(session: Session) -> list[Briefing]:
    """O resumo utilizável mais recente de cada seção (gerações rejeitadas não aparecem)."""
    sub = (
        select(Briefing.topic, func.max(Briefing.generated_at).label("t"))
        .where(Briefing.window == WINDOW, Briefing.error.is_(None),
               Briefing.validation["status"].astext != "rejected")
        .group_by(Briefing.topic).subquery()
    )
    return list(session.scalars(
        select(Briefing).join(sub, (sub.c.topic == Briefing.topic) & (sub.c.t == Briefing.generated_at))
    ))


if __name__ == "__main__":
    import argparse

    from app.db import SessionLocal
    from app.db_check import ensure_schema_current
    from app.framing.llm import get_llm

    ensure_schema_current()
    parser = argparse.ArgumentParser(description="Gera o resumo por seção com o LLM local.")
    parser.add_argument("--force", action="store_true", help="gera mesmo que as histórias não tenham mudado")
    parser.add_argument("--topic", action="append", help="só estas seções (pode repetir)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    model = get_llm()
    if model is None:
        raise SystemExit("LLM desligado (LLM_ENABLED=false).")
    with SessionLocal() as s:
        print(generate(s, model, args.topic, args.force))
