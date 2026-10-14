"""Roda uma investigação: afirmações -> evidências -> veredito -> banco.

Versionamento: rechecar uma afirmação cria uma NOVA checagem que aponta para a
anterior (supersedes_id), com as próprias evidências e datas de busca. A versão
atual é a que nenhuma outra substitui. Nada é apagado ou sobrescrito.
"""

import logging
from collections.abc import Callable
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.factcheck import extract as extract_mod
from app.factcheck import verdict as verdict_mod
from app.factcheck.parse import parse
from app.factcheck.sources import EvidenceItem, bcb, factchecks, press
from app.models import Article, Claim, Evidence, FactCheck, Investigation

log = logging.getLogger(__name__)

BcbFetcher = Callable[[bcb.Plan], list[bcb.Point]]
FactCheckSearch = Callable[[str], list[EvidenceItem]]


def current_fact_check(session: Session, claim_id: int) -> FactCheck | None:
    """A versão mais recente: a que nenhuma outra substitui."""
    superseded = select(FactCheck.supersedes_id).where(FactCheck.supersedes_id.is_not(None))
    return session.scalars(
        select(FactCheck).where(FactCheck.claim_id == claim_id, FactCheck.id.not_in(superseded))
        .order_by(FactCheck.created_at.desc()).limit(1)
    ).first()


def check_claim(
    session: Session,
    claim: Claim,
    llm=None,
    *,
    today: date | None = None,
    bcb_fetch: BcbFetcher = bcb.fetch,
    factcheck_search: FactCheckSearch | None = None,
    supersedes: FactCheck | None = None,
) -> FactCheck:
    today = today or datetime.now(UTC).date()
    parsed = parse(claim.claim_text)
    limitations: list[str] = []
    official: EvidenceItem | None = None

    # 1. Dados oficiais (só para tipos de afirmação de fato).
    if parsed.checkable and claim.claim_type not in ("opiniao", "previsao", "pergunta"):
        pl = bcb.plan(parsed, today)
        if isinstance(pl, str):
            limitations.append(f"Checagem automática não aplicada: {pl}.")
        else:
            try:
                official = bcb.to_evidence(parsed, pl, bcb.compare(parsed, pl, bcb_fetch(pl), today))
            except bcb.SourceError as exc:
                limitations.append(f"Não foi possível consultar o Banco Central agora ({exc}). Recheque mais tarde.")

    # 2. Checagens publicadas (opcional).
    published: list[EvidenceItem] = []
    key = get_settings().factcheck_api_key
    search_fc = factcheck_search or (lambda q: factchecks.search(q, key))
    if factcheck_search is None and not key:
        limitations.append("Checagens já publicadas por agências não foram consultadas (sem FACTCHECK_API_KEY).")
    else:
        try:
            published = search_fc(claim.claim_text)
        except factchecks.FactCheckSourceError as exc:
            limitations.append(f"Busca de checagens publicadas falhou: {exc}.")

    # 3. Imprensa: só contexto.
    context = press.search(session, claim.claim_text, exclude_article_id=claim.article_id)

    v = verdict_mod.decide(
        claim.claim_text, claim.claim_type or "fato", parsed, official,
        list(enumerate(published, start=1)), llm, limitations, press=context,
    )

    # A classificação de cada notícia (apoia / contradiz / irrelevante) vira a relação da evidência.
    stances = v.details.get("stances") or {}
    for pos, item in enumerate(context, start=1):
        st = stances.get(pos)
        if st and st["stance"] in ("supports", "contradicts"):
            item.relationship = st["stance"]
            item.data = {**item.data, "stance_quote": st["quote"]}
    context = sorted(context, key=lambda it: it.relationship == "context")  # as que pesam primeiro

    fc = FactCheck(
        claim_id=claim.id, assessment=v.assessment, explanation=v.explanation,
        limitations="\n".join(v.limitations) or None, review_status="pending_review",
        model_name=(v.details.get("model") if v.method in ("llm", "press") else None),
        prompt_version={"llm": verdict_mod.PROMPT_VERSION, "press": verdict_mod.PRESS_PROMPT_VERSION}.get(
            v.method, "rules-v1"),
        method=v.method, details={**v.details, "parsed": parsed.to_dict()},
        supersedes_id=supersedes.id if supersedes else None,
    )
    session.add(fc)
    session.flush()
    for item in ([official] if official else []) + published + context:
        session.add(Evidence(
            claim_id=claim.id, fact_check_id=fc.id, source_url=item.source_url, source_title=item.source_title,
            source_type=item.source_type, relevant_passage=item.relevant_passage,
            evidence_relationship=item.relationship, verification_status=item.verification_status,
            published_at=datetime.combine(item.published_at, datetime.min.time(), UTC) if item.published_at else None,
            provider=item.provider, data=item.data,
        ))
    claim.parsed = parsed.to_dict()
    session.flush()
    return fc


def run_investigation(session: Session, investigation_id: int, llm=None, **check_kwargs) -> Investigation:
    inv = session.get(Investigation, investigation_id)
    if inv is None:
        raise ValueError(f"investigação {investigation_id} não existe")
    if inv.status == "done":
        return inv  # idempotente: rodar de novo o mesmo job não duplica afirmações
    inv.status, inv.started_at, inv.error = "running", datetime.now(UTC), None
    session.commit()
    try:
        claims, info = extract_mod.extract(inv.input_text, llm)
        inv.extraction = info
        source = "article" if inv.article_id else "user"
        for c in claims:
            claim = Claim(
                investigation_id=inv.id, article_id=inv.article_id, claim_text=c.text, claim_type=c.type,
                quote=c.quote, context=inv.input_text[:1000], source=source,
                extraction_model=info.get("model") if c.method == "llm" else "rules",
                extraction_version=info.get("prompt_version") if c.method == "llm" else "rules-v1",
            )
            session.add(claim)
            session.flush()
            check_claim(session, claim, llm, **check_kwargs)
        inv.status = "done"
        if not claims:
            inv.error = "Nenhuma afirmação encontrada no texto."
    except Exception as exc:  # noqa: BLE001  (a investigação registra o erro em vez de sumir)
        session.rollback()
        inv = session.get(Investigation, investigation_id)
        inv.status, inv.error = "failed", f"{type(exc).__name__}: {str(exc)[:500]}"
        log.exception("investigação %s falhou", investigation_id)
    inv.finished_at = datetime.now(UTC)
    session.commit()
    return inv


def recheck(session: Session, claim_id: int, llm=None, **check_kwargs) -> FactCheck:
    claim = session.get(Claim, claim_id)
    if claim is None:
        raise ValueError(f"afirmação {claim_id} não existe")
    fc = check_claim(session, claim, llm, supersedes=current_fact_check(session, claim_id), **check_kwargs)
    session.commit()
    return fc


def article_text(article: Article) -> str:
    return f"{article.headline}. {article.summary or ''}".strip()
