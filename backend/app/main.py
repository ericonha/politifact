from datetime import UTC, date, datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.models import Article, ClusteringDecision, CollectionRun, Outlet, Story, StoryArticle
from app.schemas import (
    ArticleOut,
    CollectionRunOut,
    EnqueuedOut,
    HealthOut,
    OutletCoverage,
    OutletOut,
    ReviewActionIn,
    ReviewActionOut,
    ReviewItemOut,
    StoryArticleOut,
    StoryDetailOut,
    StoryOut,
    TopicOut,
)

app = FastAPI(title="PolitiFact BR", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

WINDOWS = {"24h": timedelta(hours=24), "3d": timedelta(days=3), "7d": timedelta(days=7)}


@app.get("/api/health", response_model=HealthOut)
def health(session: Session = Depends(get_session)) -> HealthOut:
    """status = "degraded" se o banco estiver fora ou com migração pendente."""
    from app.db_check import schema_status

    try:
        session.execute(text("SELECT 1"))
        current, head = schema_status()
    except Exception:
        return HealthOut(status="degraded", database="unavailable")
    db = "ok" if current == head else "migration_pending"
    return HealthOut(
        status="ok" if db == "ok" else "degraded",
        database=db,
        schema_revision=current,
        schema_head=head,
    )


@app.get("/api/outlets", response_model=list[OutletOut])
def list_outlets(session: Session = Depends(get_session)) -> list[Outlet]:
    return list(session.scalars(select(Outlet).order_by(Outlet.name)))


@app.get("/api/outlets/{outlet_id}", response_model=OutletOut)
def get_outlet(outlet_id: int, session: Session = Depends(get_session)) -> Outlet:
    outlet = session.get(Outlet, outlet_id)
    if outlet is None:
        raise HTTPException(404, "Veículo não encontrado")
    return outlet


@app.get("/api/stories", response_model=list[StoryOut])
def list_stories(
    window: str = Query("24h", pattern="^(24h|3d|7d)$"),
    topic: str | None = None,
    session: Session = Depends(get_session),
) -> list[StoryOut]:
    """Histórias com artigos publicados na janela (pela data de publicação, não de descoberta).

    A contagem é sempre "entre os veículos monitorados", nunca cobertura total da mídia.
    """
    since = datetime.now(UTC) - WINDOWS[window]
    rows = session.execute(
        select(
            StoryArticle.story_id,
            Outlet.id,
            Outlet.name,
            func.count(func.distinct(Article.id)),
        )
        .join(Article, Article.id == StoryArticle.article_id)
        .join(Outlet, Outlet.id == Article.outlet_id)
        .where(Article.published_at >= since)
        .group_by(StoryArticle.story_id, Outlet.id, Outlet.name)
    ).all()

    coverage: dict[int, list[OutletCoverage]] = {}
    for story_id, outlet_id, outlet_name, count in rows:
        coverage.setdefault(story_id, []).append(
            OutletCoverage(outlet_id=outlet_id, outlet_name=outlet_name, article_count=count)
        )
    if not coverage:
        return []

    story_q = select(Story).where(Story.id.in_(coverage))
    if topic:
        story_q = story_q.where(Story.topic == topic)
    stories = session.scalars(story_q).all()
    result = [
        StoryOut.model_validate(s).model_copy(
            update={
                "coverage": sorted(coverage[s.id], key=lambda c: c.outlet_name),
                "article_count": sum(c.article_count for c in coverage[s.id]),
                "outlet_count": len(coverage[s.id]),
            }
        )
        for s in stories
    ]
    epoch = datetime.min.replace(tzinfo=UTC)
    result.sort(key=lambda s: (s.outlet_count, s.last_observed_at or epoch), reverse=True)
    return result


@app.get("/api/stories/{story_id}/articles", response_model=list[ArticleOut])
def story_articles(story_id: int, session: Session = Depends(get_session)) -> list[Article]:
    if session.get(Story, story_id) is None:
        raise HTTPException(404, "História não encontrada")
    stmt = (
        select(Article)
        .join(StoryArticle, StoryArticle.article_id == Article.id)
        .where(StoryArticle.story_id == story_id)
        .order_by(Article.published_at)
    )
    return list(session.scalars(stmt))


@app.get("/api/articles", response_model=list[ArticleOut])
def list_articles(
    window: str = Query("24h", pattern="^(24h|3d|7d)$"),
    outlet_id: int | None = None,
    topic: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
) -> list[Article]:
    """Artigos mais recentes pela data de publicação.

    Artigos sem data de publicação no feed não aparecem aqui (não usamos a data de
    descoberta no lugar); eles continuam no banco e contam como limitação da coleta.
    """
    since = datetime.now(UTC) - WINDOWS[window]
    stmt = select(Article).where(Article.published_at >= since)
    if outlet_id is not None:
        stmt = stmt.where(Article.outlet_id == outlet_id)
    if topic:
        stmt = stmt.where(Article.topic == topic)
    stmt = stmt.order_by(Article.published_at.desc()).limit(limit)
    return list(session.scalars(stmt))


@app.get("/api/articles/{article_id}", response_model=ArticleOut)
def get_article(article_id: int, session: Session = Depends(get_session)) -> Article:
    article = session.get(Article, article_id)
    if article is None:
        raise HTTPException(404, "Artigo não encontrado")
    return article


@app.get("/api/collection-runs", response_model=list[CollectionRunOut])
def list_collection_runs(
    limit: int = Query(50, ge=1, le=500),
    outlet_id: int | None = None,
    session: Session = Depends(get_session),
) -> list[CollectionRun]:
    stmt = select(CollectionRun)
    if outlet_id is not None:
        stmt = stmt.where(CollectionRun.outlet_id == outlet_id)
    return list(session.scalars(stmt.order_by(CollectionRun.started_at.desc()).limit(limit)))


@app.post("/api/collection-runs", response_model=EnqueuedOut, status_code=202)
def trigger_collection() -> EnqueuedOut:
    """Dispara uma coleta agora. Se outra já estiver rodando, o job termina sem fazer nada."""
    from redis import Redis
    from rq import Queue

    queue = Queue("default", connection=Redis.from_url(get_settings().redis_url))
    job = queue.enqueue("app.tasks.collect_all_job", job_timeout=20 * 60)
    return EnqueuedOut(job_id=job.id)


@app.get("/api/stories/{story_id}", response_model=StoryDetailOut)
def get_story(story_id: int, session: Session = Depends(get_session)) -> StoryDetailOut:
    story = session.get(Story, story_id)
    if story is None:
        raise HTTPException(404, "História não encontrada")
    rows = session.execute(
        select(Article, Outlet.name, StoryArticle.assignment_method, StoryArticle.cluster_confidence)
        .join(StoryArticle, StoryArticle.article_id == Article.id)
        .join(Outlet, Outlet.id == Article.outlet_id)
        .where(StoryArticle.story_id == story_id)
        .order_by(func.coalesce(Article.published_at, Article.first_seen_at))
    ).all()
    articles = [
        StoryArticleOut(
            article_id=a.id, outlet_id=a.outlet_id, outlet_name=name, headline=a.headline,
            summary=a.summary, original_url=a.original_url, published_at=a.published_at,
            assignment_method=method, cluster_confidence=conf,
            topic=a.topic, topic_source=a.topic_source,
        )
        for a, name, method, conf in rows
    ]
    by_outlet: dict[int, OutletCoverage] = {}
    for art in articles:
        c = by_outlet.setdefault(art.outlet_id, OutletCoverage(
            outlet_id=art.outlet_id, outlet_name=art.outlet_name, article_count=0))
        c.article_count += 1
    return StoryDetailOut.model_validate(story).model_copy(update={
        "articles": articles,
        "coverage": sorted(by_outlet.values(), key=lambda c: c.outlet_name),
        "article_count": len(articles),
        "outlet_count": len(by_outlet),
    })


@app.get("/api/review", response_model=list[ReviewItemOut])
def list_review(
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
) -> list[ReviewItemOut]:
    """Notícias que o agrupamento automático não soube onde colocar."""
    candidate = Story.__table__.alias("candidate")
    rows = session.execute(
        select(ClusteringDecision, Article, Outlet.name, candidate.c.title)
        .join(Article, Article.id == ClusteringDecision.article_id)
        .join(Outlet, Outlet.id == Article.outlet_id)
        .outerjoin(candidate, candidate.c.id == ClusteringDecision.candidate_story_id)
        .where(ClusteringDecision.decision == "ambiguous", ClusteringDecision.resolved_at.is_(None))
        .order_by(ClusteringDecision.score.desc())
        .limit(limit)
    ).all()
    return [
        ReviewItemOut(
            decision_id=d.id, score=d.score, decided_at=d.decided_at, article_id=a.id,
            outlet_name=name, headline=a.headline, summary=a.summary, original_url=a.original_url,
            published_at=a.published_at, candidate_story_id=d.candidate_story_id,
            candidate_story_title=title,
        )
        for d, a, name, title in rows
    ]


@app.post("/api/review/{decision_id}", response_model=ReviewActionOut)
def resolve_review(
    decision_id: int,
    body: ReviewActionIn,
    session: Session = Depends(get_session),
) -> ReviewActionOut:
    """Resolve uma decisão ambígua. A decisão original fica guardada e aponta para a correção."""
    original = session.get(ClusteringDecision, decision_id)
    if original is None or original.decision != "ambiguous":
        raise HTTPException(404, "Decisão pendente não encontrada")
    if original.resolved_at is not None:
        raise HTTPException(409, "Essa decisão já foi resolvida")
    article = session.get(Article, original.article_id)
    assert article is not None
    when = article.published_at or article.first_seen_at

    if body.action == "assign":
        if original.candidate_story_id is None:
            raise HTTPException(422, "Não há história candidata para juntar")
        story = session.get(Story, original.candidate_story_id)
        if story is None:
            raise HTTPException(409, "A história candidata não existe mais")
        kind = "manual_assign"
    else:
        story = Story(title=article.headline, first_observed_at=when, last_observed_at=when)
        session.add(story)
        session.flush()
        kind = "manual_new_story"

    session.add(StoryArticle(story_id=story.id, article_id=article.id,
                             cluster_confidence=None, assignment_method="manual"))
    if story.first_observed_at is None or when < story.first_observed_at:
        story.first_observed_at = when
    if story.last_observed_at is None or when > story.last_observed_at:
        story.last_observed_at = when
    article.processing_status = "processed"

    correction = ClusteringDecision(
        article_id=article.id, story_id=story.id, candidate_story_id=original.candidate_story_id,
        decision=kind, score=original.score, algorithm_version="manual",
        details={"resolves": original.id},
    )
    session.add(correction)
    session.flush()
    original.resolved_at = datetime.now(UTC)
    original.resolved_by_id = correction.id
    from app.topics_store import refresh_story_topics

    session.flush()
    refresh_story_topics(session, [story.id])
    session.commit()
    return ReviewActionOut(decision_id=correction.id, story_id=story.id)


@app.post("/api/processing", response_model=EnqueuedOut, status_code=202)
def trigger_processing() -> EnqueuedOut:
    """Dispara o agrupamento das notícias novas agora."""
    from redis import Redis
    from rq import Queue

    queue = Queue("default", connection=Redis.from_url(get_settings().redis_url))
    job = queue.enqueue("app.tasks.process_articles_job", job_timeout=30 * 60)
    return EnqueuedOut(job_id=job.id)


@app.get("/api/coverage")
def coverage(
    window: str | None = Query(None, pattern="^(24h|3d|7d)$"),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    topic: str | None = None,
    group: str | None = Query(None, pattern="^(nacional|internacional)$"),
    session: Session = Depends(get_session),
) -> dict:
    """Painel de cobertura: preset (window) ou intervalo de datas (from/to, horário de SP)."""
    from app.coverage.metrics import RangeError, resolve_range
    from app.coverage.queries import coverage_report

    now = datetime.now(UTC)
    try:
        r = resolve_range(window, date_from, date_to, now)
    except RangeError as exc:
        raise HTTPException(422, str(exc)) from exc
    return coverage_report(session, r, now, topic, group)


@app.get("/api/compare")
def compare(
    ids: list[int] = Query(..., min_length=2, max_length=3),
    session: Session = Depends(get_session),
) -> dict:
    """Compara de 2 a 3 histórias: quem cobriu, quando, e o volume ao longo do tempo."""
    from app.coverage.queries import compare_stories

    unique = list(dict.fromkeys(ids))
    if len(unique) < 2:
        raise HTTPException(422, "Escolha pelo menos 2 histórias diferentes")
    try:
        return compare_stories(session, unique)
    except KeyError as exc:
        raise HTTPException(404, f"Histórias não encontradas: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/topics", response_model=list[TopicOut])
def list_topics(
    window: str = Query("24h", pattern="^(24h|3d|7d)$"),
    session: Session = Depends(get_session),
) -> list[TopicOut]:
    """Seções, na ordem fixa, com o número de notícias publicadas no período."""
    from app.topics import TOPICS

    since = datetime.now(UTC) - WINDOWS[window]
    counts = dict(session.execute(
        select(Article.topic, func.count())
        .where(Article.published_at >= since, Article.duplicate_of_id.is_(None))
        .group_by(Article.topic)
    ).all())
    return [TopicOut(key=k, label=v, article_count=counts.get(k, 0)) for k, v in TOPICS.items()]
