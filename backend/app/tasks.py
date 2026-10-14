"""Jobs executados pelo worker (RQ).

Fluxo: scheduler -> collect_all_job -> (ao terminar) process_articles_job.
Cada job tem seu lock no Redis, então disparos repetidos não rodam em paralelo.
"""

import logging
from contextlib import contextmanager

from redis import Redis
from redis.exceptions import LockError
from rq import Queue

from app.config import get_settings
from app.db import SessionLocal
from app.db_check import ensure_schema_current

log = logging.getLogger(__name__)

LOCK_TIMEOUT_SECONDS = 20 * 60


def _redis() -> Redis:
    return Redis.from_url(get_settings().redis_url)


@contextmanager
def _single_run(redis: Redis, name: str):
    lock = redis.lock(f"lock:{name}", timeout=LOCK_TIMEOUT_SECONDS, blocking=False)
    acquired = lock.acquire()
    try:
        yield acquired
    finally:
        if acquired:
            try:
                lock.release()
            except LockError:
                log.warning("lock %s expirou antes do fim", name)


def collect_all_job() -> dict:
    """Coleta todos os veículos ativos e, no fim, enfileira o processamento."""
    from app.ingestion.collector import collect_all

    ensure_schema_current()
    redis = _redis()
    with _single_run(redis, "collect-all") as acquired:
        if not acquired:
            log.info("coleta já em andamento; ignorando")
            return {"skipped": True}
        with SessionLocal() as session:
            runs = collect_all(session)
            result = {
                "skipped": False,
                "runs": [
                    {"outlet_id": r.outlet_id, "status": r.status, "inserted": r.records_inserted}
                    for r in runs
                ],
            }
    Queue("default", connection=redis).enqueue("app.tasks.process_articles_job", job_timeout=30 * 60)
    return result


def process_articles_job() -> dict:
    """Deduplica, gera embeddings e agrupa as notícias novas."""
    from app.clustering.embeddings import get_embedder
    from app.clustering.pipeline import process_new_articles

    ensure_schema_current()
    with _single_run(_redis(), "process-articles") as acquired:
        if not acquired:
            log.info("processamento já em andamento; ignorando")
            return {"skipped": True}
        embedder = get_embedder()
        totals: dict[str, int] = {}
        error = None
        with SessionLocal() as session:
            while True:
                stats = process_new_articles(session, embedder)
                if stats.processed == 0:
                    break
                for k, v in vars(stats).items():
                    if isinstance(v, int):
                        totals[k] = totals.get(k, 0) + v
                error = stats.embedding_error or error
    Queue("default", connection=_redis()).enqueue("app.tasks.framing_job", job_timeout=60 * 60)
    return {"skipped": False, **totals, "embedding_error": error}


def framing_job() -> dict:
    """Análise de enquadramento: regras para tudo, LLM local para histórias com 2+ veículos."""
    from app.framing.llm import get_llm
    from app.framing.pipeline import analyze_framing

    ensure_schema_current()
    with _single_run(_redis(), "framing") as acquired:
        if not acquired:
            return {"skipped": True}
        with SessionLocal() as session:
            result = vars(analyze_framing(session, get_llm()))
    Queue("default", connection=_redis()).enqueue("app.tasks.briefing_job", job_timeout=60 * 60)
    return result


def briefing_job(force: bool = False) -> dict:
    """Resumo por seção (IA local). Só regera seções cujas histórias mudaram."""
    from app.briefing.pipeline import generate
    from app.framing.llm import get_llm

    ensure_schema_current()
    model = get_llm()
    if model is None:
        return {"skipped": True, "reason": "LLM desligado"}
    with _single_run(_redis(), "briefing") as acquired:
        if not acquired:
            return {"skipped": True}
        with SessionLocal() as session:
            return vars(generate(session, model, force=force))


def investigate_job(investigation_id: int) -> dict:
    """Checagem de fatos de um texto ou notícia (fase 6)."""
    from app.factcheck.pipeline import run_investigation
    from app.framing.llm import get_llm

    ensure_schema_current()
    with SessionLocal() as session:
        inv = run_investigation(session, investigation_id, get_llm())
        return {"investigation_id": inv.id, "status": inv.status, "error": inv.error}


def recheck_job(claim_id: int) -> dict:
    """Refaz a checagem de uma afirmação, criando uma nova versão (a anterior fica no histórico)."""
    from app.factcheck.pipeline import recheck
    from app.framing.llm import get_llm

    ensure_schema_current()
    with SessionLocal() as session:
        fc = recheck(session, claim_id, get_llm())
        return {"claim_id": claim_id, "fact_check_id": fc.id, "assessment": fc.assessment}
