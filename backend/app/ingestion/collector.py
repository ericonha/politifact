"""Coleta de um veículo: baixa os feeds, normaliza e grava, registrando a execução.

Idempotente: rodar duas vezes seguidas não duplica artigos (chave = URL canônica)
e nunca altera first_seen_at de um artigo já conhecido.
"""

import logging
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.ingestion.fetch import fetch
from app.ingestion.normalize import canonical_url, content_hash, sanitize_published_at
from app.ingestion.rss import FeedEntry, parse_feed
from app.models import Article, CollectionRun, Outlet

log = logging.getLogger(__name__)

PROVIDER = "rss"
MAX_ERROR_CHARS = 2000

Fetcher = Callable[[str], bytes]


def short_error(exc: BaseException, limit: int = 200) -> str:
    """Tipo + primeira linha da mensagem (erros do SQLAlchemy trazem o SQL inteiro)."""
    first = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
    text = f"{type(exc).__name__}: {first}" if first else type(exc).__name__
    return text[:limit]


def _store_entry(session: Session, outlet: Outlet, entry: FeedEntry, now: datetime) -> bool:
    """Grava um item. Retorna True se for um artigo novo."""
    url = canonical_url(entry.link)
    published = sanitize_published_at(entry.published_at, now)
    stmt = (
        insert(Article)
        .values(
            outlet_id=outlet.id,
            canonical_url=url,
            original_url=entry.link,
            feed_guid=entry.guid,
            headline=entry.title,
            summary=entry.summary,
            published_at=published,
            updated_at=entry.updated_at,
            first_seen_at=now,
            collected_at=now,
            language=outlet.language,
            content_hash=content_hash(entry.title, entry.summary),
            content_reference=entry.link,
            collection_provider=PROVIDER,
            processing_status="new",
        )
        .on_conflict_do_nothing(index_elements=["canonical_url"])
        .returning(Article.id)
    )
    if session.execute(stmt).scalar_one_or_none() is not None:
        return True

    # Já existia: só registra que o veículo atualizou a matéria.
    if entry.updated_at is not None:
        session.execute(
            update(Article)
            .where(
                Article.canonical_url == url,
                or_(Article.updated_at.is_(None), Article.updated_at < entry.updated_at),
            )
            .values(updated_at=entry.updated_at, collected_at=now)
        )
    return False


def collect_outlet(
    session: Session,
    outlet: Outlet,
    fetcher: Fetcher = fetch,
    now: datetime | None = None,
) -> CollectionRun:
    now = now or datetime.now(UTC)
    run = CollectionRun(provider=PROVIDER, outlet_id=outlet.id, started_at=now, status="running")
    session.add(run)
    session.commit()

    errors: list[str] = []
    item_errors: Counter[str] = Counter()
    feeds_ok = 0
    discovered = inserted = failed = 0

    if not outlet.feed_urls:
        errors.append("nenhum feed configurado")

    for feed_url in outlet.feed_urls:
        try:
            entries = parse_feed(fetcher(feed_url))
        except Exception as exc:  # noqa: BLE001  (falha de um feed não derruba os outros)
            log.warning("%s: %s", feed_url, exc)
            errors.append(f"{feed_url}: {short_error(exc)}")
            continue

        feeds_ok += 1
        discovered += len(entries)
        for entry in entries:
            try:
                with session.begin_nested():
                    if _store_entry(session, outlet, entry, now):
                        inserted += 1
            except Exception as exc:  # noqa: BLE001
                failed += 1
                log.warning("item %s: %s", entry.link, short_error(exc))
                item_errors[short_error(exc)] += 1
        session.commit()

    # Agrupa erros iguais: "60 itens: UndefinedColumn ..." em vez de 60 linhas.
    for message, count in item_errors.most_common(5):
        errors.append(f"{count} {'item' if count == 1 else 'itens'}: {message}")

    if not errors:
        status = "success"
    elif feeds_ok:
        status = "partial"
    else:
        status = "failed"

    run.finished_at = datetime.now(UTC)
    run.records_discovered = discovered
    run.records_inserted = inserted
    run.records_failed = failed
    run.status = status
    run.error_summary = "\n".join(errors)[:MAX_ERROR_CHARS] or None
    session.commit()
    log.info(
        "%s: %s (descobertos=%d, novos=%d, falhas=%d)",
        outlet.slug, status, discovered, inserted, failed,
    )
    return run


def collect_all(session: Session, fetcher: Fetcher = fetch) -> list[CollectionRun]:
    outlets = session.scalars(select(Outlet).where(Outlet.active.is_(True)).order_by(Outlet.id)).all()
    return [collect_outlet(session, outlet, fetcher) for outlet in outlets]


if __name__ == "__main__":
    from app.db import SessionLocal
    from app.db_check import ensure_schema_current

    ensure_schema_current()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    with SessionLocal() as s:
        for r in collect_all(s):
            print(f"veículo {r.outlet_id}: {r.status} — {r.records_inserted} novos de {r.records_discovered}")
            if r.error_summary:
                print("   ", r.error_summary.replace("\n", "\n    "))
