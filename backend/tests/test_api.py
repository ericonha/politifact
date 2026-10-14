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


def test_framing_and_ratings_endpoints() -> None:
    assert client.get("/api/stories/999999999/framing").status_code == 404
    assert client.get("/api/articles/999999999/analysis").status_code == 404
    r = client.get("/api/ratings")
    assert r.status_code == 200 and isinstance(r.json(), list)


def test_favorite_toggle_and_filters() -> None:
    outlets = client.get("/api/outlets").json()
    target = outlets[0]
    try:
        r = client.post(f"/api/outlets/{target['id']}/favorite", json={"favorite": True})
        assert r.status_code == 200 and r.json()["favorite"] is True
        assert client.get("/api/stories?favorites=true").status_code == 200
        assert client.get("/api/articles?favorites=true").status_code == 200
        body = client.get("/api/coverage?window=24h&favorites=true").json()
        favs = {x["id"] for x in client.get("/api/outlets").json() if x["favorite"]}
        returned = {o["id"] for o in body["outlets"]}
        assert target["id"] in returned and returned <= favs
        assert client.get(f"/api/stories?outlet_id={target['id']}").status_code == 200
    finally:
        client.post(f"/api/outlets/{target['id']}/favorite", json={"favorite": target["favorite"]})
    assert client.post("/api/outlets/999999/favorite", json={"favorite": True}).status_code == 404


def test_collection_status() -> None:
    body = client.get("/api/collection-status").json()
    assert {"last_success_at", "running", "interval_minutes", "next_expected_at", "failing_outlets"} <= body.keys()


def test_stories_order_and_relevance() -> None:
    for order in ("relevance", "recent", "reach"):
        r = client.get(f"/api/stories?window=7d&order={order}")
        assert r.status_code == 200
    stories = client.get("/api/stories?window=7d").json()
    rel = [s["relevance"] for s in stories]
    assert rel == sorted(rel, reverse=True)
    assert client.get("/api/stories?order=aleatoria").status_code == 422


def test_outlet_filter_does_not_leak_into_unfiltered_list() -> None:
    # Regressão: o filtro de veículo não pode ser aplicado quando não foi pedido.
    allv = client.get("/api/stories?window=7d").json()
    outlets_seen = {c["outlet_id"] for s in allv for c in s["coverage"]}
    if len(outlets_seen) > 1:
        one = sorted(outlets_seen)[0]
        filtered = client.get(f"/api/stories?window=7d&outlet_id={one}").json()
        assert len(filtered) <= len(allv)
        assert all(any(c["outlet_id"] == one for c in s["coverage"]) for s in filtered)


def test_briefings_endpoint_shape() -> None:
    r = client.get("/api/briefings")
    assert r.status_code == 200
    for b in r.json():
        assert {"topic", "label", "overview", "points", "model", "generated_at"} <= b.keys()
        for p in b["points"]:
            assert p["stories"], "todo ponto precisa de pelo menos uma história citada"


def test_outlet_profile_shape() -> None:
    outlets = client.get("/api/outlets").json()
    body = client.get(f"/api/outlets/{outlets[0]['id']}/profile?window=30d").json()
    assert {"outlet", "range", "timeline", "sections", "actors", "form", "tone", "exclusivity", "totals"} <= body.keys()
    assert len(body["sections"]) == 10
    assert client.get("/api/outlets/999999/profile").status_code == 404
    assert client.get(f"/api/outlets/{outlets[0]['id']}/profile?window=1y").status_code == 422


def test_submit_claim_validation() -> None:
    assert client.post("/api/claims", json={"text": "curto"}).status_code == 422
    assert client.post("/api/claims", json={"text": "x" * 4001}).status_code == 422
    assert client.post("/api/claims", json={"article_id": 999999999}).status_code == 404
    r = client.post("/api/claims", json={"url": "https://nao-coletado.example/noticia"})
    assert r.status_code == 422 and "cole o texto" in r.json()["detail"].lower()


def test_factcheck_read_endpoints() -> None:
    assert client.get("/api/investigations").status_code == 200
    assert client.get("/api/investigations/999999999").status_code == 404
    assert client.get("/api/claims/999999999").status_code == 404
    assert client.post("/api/fact-checks/999999999/review", json={"decision": "approved"}).status_code == 404
