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
    FavoriteIn,
    CollectionStatusOut,
)

app = FastAPI(title="PolitiFact BR", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

WINDOWS = {"24h": timedelta(hours=24), "3d": timedelta(days=3), "7d": timedelta(days=7)}


def _outlet_filter(session: Session, outlet_id: int | None, favorites: bool) -> set[int] | None:
    """Veículos escolhidos: um veículo, os favoritos, ou None (todos)."""
    if outlet_id is not None:
        return {outlet_id}
    if favorites:
        return set(session.scalars(select(Outlet.id).where(Outlet.favorite.is_(True))))
    return None


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


def stories_in_window(
    session: Session,
    since: datetime,
    topic: str | None = None,
    wanted: set[int] | None = None,
) -> list[StoryOut]:
    """Histórias com notícias publicadas desde `since`, com cobertura por veículo e relevância.

    Ordenadas por relevância (ver app/relevance.py). Usado pela API e pelo resumo da IA.
    """
    from app.relevance import relevance

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
    for row_story_id, row_outlet_id, row_outlet_name, row_count in rows:
        coverage.setdefault(row_story_id, []).append(
            OutletCoverage(outlet_id=row_outlet_id, outlet_name=row_outlet_name, article_count=row_count)
        )
    if wanted is not None:
        # Histórias que pelo menos um dos veículos escolhidos cobriu (a cobertura mostrada continua completa).
        coverage = {sid: c for sid, c in coverage.items() if any(x.outlet_id in wanted for x in c)}
    if not coverage:
        return []

    story_q = select(Story).where(Story.id.in_(coverage))
    if topic:
        story_q = story_q.where(Story.topic == topic)
    stories = session.scalars(story_q).all()
    active = session.scalar(select(func.count()).select_from(Outlet).where(Outlet.active.is_(True))) or 1
    now = datetime.now(UTC)
    result = [
        StoryOut.model_validate(s).model_copy(
            update={
                "coverage": sorted(coverage[s.id], key=lambda c: c.outlet_name),
                "article_count": sum(c.article_count for c in coverage[s.id]),
                "outlet_count": len(coverage[s.id]),
                "relevance": relevance([c.article_count for c in coverage[s.id]], active, s.last_observed_at, now),
            }
        )
        for s in stories
    ]
    result.sort(key=lambda s: s.relevance, reverse=True)
    return result


@app.get("/api/stories", response_model=list[StoryOut])
def list_stories(
    window: str = Query("24h", pattern="^(24h|3d|7d)$"),
    topic: str | None = None,
    outlet_id: int | None = None,
    favorites: bool = False,
    order: str = Query("relevance", pattern="^(relevance|recent|reach)$"),
    session: Session = Depends(get_session),
) -> list[StoryOut]:
    """Histórias com notícias publicadas na janela (pela data de publicação, não de descoberta).

    Ordem: relevance (padrão), recent (atualizada por último) ou reach (mais veículos).
    A contagem é sempre "entre os veículos monitorados", nunca cobertura total da mídia.
    """
    since = datetime.now(UTC) - WINDOWS[window]
    result = stories_in_window(session, since, topic, _outlet_filter(session, outlet_id, favorites))
    epoch = datetime.min.replace(tzinfo=UTC)
    if order == "recent":
        result.sort(key=lambda s: s.last_observed_at or epoch, reverse=True)
    elif order == "reach":
        result.sort(key=lambda s: (s.outlet_count, s.article_count), reverse=True)
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
    favorites: bool = False,
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
    if favorites and outlet_id is None:
        stmt = stmt.where(Article.outlet_id.in_(select(Outlet.id).where(Outlet.favorite.is_(True))))
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
    outlet_id: int | None = None,
    favorites: bool = False,
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
    wanted = _outlet_filter(session, outlet_id, favorites)
    return coverage_report(session, r, now, topic, group, sorted(wanted) if wanted is not None else None)


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


@app.get("/api/stories/{story_id}/framing")
def story_framing(story_id: int, session: Session = Depends(get_session)) -> dict:
    """Manchetes da história lado a lado, com a análise observável e (se houver) a do LLM.

    Usa a versão mais recente de cada tipo de análise. A comparação descreve
    diferenças no texto, nunca intenção ou viés do veículo.
    """
    from app.framing import observable as obs_mod
    from app.framing.compare import compare
    from app.framing.llm import PROMPT_VERSION
    from app.models import ArticleAnalysis

    if session.get(Story, story_id) is None:
        raise HTTPException(404, "História não encontrada")
    rows = session.execute(
        select(Article, Outlet.name, Outlet.language)
        .join(StoryArticle, StoryArticle.article_id == Article.id)
        .join(Outlet, Outlet.id == Article.outlet_id)
        .where(StoryArticle.story_id == story_id)
        .order_by(func.coalesce(Article.published_at, Article.first_seen_at))
    ).all()
    ids = [a.id for a, _, _ in rows]
    analyses: dict[tuple[int, str], ArticleAnalysis] = {}
    if ids:
        for an in session.scalars(
            select(ArticleAnalysis)
            .where(ArticleAnalysis.article_id.in_(ids), ArticleAnalysis.result.is_not(None))
            .order_by(ArticleAnalysis.created_at)
        ):
            analyses[(an.article_id, an.analysis_type)] = an  # a mais recente vence

    items = []
    for a, outlet_name, language in rows:
        obs = analyses.get((a.id, "observable"))
        observable = obs.result if obs else obs_mod.analyze(a.headline, a.summary)
        llm = analyses.get((a.id, "llm"))
        items.append({
            "article_id": a.id,
            "outlet_name": outlet_name,
            "language": language,
            "headline": a.headline,
            "summary": a.summary,
            "original_url": a.original_url,
            "published_at": a.published_at,
            "observable": observable,
            "llm": None if llm is None else {
                **llm.result,
                "validation": llm.validation,
                "model": llm.analysis_model,
                "prompt_version": llm.prompt_version,
                "created_at": llm.created_at,
            },
        })
    return {
        "story_id": story_id,
        "items": items,
        "comparison": compare([{"outlet": i["outlet_name"], "observable": i["observable"]} for i in items]),
        "llm_prompt_version": PROMPT_VERSION,
    }


@app.get("/api/articles/{article_id}/analysis")
def article_analysis(article_id: int, session: Session = Depends(get_session)) -> list[dict]:
    """Todas as análises de uma notícia, em ordem (histórico completo)."""
    from app.models import ArticleAnalysis

    if session.get(Article, article_id) is None:
        raise HTTPException(404, "Artigo não encontrado")
    return [
        {
            "id": an.id, "type": an.analysis_type, "result": an.result, "validation": an.validation,
            "model": an.analysis_model, "prompt_version": an.prompt_version, "created_at": an.created_at,
        }
        for an in session.scalars(
            select(ArticleAnalysis).where(ArticleAnalysis.article_id == article_id).order_by(ArticleAnalysis.created_at)
        )
    ]


@app.get("/api/ratings")
def outlet_ratings(session: Session = Depends(get_session)) -> list[dict]:
    """Avaliações de orientação, sempre com avaliador, metodologia e data (histórico completo)."""
    from app.models import OutletBiasRating
    from app.ratings import LABELS

    return [
        {
            "outlet_id": r.outlet_id, "provider": r.provider, "rating": r.rating,
            "rating_label": LABELS.get(r.rating, r.rating), "methodology_url": r.methodology_url,
            "reference_url": r.reference_url, "assessed_at": r.assessed_at, "valid_from": r.valid_from,
            "valid_until": r.valid_until, "confidence": r.confidence, "notes": r.notes,
        }
        for r in session.scalars(select(OutletBiasRating).order_by(OutletBiasRating.outlet_id,
                                                                     OutletBiasRating.assessed_at))
    ]


@app.post("/api/framing", response_model=EnqueuedOut, status_code=202)
def trigger_framing() -> EnqueuedOut:
    """Dispara a análise de enquadramento agora."""
    from redis import Redis
    from rq import Queue

    queue = Queue("default", connection=Redis.from_url(get_settings().redis_url))
    job = queue.enqueue("app.tasks.framing_job", job_timeout=60 * 60)
    return EnqueuedOut(job_id=job.id)


@app.post("/api/outlets/{outlet_id}/favorite", response_model=OutletOut)
def set_favorite(outlet_id: int, body: FavoriteIn, session: Session = Depends(get_session)) -> Outlet:
    outlet = session.get(Outlet, outlet_id)
    if outlet is None:
        raise HTTPException(404, "Veículo não encontrado")
    outlet.favorite = body.favorite
    session.commit()
    return outlet


@app.get("/api/collection-status", response_model=CollectionStatusOut)
def collection_status(session: Session = Depends(get_session)) -> CollectionStatusOut:
    """Quando foi a última coleta, se há uma rodando e quando vem a próxima."""
    interval = get_settings().collect_interval_minutes
    last_success = session.scalar(
        select(func.max(CollectionRun.finished_at)).where(CollectionRun.status.in_(["success", "partial"]))
    )
    last_run = session.scalars(select(CollectionRun).order_by(CollectionRun.started_at.desc()).limit(1)).first()
    now = datetime.now(UTC)
    running = session.scalar(
        select(func.count()).select_from(CollectionRun).where(
            CollectionRun.status == "running", CollectionRun.started_at >= now - timedelta(minutes=30))
    ) > 0
    # Veículos ativos cuja coleta mais recente falhou.
    latest = (
        select(CollectionRun.outlet_id, func.max(CollectionRun.started_at).label("t"))
        .group_by(CollectionRun.outlet_id).subquery()
    )
    failing = session.scalars(
        select(Outlet.name)
        .join(latest, latest.c.outlet_id == Outlet.id)
        .join(CollectionRun, (CollectionRun.outlet_id == Outlet.id) & (CollectionRun.started_at == latest.c.t))
        .where(Outlet.active.is_(True), CollectionRun.status == "failed")
        .order_by(Outlet.name)
    ).all()
    return CollectionStatusOut(
        last_success_at=last_success,
        last_run_started_at=last_run.started_at if last_run else None,
        last_run_status=last_run.status if last_run else None,
        running=running,
        interval_minutes=interval,
        next_expected_at=(last_run.started_at + timedelta(minutes=interval)) if last_run else None,
        failing_outlets=list(failing),
    )


@app.get("/api/briefings")
def briefings(session: Session = Depends(get_session)) -> list[dict]:
    """Resumo mais recente de cada seção (últimas 24 h), com as histórias citadas em cada ponto."""
    from app.briefing.pipeline import latest
    from app.topics import TOPICS

    items = latest(session)
    ids = {i for b in items for p in (b.result or {}).get("points", []) for i in p["story_ids"]}
    stories = {s.id: s for s in session.scalars(select(Story).where(Story.id.in_(ids)))} if ids else {}
    reach = dict(session.execute(
        select(StoryArticle.story_id, func.count(func.distinct(Article.outlet_id)))
        .join(Article, Article.id == StoryArticle.article_id)
        .where(StoryArticle.story_id.in_(ids)).group_by(StoryArticle.story_id)
    ).all()) if ids else {}
    order = list(TOPICS)
    out = []
    for b in sorted(items, key=lambda b: order.index(b.topic) if b.topic in order else 99):
        out.append({
            "topic": b.topic,
            "label": TOPICS.get(b.topic, b.topic),
            "generated_at": b.generated_at,
            "period_start": b.period_start,
            "period_end": b.period_end,
            "model": b.model,
            "prompt_version": b.prompt_version,
            "story_count": len(b.story_ids),
            "overview": (b.result or {}).get("overview", ""),
            "points": [
                {
                    "text": p["text"],
                    "stories": [
                        {"id": i, "title": stories[i].title if i in stories else f"História {i}",
                         "outlet_count": reach.get(i, 0)}
                        for i in p["story_ids"]
                    ],
                }
                for p in (b.result or {}).get("points", [])
            ],
            "validation": b.validation,
        })
    return out


@app.post("/api/briefings", response_model=EnqueuedOut, status_code=202)
def trigger_briefings(force: bool = False) -> EnqueuedOut:
    """Gera os resumos agora (force=true regera mesmo sem mudança nas histórias)."""
    from redis import Redis
    from rq import Queue

    queue = Queue("default", connection=Redis.from_url(get_settings().redis_url))
    job = queue.enqueue("app.tasks.briefing_job", force=force, job_timeout=60 * 60)
    return EnqueuedOut(job_id=job.id)


@app.get("/api/outlets/{outlet_id}/profile")
def outlet_profile_endpoint(
    outlet_id: int,
    window: str = Query("7d", pattern="^(7d|30d)$"),
    session: Session = Depends(get_session),
) -> dict:
    """Perfil medido do veículo no período, comparado à média dos veículos do mesmo grupo.

    Não é rótulo de orientação política: mede seções, atores nas manchetes, forma
    das manchetes, tom lido pela IA (validado) e exclusividade.
    """
    from app.coverage.metrics import resolve_range
    from app.coverage.profile import outlet_profile

    outlet = session.get(Outlet, outlet_id)
    if outlet is None:
        raise HTTPException(404, "Veículo não encontrado")
    now = datetime.now(UTC)
    return outlet_profile(session, outlet, resolve_range(window, None, None, now), now)


@app.get("/api/outlets/{outlet_id}/bias")
def outlet_bias_endpoint(
    outlet_id: int,
    window: str = Query("7d", pattern="^(7d|30d)$"),
    session: Session = Depends(get_session),
) -> dict:
    """Diferenças observáveis do veículo em relação aos pares: omissões, atraso, vocabulário e edições.

    Não é rótulo de orientação política, e só vale para o que os feeds RSS mostram.
    """
    from app.coverage.bias import outlet_bias
    from app.coverage.metrics import resolve_range

    outlet = session.get(Outlet, outlet_id)
    if outlet is None:
        raise HTTPException(404, "Veículo não encontrado")
    now = datetime.now(UTC)
    return outlet_bias(session, outlet, resolve_range(window, None, None, now), now)


# ---------------------------------------------------------------------------
# Fase 6: checagem de fatos
# ---------------------------------------------------------------------------

def _enqueue(func: str, *args) -> str:
    from redis import Redis
    from rq import Queue

    # Fila própria ("checks"), atendida por worker-checks: um clique do usuário não espera jobs em lote.
    queue = Queue("checks", connection=Redis.from_url(get_settings().redis_url))
    return queue.enqueue(func, *args, job_timeout=10 * 60).id


def _fact_check_dict(fc, evidence) -> dict:
    from app.factcheck.verdict import ASSESSMENTS

    return {
        "id": fc.id, "assessment": fc.assessment, "assessment_label": ASSESSMENTS.get(fc.assessment, fc.assessment),
        "explanation": fc.explanation, "limitations": [x for x in (fc.limitations or "").split("\n") if x],
        "method": fc.method, "model": fc.model_name, "prompt_version": fc.prompt_version,
        "review_status": fc.review_status, "reviewed_at": fc.reviewed_at, "review_note": fc.review_note,
        "created_at": fc.created_at, "supersedes_id": fc.supersedes_id, "details": fc.details,
        "evidence": [
            {"id": e.id, "provider": e.provider, "source_type": e.source_type, "source_url": e.source_url,
             "source_title": e.source_title, "relevant_passage": e.relevant_passage,
             "relationship": e.evidence_relationship, "verification_status": e.verification_status,
             "published_at": e.published_at, "retrieved_at": e.retrieved_at, "data": e.data}
            for e in evidence
        ],
    }


def _claim_dict(session: Session, claim) -> dict:
    """Afirmação + versão atual da checagem + histórico de versões anteriores."""
    from app.factcheck.pipeline import current_fact_check
    from app.models import Evidence, FactCheck

    current = current_fact_check(session, claim.id)
    versions = session.scalars(
        select(FactCheck).where(FactCheck.claim_id == claim.id).order_by(FactCheck.created_at.desc())
    ).all()
    ev_by_fc: dict[int, list] = {}
    for e in session.scalars(select(Evidence).where(Evidence.claim_id == claim.id).order_by(Evidence.id)):
        ev_by_fc.setdefault(e.fact_check_id, []).append(e)
    return {
        "id": claim.id, "text": claim.claim_text, "quote": claim.quote, "type": claim.claim_type,
        "parsed": claim.parsed, "article_id": claim.article_id, "investigation_id": claim.investigation_id,
        "extraction_model": claim.extraction_model, "created_at": claim.created_at,
        "current": _fact_check_dict(current, ev_by_fc.get(current.id, [])) if current else None,
        "history": [
            {"id": v.id, "assessment": v.assessment, "review_status": v.review_status, "created_at": v.created_at,
             "supersedes_id": v.supersedes_id}
            for v in versions if current is None or v.id != current.id
        ],
    }


@app.post("/api/claims", status_code=202)
def submit_claim(body: dict, session: Session = Depends(get_session)) -> dict:
    """Pede uma checagem. Corpo: {"text": "..."} ou {"article_id": 123} ou {"url": "link de notícia coletada"}.

    Responde na hora com o id da investigação; o trabalho roda no worker.
    """
    from app.factcheck.pipeline import article_text
    from app.ingestion.normalize import canonical_url
    from app.models import Investigation

    text_in = (body.get("text") or "").strip() if isinstance(body.get("text"), str) else ""
    article = None
    if body.get("article_id") is not None:
        try:
            article = session.get(Article, int(body["article_id"]))
        except (TypeError, ValueError):
            article = None
        if article is None:
            raise HTTPException(404, "Notícia não encontrada")
    elif isinstance(body.get("url"), str) and body["url"].strip():
        article = session.scalars(
            select(Article).where(Article.canonical_url == canonical_url(body["url"]))
        ).first()
        if article is None:
            raise HTTPException(422, "Esse link não está entre as notícias coletadas. Cole o texto da afirmação.")
    if article is not None:
        text_in = article_text(article)
    if len(text_in) < 10:
        raise HTTPException(422, "Escreva a afirmação (pelo menos 10 caracteres).")
    if len(text_in) > 4000:
        raise HTTPException(422, "Texto longo demais: mande até 4.000 caracteres.")

    inv = Investigation(input_type="article" if article else "text", input_text=text_in,
                        article_id=article.id if article else None, status="queued")
    session.add(inv)
    session.commit()
    job_id = _enqueue("app.tasks.investigate_job", inv.id)
    return {"investigation_id": inv.id, "job_id": job_id}


@app.get("/api/investigations")
def list_investigations(limit: int = Query(30, ge=1, le=200), session: Session = Depends(get_session)) -> list[dict]:
    from app.factcheck.pipeline import current_fact_check
    from app.models import Claim, Investigation

    out = []
    for inv in session.scalars(select(Investigation).order_by(Investigation.created_at.desc()).limit(limit)):
        claims = session.scalars(select(Claim).where(Claim.investigation_id == inv.id).order_by(Claim.id)).all()
        verdicts = []
        for c in claims:
            fc = current_fact_check(session, c.id)
            if fc:
                verdicts.append({"claim_id": c.id, "text": c.claim_text, "assessment": fc.assessment,
                                 "review_status": fc.review_status})
        out.append({"id": inv.id, "input_type": inv.input_type, "input_text": inv.input_text[:300],
                    "status": inv.status, "error": inv.error, "created_at": inv.created_at, "claims": verdicts})
    return out


@app.get("/api/investigations/{investigation_id}")
def get_investigation(investigation_id: int, session: Session = Depends(get_session)) -> dict:
    from app.models import Claim, Investigation

    inv = session.get(Investigation, investigation_id)
    if inv is None:
        raise HTTPException(404, "Investigação não encontrada")
    claims = session.scalars(select(Claim).where(Claim.investigation_id == inv.id).order_by(Claim.id)).all()
    article = session.get(Article, inv.article_id) if inv.article_id else None
    return {
        "id": inv.id, "input_type": inv.input_type, "input_text": inv.input_text, "status": inv.status,
        "error": inv.error, "extraction": inv.extraction, "created_at": inv.created_at,
        "started_at": inv.started_at, "finished_at": inv.finished_at,
        "article": None if article is None else {
            "id": article.id, "headline": article.headline, "original_url": article.original_url,
            "outlet": session.get(Outlet, article.outlet_id).name, "published_at": article.published_at},
        "claims": [_claim_dict(session, c) for c in claims],
    }


@app.get("/api/claims/{claim_id}")
def get_claim(claim_id: int, session: Session = Depends(get_session)) -> dict:
    from app.models import Claim

    claim = session.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(404, "Afirmação não encontrada")
    return _claim_dict(session, claim)


@app.get("/api/claims/{claim_id}/evidence")
def get_claim_evidence(claim_id: int, session: Session = Depends(get_session)) -> list[dict]:
    """Evidências da versão atual da checagem."""
    current = get_claim(claim_id, session)["current"]
    return current["evidence"] if current else []


@app.post("/api/claims/{claim_id}/recheck", status_code=202)
def recheck_claim(claim_id: int, session: Session = Depends(get_session)) -> dict:
    from app.models import Claim

    if session.get(Claim, claim_id) is None:
        raise HTTPException(404, "Afirmação não encontrada")
    return {"job_id": _enqueue("app.tasks.recheck_job", claim_id)}


@app.post("/api/fact-checks/{fact_check_id}/review")
def review_fact_check(fact_check_id: int, body: dict, session: Session = Depends(get_session)) -> dict:
    """Revisão humana: {"decision": "approved" | "rejected", "note": "..."}. Só a versão atual."""
    from app.factcheck.pipeline import current_fact_check
    from app.models import FactCheck

    fc = session.get(FactCheck, fact_check_id)
    if fc is None:
        raise HTTPException(404, "Checagem não encontrada")
    decision = body.get("decision")
    if decision not in ("approved", "rejected"):
        raise HTTPException(422, "decision deve ser approved ou rejected")
    current = current_fact_check(session, fc.claim_id)
    if current is None or current.id != fc.id:
        raise HTTPException(409, "Essa versão já foi substituída; revise a versão atual")
    fc.review_status = decision
    fc.reviewed_at = datetime.now(UTC)
    note = body.get("note")
    fc.review_note = note.strip()[:1000] if isinstance(note, str) and note.strip() else None
    session.commit()
    return {"id": fc.id, "review_status": fc.review_status}
