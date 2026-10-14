"""Medidas de viés com banco (precisa do Postgres do compose; sem rede).

Cenário controlado, num grupo próprio ("teste-xxxx") para não misturar com os veículos reais:
5 veículos; 12 histórias cobertas por A, B, C e D (A sempre primeiro, D sempre último); E não cobre nenhuma.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.coverage.bias import outlet_bias
from app.coverage.bias_math import classify_change
from app.coverage.metrics import resolve_range
from app.db import SessionLocal
from app.main import app
from app.models import Article, ArticleRevision, Outlet, Story, StoryArticle

OFFSETS = {"A": 0, "B": 30, "C": 90, "D": 120}  # minutos depois do primeiro


@pytest.fixture
def scenario():
    group = f"teste-{uuid.uuid4().hex[:8]}"
    now = datetime.now(UTC)
    base = now - timedelta(days=2)
    outlets: dict[str, int] = {}
    story_ids: list[int] = []
    article_ids: dict[tuple[str, int], int] = {}
    with SessionLocal() as s:
        for name in "ABCDE":
            o = Outlet(slug=f"{group}-{name.lower()}", name=f"Veículo {name}",
                       canonical_domain=f"{group}-{name.lower()}.example",
                       country="BR", language="pt-BR", feed_urls=[], outlet_group=group)
            s.add(o)
            s.flush()
            outlets[name] = o.id
        for i in range(12):
            t0 = base + timedelta(hours=i)
            st = Story(title=f"História {i}", topic="politica", first_observed_at=t0, last_observed_at=t0)
            s.add(st)
            s.flush()
            story_ids.append(st.id)
            for name, off in OFFSETS.items():
                a = Article(
                    outlet_id=outlets[name], canonical_url=f"https://{group}.example/{name}/{i}",
                    original_url=f"https://{group}.example/{name}/{i}", headline=f"Manchete {name} {i}",
                    published_at=t0 + timedelta(minutes=off), collection_provider="test", topic="politica",
                )
                s.add(a)
                s.flush()
                article_ids[(name, i)] = a.id
                s.add(StoryArticle(story_id=st.id, article_id=a.id, assignment_method="test"))
        s.commit()
    yield {"group": group, "outlets": outlets, "stories": story_ids, "articles": article_ids, "now": now}
    with SessionLocal() as s:
        ids = list(article_ids.values())
        s.execute(delete(ArticleRevision).where(ArticleRevision.article_id.in_(ids)))
        s.execute(delete(StoryArticle).where(StoryArticle.article_id.in_(ids)))
        s.execute(delete(Article).where(Article.id.in_(ids)))
        s.execute(delete(Story).where(Story.id.in_(story_ids)))
        s.execute(delete(Outlet).where(Outlet.id.in_(outlets.values())))
        s.commit()


def _bias(name: str, sc: dict) -> dict:
    with SessionLocal() as s:
        o = s.get(Outlet, sc["outlets"][name])
        return outlet_bias(s, o, resolve_range("7d", None, None, sc["now"]), sc["now"])


def test_omissions_for_an_outlet_that_covers_nothing(scenario) -> None:
    b = _bias("E", scenario)
    om = b["omissions"]
    assert om["eligible_stories"] == 12 and om["missed"] == 12 and om["omission_rate"] == 1.0
    assert om["blind_spots"] and om["blind_spots"][0]["outlets_count"] == 4
    assert om["by_topic"][0]["topic"] == "politica" and om["by_topic"][0]["omission_rate"] == 1.0
    assert b["peers"]["count"] == 4


def test_covering_outlet_has_no_omissions_and_delay_matches(scenario) -> None:
    a, d = _bias("A", scenario), _bias("D", scenario)
    assert a["omissions"]["missed"] == 0
    assert a["delay"]["median_minutes"] == 0 and a["delay"]["first_share"] == 1.0
    assert d["delay"]["median_minutes"] == 120 and d["delay"]["first_share"] == 0.0
    assert d["delay"]["stories"] == 12 and d["delay"]["enough"]


def test_vocabulary_refuses_small_sample_but_has_the_shape(scenario) -> None:
    v = _bias("A", scenario)["vocabulary"]
    assert v["enough"] is False and v["uses_more"] == [] and v["language"] == "pt-BR"


def test_edits_are_counted_and_listed(scenario) -> None:
    aid = scenario["articles"][("B", 0)]
    change = classify_change("Manchete B 0", None, "Manchete B 0 não confirma pacote de R$ 10 bilhões", None)
    with SessionLocal() as s:
        s.add(ArticleRevision(article_id=aid, headline="Manchete B 0 não confirma pacote de R$ 10 bilhões",
                              summary=None, content_hash="h" * 64, change=change))
        s.commit()
    e = _bias("B", scenario)["edits"]
    assert e["articles"] == 12 and e["edited"] == 1 and e["meaning_flagged"] == 1
    assert e["examples"][0]["original_headline"] == "Manchete B 0"
    assert e["examples"][0]["new_headline"].startswith("Manchete B 0 não confirma")
    # o original continua intacto no artigo
    with SessionLocal() as s:
        assert s.scalar(select(Article.headline).where(Article.id == aid)) == "Manchete B 0"
    assert _bias("A", scenario)["edits"]["edited"] == 0


def test_bias_endpoint(scenario) -> None:
    client = TestClient(app)
    r = client.get(f"/api/outlets/{scenario['outlets']['A']}/bias?window=7d")
    assert r.status_code == 200, r.text
    assert {"omissions", "delay", "vocabulary", "edits", "peers", "range"} <= r.json().keys()
    assert client.get("/api/outlets/999999999/bias").status_code == 404
    assert client.get(f"/api/outlets/{scenario['outlets']['A']}/bias?window=1y").status_code == 422
