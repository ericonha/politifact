"""Fontes de evidência.

bcb.py         dados oficiais do Banco Central (SGS): decidem veredito por regra.
factchecks.py  checagens já publicadas (Google Fact Check Tools, opcional).
press.py       notícias já coletadas pelo sistema: só contexto, nunca prova.
"""

from dataclasses import dataclass, field
from datetime import date


@dataclass
class EvidenceItem:
    provider: str  # bcb_sgs | factcheck | press
    source_type: str  # official_data | fact_check | press
    source_url: str
    source_title: str
    relevant_passage: str
    relationship: str  # supports | contradicts | context | related
    verification_status: str  # retrieved_by_system | third_party | context_only
    published_at: date | None = None
    data: dict = field(default_factory=dict)
