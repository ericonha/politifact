"""Processa notícias novas: deduplicação -> embeddings -> agrupamento em histórias.

Roda depois de cada coleta (job encadeado em app.tasks). Idempotente: só
mexe em artigos com processing_status = "new".
"""

import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clustering.core import (
    ALGORITHM_VERSION,
    DedupCandidate,
    Features,
    Params,
    StoryState,
    decide,
    find_duplicate,
    headline_tokens,
    make_features,
)
from app.clustering.embeddings import Embedder, EmbeddingError, article_text
from app.models import Article, ClusteringDecision, Story, StoryArticle

log = logging.getLogger(__name__)

DEDUP_LOOKBACK = timedelta(hours=72)
EMBED_BATCH = 32


@dataclass
class ProcessStats:
    processed: int = 0
    duplicates: int = 0
    assigned: int = 0
    new_stories: int = 0
    ambiguous: int = 0
    embedded: int = 0
    embedding_error: str | None = None


def article_time(a: Article) -> datetime:
    """Momento usado para ordenar e comparar no agrupamento.

    Usa a data de publicação; se o feed não informou, usa a de descoberta só
    para o agrupamento (as janelas de cobertura continuam ignorando o artigo).
    """
    return a.published_at or a.first_seen_at


def _features(a: Article) -> Features:
    emb = list(a.embedding) if a.embedding is not None else None
    return make_features(a.id, a.outlet_id, article_time(a), a.headline, a.summary, emb)


def _dedup_candidate(a: Article) -> DedupCandidate:
    return DedupCandidate(a.id, a.outlet_id, article_time(a), a.content_hash, headline_tokens(a.headline))


def _embed(articles: list[Article], embedder: Embedder, stats: ProcessStats) -> None:
    todo = [a for a in articles if a.embedding is None or a.embedding_model != embedder.model]
    for i in range(0, len(todo), EMBED_BATCH):
        batch = todo[i : i + EMBED_BATCH]
        try:
            vectors = embedder.embed([article_text(a.headline, a.summary) for a in batch])
        except EmbeddingError as exc:
            # Segue sem embeddings: o agrupamento cai para léxico + entidades.
            stats.embedding_error = str(exc)
            log.warning("embeddings indisponíveis, seguindo sem: %s", exc)
            return
        for a, v in zip(batch, vectors, strict=True):
            a.embedding = v
            a.embedding_model = embedder.model
            stats.embedded += 1


def _load_story_states(session: Session, since: datetime) -> dict[int, StoryState]:
    rows = session.execute(
        select(StoryArticle.story_id, Article)
        .join(Article, Article.id == StoryArticle.article_id)
        .join(Story, Story.id == StoryArticle.story_id)
        .where(Story.last_observed_at >= since, Article.duplicate_of_id.is_(None))
    ).all()
    states: dict[int, StoryState] = {}
    for story_id, article in rows:
        states.setdefault(story_id, StoryState(story_id)).members.append(_features(article))
    return states


def _touch_story(story: Story, t: datetime) -> None:
    if story.first_observed_at is None or t < story.first_observed_at:
        story.first_observed_at = t
    if story.last_observed_at is None or t > story.last_observed_at:
        story.last_observed_at = t


def process_new_articles(
    session: Session,
    embedder: Embedder | None,
    params: Params | None = None,
    limit: int = 1000,
    only_ids: list[int] | None = None,
) -> ProcessStats:
    """Processa até `limit` artigos novos. `only_ids` restringe a artigos específicos (testes)."""
    params = params or Params()
    stats = ProcessStats()
    details = {"params": asdict(params)}

    query = select(Article).where(Article.processing_status == "new")
    if only_ids is not None:
        query = query.where(Article.id.in_(only_ids))
    new = session.scalars(
        query.order_by(func.coalesce(Article.published_at, Article.first_seen_at), Article.id).limit(limit)
    ).all()
    if not new:
        return stats

    earliest = min(article_time(a) for a in new)

    # 1) Deduplicação, em ordem: um artigo pode ser duplicata de outro do mesmo lote.
    pool = [
        _dedup_candidate(a)
        for a in session.scalars(
            select(Article).where(
                func.coalesce(Article.published_at, Article.first_seen_at) >= earliest - DEDUP_LOOKBACK,
                Article.processing_status != "new",
                Article.duplicate_of_id.is_(None),
            )
        )
    ]
    originals: list[Article] = []
    duplicates: list[tuple[Article, int, str]] = []
    for a in new:
        cand = _dedup_candidate(a)
        hit = find_duplicate(cand, pool)
        if hit is None:
            originals.append(a)
            pool.append(cand)
        else:
            duplicates.append((a, *hit))

    # 2) Embeddings só para os originais.
    if embedder is not None:
        _embed(originals, embedder, stats)
    session.flush()

    # 3) Agrupamento incremental.
    states = _load_story_states(session, earliest - timedelta(hours=params.story_window_hours))
    stories_by_id: dict[int, Story] = {}

    def story(sid: int) -> Story:
        if sid not in stories_by_id:
            stories_by_id[sid] = session.get(Story, sid)  # type: ignore[assignment]
        return stories_by_id[sid]

    story_of_article: dict[int, int] = {}

    for a in originals:
        f = _features(a)
        d = decide(f, list(states.values()), params)
        t = article_time(a)

        if d.kind == "assigned":
            session.add(StoryArticle(story_id=d.story_id, article_id=a.id,
                                     cluster_confidence=d.score, assignment_method="auto"))
            _touch_story(story(d.story_id), t)  # type: ignore[arg-type]
            states[d.story_id].members.append(f)  # type: ignore[index]
            story_of_article[a.id] = d.story_id  # type: ignore[assignment]
            a.processing_status = "processed"
            stats.assigned += 1
            decision_story, candidate = d.story_id, None
        elif d.kind == "new_story":
            s = Story(title=a.headline, first_observed_at=t, last_observed_at=t)
            session.add(s)
            session.flush()
            stories_by_id[s.id] = s
            session.add(StoryArticle(story_id=s.id, article_id=a.id,
                                     cluster_confidence=None, assignment_method="seed"))
            states[s.id] = StoryState(s.id, [f])
            story_of_article[a.id] = s.id
            a.processing_status = "processed"
            stats.new_stories += 1
            decision_story, candidate = s.id, d.story_id
        else:  # ambiguous: fica fora de qualquer história até alguém revisar
            a.processing_status = "needs_review"
            stats.ambiguous += 1
            decision_story, candidate = None, d.story_id

        session.add(ClusteringDecision(
            article_id=a.id, story_id=decision_story, candidate_story_id=candidate,
            decision=d.kind, score=d.score, algorithm_version=ALGORITHM_VERSION, details=details,
        ))
        stats.processed += 1

    # 4) Duplicatas: republicação de outro veículo entra na história do original
    #    (o veículo publicou, então conta na cobertura); duplicata do mesmo veículo não.
    outlet_of = {a.id: a.outlet_id for a in new}
    for a, original_id, method in duplicates:
        a.duplicate_of_id = original_id
        a.duplicate_method = method
        a.processing_status = "duplicate"
        original_outlet = outlet_of.get(original_id) or session.get(Article, original_id).outlet_id  # type: ignore[union-attr]
        target = story_of_article.get(original_id) or session.scalar(
            select(StoryArticle.story_id).where(StoryArticle.article_id == original_id)
        )
        linked = None
        if target is not None and original_outlet != a.outlet_id:
            session.add(StoryArticle(story_id=target, article_id=a.id,
                                     cluster_confidence=1.0, assignment_method="syndicated"))
            _touch_story(story(target), article_time(a))
            linked = target
        session.add(ClusteringDecision(
            article_id=a.id, story_id=linked, candidate_story_id=None, decision="duplicate",
            score=None, algorithm_version=ALGORITHM_VERSION,
            details={"duplicate_of": original_id, "method": method},
        ))
        stats.duplicates += 1
        stats.processed += 1

    session.commit()
    log.info("processamento: %s", stats)
    return stats


def reset_clustering(session: Session) -> None:
    """Apaga histórias, vínculos e decisões e devolve todos os artigos para "new".

    Ferramenta de desenvolvimento para reprocessar após mudar parâmetros.
    Destrói o histórico de agrupamento (inclusive correções manuais).
    """
    session.execute(ClusteringDecision.__table__.delete())
    session.execute(StoryArticle.__table__.delete())
    session.execute(Story.__table__.delete())
    session.execute(
        Article.__table__.update().values(
            processing_status="new", duplicate_of_id=None, duplicate_method=None
        )
    )
    session.commit()


if __name__ == "__main__":
    import argparse

    from app.clustering.embeddings import get_embedder
    from app.db import SessionLocal

    parser = argparse.ArgumentParser(description="Deduplica e agrupa notícias novas.")
    parser.add_argument("--reset", action="store_true",
                        help="apaga TODAS as histórias e decisões e reprocessa do zero")
    parser.add_argument("--yes", action="store_true", help="confirma o --reset")
    parser.add_argument("--no-embeddings", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    with SessionLocal() as s:
        if args.reset:
            if not args.yes:
                parser.error("--reset apaga o histórico de agrupamento; repita com --yes para confirmar")
            reset_clustering(s)
            print("Agrupamento zerado.")
        embedder = None if args.no_embeddings else get_embedder()
        total = ProcessStats()
        while True:
            st = process_new_articles(s, embedder)
            if st.processed == 0:
                break
            for k in ("processed", "duplicates", "assigned", "new_stories", "ambiguous", "embedded"):
                setattr(total, k, getattr(total, k) + getattr(st, k))
            total.embedding_error = st.embedding_error or total.embedding_error
        print(total)
