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
    assert r.json() == {"status": "ok", "database": "ok"}


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
