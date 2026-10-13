"""Classifica em seções os artigos que ainda não têm seção e recalcula a das histórias.

Idempotente; roda no serviço `migrate` a cada `docker compose up`.
Com --all, reclassifica tudo (útil depois de mudar as regras em app/topics.py).
"""

import argparse
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Article, Outlet, StoryArticle
from app.topics import classify
from app.topics_store import refresh_story_topics

BATCH = 500


def backfill(session: Session, everything: bool = False) -> Counter[str]:
    sources: Counter[str] = Counter()
    touched_articles: list[int] = []
    foreign = set(session.scalars(select(Outlet.id).where(Outlet.outlet_group == "internacional")))
    query = select(Article).order_by(Article.id)
    if not everything:
        query = query.where(Article.topic.is_(None))
    last_id = 0
    while True:
        batch = session.scalars(query.where(Article.id > last_id).limit(BATCH)).all()
        if not batch:
            break
        for a in batch:
            r = classify(a.original_url, a.feed_categories, a.headline, a.summary,
                         foreign=a.outlet_id in foreign)
            a.topic, a.topic_source = r.topic, r.source
            sources[r.source] += 1
            touched_articles.append(a.id)
        last_id = batch[-1].id
        session.commit()

    if touched_articles:
        story_ids = set(session.scalars(
            select(StoryArticle.story_id).where(StoryArticle.article_id.in_(touched_articles))
        ))
        refresh_story_topics(session, story_ids)
        session.commit()
    return sources


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="reclassifica todos os artigos")
    args = parser.parse_args()
    with SessionLocal() as s:
        result = backfill(s, everything=args.all)
    total = sum(result.values())
    if total:
        detail = ", ".join(f"{k}={v}" for k, v in result.most_common())
        print(f"Seções: {total} artigos classificados ({detail}).")
    else:
        print("Seções: nada a classificar.")
