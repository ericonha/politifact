"""Relatório de cobertura a partir do banco.

Definições (mostradas também na tela, em "Como contamos"):
- Artigo elegível: tem data de publicação dentro do período e não é duplicata
  do mesmo veículo. Republicação de outro veículo conta (o veículo publicou).
- Cobertura de uma história por um veículo: artigos elegíveis desse veículo
  ligados à história, publicados no período.
- Alcance de uma história: número de veículos distintos que a cobriram no período.
- Tudo é "entre os veículos monitorados", nunca cobertura total da mídia.
"""

from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from app.config import get_settings
from app.coverage.metrics import (
    Range,
    choose_bucket,
    collection_gaps,
    covered_fraction,
    exclusive_counts,
    reach_distribution,
    timeline,
)
from app.models import Article, ClusteringDecision, CollectionRun, Outlet, Story, StoryArticle
from app.topics import OTHER, TOPICS

TOP_STORIES = 40
MAX_GAPS_SHOWN = 5


def _eligible_articles(
    session: Session,
    start: datetime,
    end: datetime,
    topic: str | None = None,
    outlet_ids: list[int] | None = None,
):
    """(id, outlet_id, published_at, topic) dos artigos elegíveis no período."""
    original = aliased(Article)
    q = (
        select(Article.id, Article.outlet_id, Article.published_at, Article.topic)
        .outerjoin(original, original.id == Article.duplicate_of_id)
        .where(
            Article.published_at >= start,
            Article.published_at < end,
            or_(Article.duplicate_of_id.is_(None), original.outlet_id != Article.outlet_id),
        )
    )
    if topic:
        q = q.where(Article.topic == topic)
    if outlet_ids is not None:
        q = q.where(Article.outlet_id.in_(outlet_ids))
    return session.execute(q).all()


def topic_matrix(session: Session, start: datetime, end: datetime, outlet_ids: list[int] | None = None) -> list[dict]:
    """Notícias por seção e veículo no período (sem filtro de seção)."""
    counts: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for a in _eligible_articles(session, start, end, outlet_ids=outlet_ids):
        counts[a.topic or OTHER][a.outlet_id] += 1
    order = list(TOPICS)
    return [
        {"topic": t, "label": TOPICS.get(t, t), "by_outlet": dict(counts[t]), "total": sum(counts[t].values())}
        for t in sorted(counts, key=lambda t: order.index(t) if t in order else len(order))
    ]


def coverage_report(
    session: Session,
    r: Range,
    now: datetime,
    topic: str | None = None,
    group: str | None = None,
    outlet_filter: list[int] | None = None,
) -> dict:
    """`group` ("nacional"/"internacional") e `outlet_filter` (ids, ex.: favoritos)
    restringem veículos, notícias e histórias."""
    interval = timedelta(minutes=get_settings().collect_interval_minutes)
    max_gap = 2 * interval

    outlet_q = select(Outlet).order_by(Outlet.name)
    if group:
        outlet_q = outlet_q.where(Outlet.outlet_group == group)
    if outlet_filter is not None:
        outlet_q = outlet_q.where(Outlet.id.in_(outlet_filter))
    outlets = session.scalars(outlet_q).all()
    outlet_ids = [o.id for o in outlets]
    restricted = bool(group) or outlet_filter is not None
    articles = _eligible_articles(session, r.start, r.end, topic, outlet_ids if restricted else None)
    article_ids = [a.id for a in articles]
    outlet_of = {a.id: a.outlet_id for a in articles}

    # Histórias e alcance no período
    links = session.execute(
        select(StoryArticle.story_id, StoryArticle.article_id).where(StoryArticle.article_id.in_(article_ids))
    ).all() if article_ids else []
    story_outlets: dict[int, set[int]] = defaultdict(set)
    story_counts: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for story_id, article_id in links:
        o = outlet_of[article_id]
        story_outlets[story_id].add(o)
        story_counts[story_id][o] += 1

    exclusives = exclusive_counts(story_outlets)
    stories_per_outlet: dict[int, int] = defaultdict(int)
    for outlets_set in story_outlets.values():
        for o in outlets_set:
            stories_per_outlet[o] += 1

    active_ids = {o.id for o in outlets if o.active}
    all_active = sum(1 for s in story_outlets.values() if active_ids and active_ids <= s)

    # Linha do tempo por veículo
    starts, series = timeline(((a.outlet_id, a.published_at) for a in articles), [o.id for o in outlets], r)

    # Coletas: lacunas e possíveis perdas (feed com só notícias novas)
    runs = session.execute(
        select(CollectionRun.outlet_id, CollectionRun.started_at, CollectionRun.status,
               CollectionRun.records_discovered, CollectionRun.records_inserted)
        .where(CollectionRun.started_at >= r.start - max_gap, CollectionRun.started_at < r.end)
        .order_by(CollectionRun.started_at)
    ).all()
    first_run = dict(session.execute(
        select(CollectionRun.outlet_id, func.min(CollectionRun.started_at)).group_by(CollectionRun.outlet_id)
    ).all())
    last_ok = dict(session.execute(
        select(CollectionRun.outlet_id, func.max(CollectionRun.finished_at))
        .where(CollectionRun.status.in_(["success", "partial"]))
        .group_by(CollectionRun.outlet_id)
    ).all())

    ok_times: dict[int, list[datetime]] = defaultdict(list)
    failed_runs: dict[int, int] = defaultdict(int)
    overflow: dict[int, int] = defaultdict(int)
    for outlet_id, started, status, discovered, inserted in runs:
        if status in ("success", "partial"):
            ok_times[outlet_id].append(started)
            if (discovered and inserted == discovered and started != first_run.get(outlet_id)
                    and started >= r.start):
                overflow[outlet_id] += 1
        elif status == "failed" and started >= r.start:
            failed_runs[outlet_id] += 1

    outlet_rows = []
    for o in outlets:
        gaps = collection_gaps(ok_times[o.id], r.start, r.end, max_gap) if o.active else []
        outlet_rows.append({
            "id": o.id,
            "slug": o.slug,
            "name": o.name,
            "group": o.outlet_group,
            "language": o.language,
            "active": o.active,
            "collection_notes": o.collection_notes,
            "article_count": sum(series[o.id]),
            "story_count": stories_per_outlet.get(o.id, 0),
            "exclusive_story_count": exclusives.get(o.id, 0),
            "covered_fraction": covered_fraction(gaps, r.start, r.end) if o.active else None,
            "gap_hours": round(sum(g.hours for g in gaps), 1),
            "gaps": [{"start": g.start, "end": g.end} for g in sorted(gaps, key=lambda g: -g.hours)[:MAX_GAPS_SHOWN]],
            "failed_runs": failed_runs.get(o.id, 0),
            "possible_overflow_runs": overflow.get(o.id, 0),
            "last_success_at": last_ok.get(o.id),
        })

    # Histórias mais cobertas
    ranked = sorted(story_outlets, key=lambda s: (len(story_outlets[s]), sum(story_counts[s].values())),
                    reverse=True)[:TOP_STORIES]
    story_meta = {s.id: s for s in session.scalars(select(Story).where(Story.id.in_(ranked)))} if ranked else {}
    names = {o.id: o.name for o in outlets}
    top_stories = [
        {
            "id": sid,
            "title": story_meta[sid].title,
            "summary": story_meta[sid].summary,
            "topic": story_meta[sid].topic,
            "first_observed_at": story_meta[sid].first_observed_at,
            "last_observed_at": story_meta[sid].last_observed_at,
            "article_count": sum(story_counts[sid].values()),
            "outlet_count": len(story_outlets[sid]),
            "coverage": [
                {"outlet_id": oid, "outlet_name": names[oid], "article_count": n}
                for oid, n in sorted(story_counts[sid].items())
            ],
        }
        for sid in ranked if sid in story_meta
    ]

    # Limitações do período
    in_group = Article.outlet_id.in_(outlet_ids)
    undated = session.scalar(
        select(func.count()).select_from(Article)
        .where(Article.published_at.is_(None), Article.first_seen_at >= r.start, Article.first_seen_at < r.end,
               in_group)
    )
    in_range_q = select(func.count()).select_from(Article).where(
        Article.published_at >= r.start, Article.published_at < r.end, in_group)
    if topic:
        in_range_q = in_range_q.where(Article.topic == topic)
    in_range_total = session.scalar(in_range_q)
    pending_review = session.scalar(
        select(func.count()).select_from(ClusteringDecision)
        .join(Article, Article.id == ClusteringDecision.article_id)
        .where(ClusteringDecision.decision == "ambiguous", ClusteringDecision.resolved_at.is_(None),
               Article.published_at >= r.start, Article.published_at < r.end, in_group)
    )
    not_clustered = len(article_ids) - len({a for _, a in links})

    return {
        "range": {
            "start": r.start, "end": r.end, "label": r.label,
            "bucket_seconds": int(r.bucket.total_seconds()), "generated_at": now,
        },
        "totals": {
            "articles": len(articles),
            "stories": len(story_outlets),
            "stories_all_active_outlets": all_active,
            "active_outlets": len(active_ids),
            "duplicates_excluded": (in_range_total or 0) - len(articles),
            "undated_articles": undated or 0,
            "pending_review": pending_review or 0,
            "not_clustered": not_clustered,
        },
        "outlets": outlet_rows,
        "timeline": {
            "buckets": starts,
            "series": [{"outlet_id": oid, "counts": counts} for oid, counts in series.items()],
        },
        "reach_distribution": [{"outlets": k, "stories": v} for k, v in reach_distribution(story_outlets).items()],
        "top_stories": top_stories,
        "topic": topic,
        "group": group,
        "topics": topic_matrix(session, r.start, r.end, outlet_ids if restricted else None),
        "collection_interval_minutes": int(interval.total_seconds() // 60),
    }


def compare_stories(session: Session, story_ids: list[int]) -> dict:
    """Linha do tempo e cobertura por veículo de até 3 histórias, lado a lado."""
    stories = {s.id: s for s in session.scalars(select(Story).where(Story.id.in_(story_ids)))}
    missing = [i for i in story_ids if i not in stories]
    if missing:
        raise KeyError(missing)

    original = aliased(Article)
    rows = session.execute(
        select(StoryArticle.story_id, Article.id, Article.outlet_id, Outlet.name, Article.published_at,
               Article.headline, Article.original_url, StoryArticle.assignment_method)
        .join(Article, Article.id == StoryArticle.article_id)
        .join(Outlet, Outlet.id == Article.outlet_id)
        .outerjoin(original, original.id == Article.duplicate_of_id)
        .where(
            StoryArticle.story_id.in_(story_ids),
            Article.published_at.is_not(None),
            or_(Article.duplicate_of_id.is_(None), original.outlet_id != Article.outlet_id),
        )
        .order_by(Article.published_at)
    ).all()

    if rows:
        start = min(r.published_at for r in rows)
        end = max(r.published_at for r in rows) + timedelta(seconds=1)
    else:
        start = min((s.first_observed_at for s in stories.values() if s.first_observed_at), default=None)
        if start is None:
            raise ValueError("histórias sem notícias datadas")
        end = start + timedelta(hours=1)
    bucket = choose_bucket(end - start)
    rng = Range(start, max(end, start + bucket), bucket, "")
    starts, series = timeline(((r.story_id, r.published_at) for r in rows), story_ids, rng)

    per_story = []
    for sid in story_ids:
        srows = [r for r in rows if r.story_id == sid]
        by_outlet: dict[int, dict] = {}
        for r in srows:
            entry = by_outlet.setdefault(r.outlet_id, {
                "outlet_id": r.outlet_id, "outlet_name": r.name, "article_count": 0,
                "first_published_at": r.published_at,
            })
            entry["article_count"] += 1
        per_story.append({
            "id": sid,
            "title": stories[sid].title,
            "first_observed_at": stories[sid].first_observed_at,
            "last_observed_at": stories[sid].last_observed_at,
            "article_count": len(srows),
            "outlets": sorted(by_outlet.values(), key=lambda e: e["first_published_at"]),
            "articles": [
                {"article_id": r.id, "outlet_name": r.name, "headline": r.headline,
                 "original_url": r.original_url, "published_at": r.published_at,
                 "assignment_method": r.assignment_method}
                for r in srows
            ],
        })

    return {
        "bucket_seconds": int(bucket.total_seconds()),
        "timeline": {"buckets": starts, "series": [{"story_id": k, "counts": v} for k, v in series.items()]},
        "stories": per_story,
    }
