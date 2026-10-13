"""Grava análises de enquadramento no banco.

1. Observável (regras): para toda notícia sem análise na versão atual. Barato.
2. LLM: só para notícias de histórias com 2+ veículos (onde comparar faz sentido),
   das últimas 72 h, limitado por execução (o modelo local é lento).
Nada é sobrescrito: mudar o prompt ou o modelo gera linhas novas.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, exists, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.framing import llm as llm_mod
from app.framing import observable
from app.models import Article, ArticleAnalysis, Outlet, StoryArticle

log = logging.getLogger(__name__)

LLM_LOOKBACK = timedelta(hours=72)
OBS_BATCH = 500


@dataclass
class FramingStats:
    observable: int = 0
    llm_ok: int = 0
    llm_adjusted: int = 0
    llm_rejected: int = 0
    llm_error: str | None = None


def _has(analysis_type: str, version: str, model: str | None = None):
    cond = [
        ArticleAnalysis.article_id == Article.id,
        ArticleAnalysis.analysis_type == analysis_type,
        ArticleAnalysis.prompt_version == version,
    ]
    if model:
        cond.append(ArticleAnalysis.analysis_model == model)
    return exists().where(and_(*cond))


def run_observable(session: Session, stats: FramingStats) -> None:
    while True:
        batch = session.scalars(
            select(Article)
            .where(~_has("observable", observable.VERSION), Article.duplicate_of_id.is_(None))
            .order_by(Article.id)
            .limit(OBS_BATCH)
        ).all()
        if not batch:
            return
        for a in batch:
            r = observable.analyze(a.headline, a.summary)
            session.add(ArticleAnalysis(
                article_id=a.id, analysis_type="observable", result=r,
                entities=[x["name"] for x in r["actors"]], topics=[a.topic] if a.topic else None,
                language_characteristics={k: r[k] for k in ("is_question", "has_exclamation", "has_quote",
                                                              "has_number", "loaded_terms")},
                analysis_model="rules", prompt_version=observable.VERSION,
            ))
            stats.observable += 1
        session.commit()


def run_llm(session: Session, model, stats: FramingStats, limit: int) -> None:
    since = datetime.now(UTC) - LLM_LOOKBACK
    reach = (
        select(StoryArticle.story_id, func.count(func.distinct(Article.outlet_id)).label("n"))
        .join(Article, Article.id == StoryArticle.article_id)
        .group_by(StoryArticle.story_id)
        .subquery()
    )
    rows = session.execute(
        select(Article, Outlet.name)
        .join(Outlet, Outlet.id == Article.outlet_id)
        .join(StoryArticle, StoryArticle.article_id == Article.id)
        .join(reach, reach.c.story_id == StoryArticle.story_id)
        .where(
            reach.c.n >= 2,
            Article.published_at >= since,
            Article.duplicate_of_id.is_(None),
            ~_has("llm", llm_mod.PROMPT_VERSION, model.model),
        )
        .order_by(reach.c.n.desc(), Article.published_at.desc())
        .limit(limit)
    ).all()

    for article, outlet_name in rows:
        try:
            v = llm_mod.analyze(model, outlet_name, article.headline, article.summary)
        except llm_mod.LLMError as exc:
            stats.llm_error = str(exc)
            log.warning("LLM indisponível, parando esta rodada: %s", exc)
            break
        session.add(ArticleAnalysis(
            article_id=article.id, analysis_type="llm", result=v.result, validation=v.validation,
            framing_summary=v.result["angle"] or None, analysis_model=model.model,
            prompt_version=llm_mod.PROMPT_VERSION,
        ))
        session.commit()
        if v.status == "ok":
            stats.llm_ok += 1
        elif v.status == "adjusted":
            stats.llm_adjusted += 1
        else:
            stats.llm_rejected += 1


def analyze_framing(session: Session, model=None, limit: int | None = None) -> FramingStats:
    stats = FramingStats()
    run_observable(session, stats)
    if model is not None:
        run_llm(session, model, stats, limit or get_settings().llm_articles_per_run)
    log.info("enquadramento: %s", stats)
    return stats


if __name__ == "__main__":
    import argparse

    from app.db import SessionLocal
    from app.db_check import ensure_schema_current

    ensure_schema_current()
    parser = argparse.ArgumentParser(description="Analisa o enquadramento das manchetes.")
    parser.add_argument("--no-llm", action="store_true", help="só a análise por regras")
    parser.add_argument("--limit", type=int, help="máximo de notícias analisadas pelo LLM")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    with SessionLocal() as s:
        print(analyze_framing(s, None if args.no_llm else llm_mod.get_llm(), args.limit))
