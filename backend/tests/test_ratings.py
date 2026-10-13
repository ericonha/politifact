"""Carregador de avaliações atribuídas (precisa do Postgres do compose)."""

import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import Outlet, OutletBiasRating
from app.ratings import RatingError, load_ratings


@pytest.fixture
def outlet():
    slug = f"teste-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as s:
        o = Outlet(slug=slug, name="Teste", canonical_domain=f"{slug}.example", country="BR",
                   language="pt-BR", feed_urls=[], active=False)
        s.add(o)
        s.commit()
        yield o
        s.execute(delete(OutletBiasRating).where(OutletBiasRating.outlet_id == o.id))
        s.execute(delete(Outlet).where(Outlet.id == o.id))
        s.commit()


def _write(tmp_path: Path, ratings: list[dict]) -> Path:
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"ratings": ratings}), encoding="utf-8")
    return p


def test_load_is_idempotent_and_keeps_history(outlet, tmp_path) -> None:
    base = {"outlet_slug": outlet.slug, "provider": "Avaliador X", "rating": "center",
            "methodology_url": "https://x.example/m"}
    path = _write(tmp_path, [{**base, "assessed_at": "2025-01-01"}, {**base, "assessed_at": "2026-01-01",
                                                                       "rating": "center-right"}])
    with SessionLocal() as s:
        assert load_ratings(s, path) == (2, 0)
        assert load_ratings(s, path) == (0, 2)
        rows = s.scalars(select(OutletBiasRating).where(OutletBiasRating.outlet_id == outlet.id)).all()
    assert sorted(r.rating for r in rows) == ["center", "center-right"]


def test_rejects_unattributed_or_invalid(outlet, tmp_path) -> None:
    with SessionLocal() as s:
        with pytest.raises(RatingError):
            load_ratings(s, _write(tmp_path, [{"outlet_slug": outlet.slug, "rating": "center"}]))
        with pytest.raises(RatingError):
            load_ratings(s, _write(tmp_path, [{"outlet_slug": outlet.slug, "provider": "X", "rating": "extrema",
                                              "methodology_url": "u", "assessed_at": "2026-01-01"}]))
