"""Investigação completa com fontes falsas (precisa do Postgres do compose; sem rede)."""

from datetime import date

import pytest
from sqlalchemy import delete, select

from app.db import SessionLocal
from app.factcheck.pipeline import current_fact_check, recheck, run_investigation
from app.factcheck.sources.bcb import Point, SourceError
from app.models import Claim, Evidence, FactCheck, Investigation

TODAY = date(2026, 10, 13)


def selic_1375(plan):
    return [Point(date(2026, 10, 10), 13.75), Point(date(2026, 11, 2), 13.75)]  # inclui data futura


def no_factchecks(query):
    return []


@pytest.fixture
def created():
    ids: list[int] = []
    yield ids
    with SessionLocal() as s:
        claim_ids = list(s.scalars(select(Claim.id).where(Claim.investigation_id.in_(ids))))
        s.execute(delete(Evidence).where(Evidence.claim_id.in_(claim_ids)))
        s.execute(delete(FactCheck).where(FactCheck.claim_id.in_(claim_ids)))
        s.execute(delete(Claim).where(Claim.id.in_(claim_ids)))
        s.execute(delete(Investigation).where(Investigation.id.in_(ids)))
        s.commit()


def _new(s, text: str, ids: list[int]) -> Investigation:
    inv = Investigation(input_type="text", input_text=text, status="queued")
    s.add(inv)
    s.commit()
    ids.append(inv.id)
    return inv


def test_full_investigation_with_official_data(created) -> None:
    with SessionLocal() as s:
        inv = _new(s, "A Selic está em 13,75% ao ano.", created)
        run_investigation(s, inv.id, None, today=TODAY, bcb_fetch=selic_1375, factcheck_search=no_factchecks)
        s.refresh(inv)
        (claim,) = s.scalars(select(Claim).where(Claim.investigation_id == inv.id)).all()
        fc = current_fact_check(s, claim.id)
        evidence = s.scalars(select(Evidence).where(Evidence.fact_check_id == fc.id)).all()

    assert inv.status == "done" and inv.extraction["method"] == "rules"
    assert fc.assessment == "verdadeiro" and fc.method == "rules" and fc.review_status == "pending_review"
    official = [e for e in evidence if e.source_type == "official_data"]
    assert len(official) == 1 and official[0].evidence_relationship == "supports"
    assert official[0].data["reference_day"] == "2026-10-10"  # data futura ignorada
    assert claim.parsed["indicator"] == "selic"


def test_recheck_creates_new_version_and_keeps_old(created) -> None:
    with SessionLocal() as s:
        inv = _new(s, "A Selic está em 13,75% ao ano.", created)
        run_investigation(s, inv.id, None, today=TODAY, bcb_fetch=selic_1375, factcheck_search=no_factchecks)
        claim = s.scalars(select(Claim).where(Claim.investigation_id == inv.id)).one()
        first = current_fact_check(s, claim.id)

        def selic_changed(plan):
            return [Point(date(2026, 10, 12), 12.75)]

        second = recheck(s, claim.id, None, today=TODAY, bcb_fetch=selic_changed, factcheck_search=no_factchecks)
        versions = s.scalars(select(FactCheck).where(FactCheck.claim_id == claim.id)).all()

    assert second.supersedes_id == first.id
    assert second.assessment == "falso" and first.assessment == "verdadeiro"
    assert len(versions) == 2


def test_source_failure_becomes_no_evidence_with_limitation(created) -> None:
    def down(plan):
        raise SourceError("timeout simulado")

    with SessionLocal() as s:
        inv = _new(s, "A inflação de 2025 foi de 4,26%.", created)
        run_investigation(s, inv.id, None, today=TODAY, bcb_fetch=down, factcheck_search=no_factchecks)
        claim = s.scalars(select(Claim).where(Claim.investigation_id == inv.id)).one()
        fc = current_fact_check(s, claim.id)

    assert fc.assessment == "sem_evidencia"
    assert "Banco Central" in (fc.limitations or "")


def test_run_is_idempotent(created) -> None:
    with SessionLocal() as s:
        inv = _new(s, "A Selic está em 13,75% ao ano.", created)
        for _ in range(2):
            run_investigation(s, inv.id, None, today=TODAY, bcb_fetch=selic_1375, factcheck_search=no_factchecks)
        n = len(s.scalars(select(Claim).where(Claim.investigation_id == inv.id)).all())
    assert n == 1
