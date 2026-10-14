"""Resumo por seção com LLM falso (precisa do Postgres do compose)."""

import pytest
from sqlalchemy import delete

from app.briefing import core
from app.briefing.pipeline import collect_inputs, generate
from app.db import SessionLocal
from app.models import Briefing


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    # Não deixa resumos de teste no banco (eles apareceriam na página Resumo).
    with SessionLocal() as s:
        s.execute(delete(Briefing).where(Briefing.model == FakeLLM.model))
        s.commit()


class FakeLLM:
    model = "fake-briefing"

    def __init__(self):
        self.calls = 0

    def complete_json(self, system, user, schema):
        self.calls += 1
        assert "<historias>" in user and "DADO" in system
        first_id = int(user.split("[id ")[1].split("]")[0])
        return {"overview": "", "points": [{"text": "Resumo de teste.", "story_ids": [first_id, 999999999]}]}


def test_generate_is_idempotent_for_same_inputs() -> None:
    llm = FakeLLM()
    with SessionLocal() as s:
        first = generate(s, llm, topics=["politica"])
        calls_after_first = llm.calls
        second = generate(s, llm, topics=["politica"])
    if first.generated:  # só há o que testar se existem histórias de política nas últimas 24 h
        assert second.unchanged == ["politica"]
        assert llm.calls == calls_after_first


def test_collect_inputs_limits_stories() -> None:
    from datetime import UTC, datetime, timedelta

    with SessionLocal() as s:
        inputs = collect_inputs(s, "politica", datetime.now(UTC) - timedelta(hours=24))
    assert len(inputs) <= core.MAX_STORIES
    for i in inputs:
        assert len({o for o, _, _ in i.headlines}) == len(i.headlines)  # uma manchete por veículo
