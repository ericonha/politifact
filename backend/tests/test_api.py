"""Testes de integração: exigem o Postgres do docker compose rodando.

Rodar com:  docker compose run --rm api pytest
"""

from fastapi.testclient import TestClient

from app.main import app
from app.seed import OUTLETS

client = TestClient(app)


def test_health() -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok", body
    assert body["schema_revision"] == body["schema_head"]


def test_outlets_seeded() -> None:
    r = client.get("/api/outlets")
    assert r.status_code == 200
    slugs = {o["slug"] for o in r.json()}
    assert {o["slug"] for o in OUTLETS} <= slugs


def test_stories_rejects_unknown_window() -> None:
    assert client.get("/api/stories?window=1y").status_code == 422


def test_stories_default_window() -> None:
    r = client.get("/api/stories")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_missing_story_returns_404() -> None:
    assert client.get("/api/stories/999999999/articles").status_code == 404


def test_coverage_presets_and_validation() -> None:
    for w in ("24h", "3d", "7d"):
        r = client.get(f"/api/coverage?window={w}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert {"range", "totals", "outlets", "timeline", "reach_distribution", "top_stories"} <= body.keys()
        n = len(body["timeline"]["buckets"])
        assert all(len(s["counts"]) == n for s in body["timeline"]["series"])
    assert client.get("/api/coverage?from=2026-10-01&to=2026-10-02").status_code == 200
    assert client.get("/api/coverage?from=2026-10-05&to=2026-10-01").status_code == 422
    assert client.get("/api/coverage?from=2026-10-05").status_code == 422


def test_compare_validation() -> None:
    assert client.get("/api/compare?ids=1").status_code == 422
    assert client.get("/api/compare?ids=999999998&ids=999999999").status_code == 404


def test_topics_and_filters() -> None:
    r = client.get("/api/topics")
    assert r.status_code == 200
    keys = [t["key"] for t in r.json()]
    assert keys[0] == "politica" and "outros" in keys
    assert client.get("/api/articles?topic=politica").status_code == 200
    assert client.get("/api/stories?topic=esportes").status_code == 200
    body = client.get("/api/coverage?window=24h&topic=economia").json()
    assert body["topic"] == "economia"
    assert isinstance(body["topics"], list)


def test_coverage_by_group() -> None:
    for g in ("nacional", "internacional"):
        body = client.get(f"/api/coverage?window=24h&group={g}").json()
        assert body["group"] == g
        assert all(o["group"] == g for o in body["outlets"])
    assert client.get("/api/coverage?group=marte").status_code == 422


def test_all_seeded_outlets_have_group() -> None:
    outlets = client.get("/api/outlets").json()
    assert {o["outlet_group"] for o in outlets} <= {"nacional", "internacional"}
