"""Seção das histórias no banco (maioria das seções das suas notícias)."""

from collections import defaultdict
from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Article, Story, StoryArticle
from app.topics import majority_topic


def refresh_story_topics(session: Session, story_ids: Iterable[int]) -> None:
    ids = [i for i in set(story_ids) if i is not None]
    if not ids:
        return
    rows = session.execute(
        select(StoryArticle.story_id, Article.topic)
        .join(Article, Article.id == StoryArticle.article_id)
        .where(StoryArticle.story_id.in_(ids))
        .order_by(StoryArticle.story_id, func.coalesce(Article.published_at, Article.first_seen_at))
    ).all()
    topics: dict[int, list[str]] = defaultdict(list)
    for story_id, topic in rows:
        topics[story_id].append(topic)
    for story in session.scalars(select(Story).where(Story.id.in_(ids))):
        story.topic = majority_topic(topics.get(story.id, []))
