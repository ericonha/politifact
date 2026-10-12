"""Veículos monitorados no MVP.

Este arquivo é a fonte da configuração de coleta: rodar o seed de novo
atualiza nome, domínio, feeds, observações e ativo/inativo dos veículos
existentes. Mudanças nos feeds se fazem aqui.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Outlet

OUTLETS = [
    {
        "slug": "jovem-pan",
        "name": "Jovem Pan",
        "canonical_domain": "jovempan.com.br",
        "country": "BR",
        "language": "pt-BR",
        "feed_urls": ["https://jovempan.com.br/feed"],
        "active": True,
        "collection_notes": None,
    },
    {
        "slug": "band",
        "name": "Band",
        "canonical_domain": "band.com.br",
        "country": "BR",
        "language": "pt-BR",
        "feed_urls": [],
        "active": False,
        "collection_notes": (
            "Sem feed RSS público encontrado (out/2026). Desativado até achar uma fonte "
            "permitida, por exemplo um sitemap de notícias autorizado pelo robots.txt."
        ),
    },
    {
        "slug": "cnn-brasil",
        "name": "CNN Brasil",
        "canonical_domain": "cnnbrasil.com.br",
        "country": "BR",
        "language": "pt-BR",
        "feed_urls": ["https://www.cnnbrasil.com.br/feed/"],
        "active": True,
        "collection_notes": None,
    },
    {
        "slug": "bbc-brasil",
        "name": "BBC News Brasil",
        "canonical_domain": "bbc.com/portuguese",
        "country": "GB",
        "language": "pt-BR",
        "feed_urls": ["https://feeds.bbci.co.uk/portuguese/rss.xml"],
        "active": True,
        "collection_notes": None,
    },
]


def seed_outlets(session: Session) -> int:
    """Cria veículos novos e atualiza a configuração dos existentes. Retorna quantos foram criados."""
    existing = {o.slug: o for o in session.scalars(select(Outlet))}
    created = 0
    for data in OUTLETS:
        outlet = existing.get(data["slug"])
        if outlet is None:
            session.add(Outlet(**data))
            created += 1
        else:
            for key, value in data.items():
                setattr(outlet, key, value)
    session.commit()
    return created


if __name__ == "__main__":
    with SessionLocal() as s:
        print(f"Veículos criados: {seed_outlets(s)}")
