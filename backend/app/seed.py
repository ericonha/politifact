"""Veículos monitorados.

Este arquivo é a fonte da configuração de coleta: o serviço `migrate` roda o
seed a cada `docker compose up` e atualiza nome, domínio, feeds, grupo,
observações e ativo/inativo dos veículos existentes.

Grupos:
- "nacional": veículos brasileiros (inclui marcas licenciadas, como CNN Brasil);
- "internacional": veículos estrangeiros, com edição em português ou não.
  O painel permite comparar cada grupo separadamente, porque um veículo
  estrangeiro publica poucas notícias sobre o Brasil e pareceria "ignorar"
  histórias numa comparação direta com veículos nacionais.

`verified`: o feed foi aberto e lido em 12/10/2026. Os não verificados estão
ativos; se o feed falhar, o motivo aparece na tela Coletas.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Outlet

NOT_VERIFIED = "Feed não verificado na configuração; se falhar, o motivo aparece em Coletas."


def _o(slug, name, domain, feeds, *, group="nacional", country="BR", language="pt-BR",
       active=True, verified=True, notes=None):
    return {
        "slug": slug, "name": name, "canonical_domain": domain, "feed_urls": feeds,
        "outlet_group": group, "country": country, "language": language, "active": active,
        "collection_notes": notes if notes is not None else (None if verified else NOT_VERIFIED),
    }


OUTLETS = [
    # --- Nacionais ---------------------------------------------------------
    _o("jovem-pan", "Jovem Pan", "jovempan.com.br", ["https://jovempan.com.br/feed"],
       notes="O feed traz só as 10 notícias mais recentes; em horas movimentadas pode perder notícias."),
    _o("band", "Band", "band.com.br", [], active=False,
       notes=("Sem feed RSS público encontrado (out/2026). Desativado até achar uma fonte "
              "permitida, por exemplo um sitemap de notícias autorizado pelo robots.txt.")),
    _o("cnn-brasil", "CNN Brasil", "cnnbrasil.com.br", ["https://www.cnnbrasil.com.br/feed/"]),
    _o("agencia-brasil", "Agência Brasil", "agenciabrasil.ebc.com.br",
       ["https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml"]),
    _o("poder360", "Poder360", "poder360.com.br", ["https://www.poder360.com.br/feed/"],
       notes="O feed traz só as 10 notícias mais recentes."),
    _o("metropoles", "Metrópoles", "metropoles.com", ["https://www.metropoles.com/feed"]),
    _o("cartacapital", "CartaCapital", "cartacapital.com.br", ["https://www.cartacapital.com.br/feed/"]),
    _o("gazeta-do-povo", "Gazeta do Povo", "gazetadopovo.com.br",
       ["https://www.gazetadopovo.com.br/feed/rss/ultimas-noticias.xml"]),
    _o("revista-oeste", "Revista Oeste", "revistaoeste.com", ["https://revistaoeste.com/feed/"]),
    _o("infomoney", "InfoMoney", "infomoney.com.br", ["https://www.infomoney.com.br/feed/"]),
    _o("g1", "g1", "g1.globo.com", ["https://g1.globo.com/rss/g1/"], verified=False),
    _o("folha", "Folha de S.Paulo", "folha.uol.com.br",
       ["https://feeds.folha.uol.com.br/emcimadahora/rss091.xml"], verified=False),
    _o("veja", "Veja", "veja.abril.com.br", ["https://veja.abril.com.br/feed/"], verified=False),
    _o("uol", "UOL", "noticias.uol.com.br", ["https://rss.uol.com.br/feed/noticias.xml"], verified=False),
    # --- Internacionais em português --------------------------------------
    _o("bbc-brasil", "BBC News Brasil", "bbc.com/portuguese",
       ["https://feeds.bbci.co.uk/portuguese/rss.xml"], group="internacional", country="GB"),
    _o("bloomberg-linea", "Bloomberg Línea Brasil", "bloomberglinea.com.br",
       ["https://www.bloomberglinea.com.br/arc/outboundfeeds/rss/?outputType=xml"],
       group="internacional", country="US",
       notes="Feed pouco atualizado: a notícia mais recente tinha 3 dias na configuração."),
    _o("dw-brasil", "DW Brasil", "dw.com/pt-br", ["https://rss.dw.com/xml/rss-br-all"],
       group="internacional", country="DE", verified=False),
    _o("rfi-brasil", "RFI Brasil", "rfi.fr/br", ["https://www.rfi.fr/br/rss"],
       group="internacional", country="FR", verified=False),
    # --- Internacionais em inglês (sem tradução) ---------------------------
    # Só as seções sobre o Brasil/Américas: o feed geral encheria o painel de
    # notícias sem relação com o Brasil. Agrupar com notícias em português
    # depende dos embeddings multilíngues (Ollama + bge-m3).
    _o("the-economist", "The Economist", "economist.com",
       ["https://www.economist.com/the-americas/rss.xml"], group="internacional", country="GB",
       language="en", verified=False,
       notes="Seção The Americas (inclui outros países da região). " + NOT_VERIFIED),
    _o("the-guardian", "The Guardian", "theguardian.com",
       ["https://www.theguardian.com/world/brazil/rss"], group="internacional", country="GB",
       language="en", verified=False,
       notes="Página sobre o Brasil. " + NOT_VERIFIED),
]

# Fora por decisão ou impossibilidade (documentado para não ser readicionado por engano):
# - Bloomberg (original em inglês): robots.txt proíbe coleta automática; use a Bloomberg Línea.
# - Reuters e AP: sem RSS público.
# - O Globo e Estadão: fora do escopo do MVP.


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
