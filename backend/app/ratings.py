"""Avaliações de orientação política dos veículos, sempre ATRIBUÍDAS a um avaliador.

O sistema não classifica veículos por conta própria. Cada avaliação vem de uma
fonte identificada (provider), com metodologia, data e link, e fica num arquivo
editável: backend/data/outlet_ratings.json. O serviço `migrate` carrega o arquivo
a cada `docker compose up`.

Histórico: avaliações nunca são apagadas pelo carregador. Uma reavaliação é uma
nova entrada com outra data (assessed_at); a anterior pode ganhar valid_until.
"""

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Outlet, OutletBiasRating

RATINGS_FILE = Path(__file__).resolve().parent.parent / "data" / "outlet_ratings.json"

LABELS = {
    "left": "esquerda",
    "center-left": "centro-esquerda",
    "center": "centro",
    "center-right": "centro-direita",
    "right": "direita",
    "mixed": "misto",
    "unknown": "indefinido",
}
REQUIRED = ("outlet_slug", "provider", "rating", "methodology_url", "assessed_at")


class RatingError(ValueError):
    pass


def _date(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def load_ratings(session: Session, path: Path = RATINGS_FILE) -> tuple[int, int]:
    """Insere avaliações novas do arquivo. Retorna (inseridas, já existentes)."""
    if not path.exists():
        return 0, 0
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("ratings", [])
    outlets = {o.slug: o.id for o in session.scalars(select(Outlet))}
    inserted = existing = 0
    for i, e in enumerate(entries):
        missing = [k for k in REQUIRED if not e.get(k)]
        if missing:
            raise RatingError(f"avaliação #{i + 1}: faltam campos {missing}")
        if e["rating"] not in LABELS:
            raise RatingError(f"avaliação #{i + 1}: rating '{e['rating']}' inválido; use {list(LABELS)}")
        outlet_id = outlets.get(e["outlet_slug"])
        if outlet_id is None:
            raise RatingError(f"avaliação #{i + 1}: veículo '{e['outlet_slug']}' não existe em seed.py")
        assessed = _date(e["assessed_at"])
        found = session.scalar(select(OutletBiasRating).where(
            OutletBiasRating.outlet_id == outlet_id,
            OutletBiasRating.provider == e["provider"],
            OutletBiasRating.assessed_at == assessed,
        ))
        if found:
            existing += 1
            # Só completa o fim da validade (reavaliação posterior); não reescreve a avaliação.
            if e.get("valid_until") and not found.valid_until:
                found.valid_until = _date(e["valid_until"])
            continue
        session.add(OutletBiasRating(
            outlet_id=outlet_id, provider=e["provider"], rating=e["rating"],
            methodology_url=e["methodology_url"], reference_url=e.get("reference_url"),
            assessed_at=assessed, valid_from=_date(e.get("valid_from")) or assessed,
            valid_until=_date(e.get("valid_until")), confidence=e.get("confidence"), notes=e.get("notes"),
        ))
        inserted += 1
    session.commit()
    return inserted, existing


if __name__ == "__main__":
    from app.db import SessionLocal

    with SessionLocal() as s:
        ins, ex = load_ratings(s)
    print(f"Avaliações de veículos: {ins} novas, {ex} já existentes.")
