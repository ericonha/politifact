"""Checagens publicadas: leitura do formato ClaimReview (sem rede)."""

import json

from app.factcheck.sources.factchecks import parse_response, search
from app.factcheck.sources.press import build_query

PAYLOAD = json.dumps({
    "claims": [
        {
            "text": "A inflação de 2025 foi a maior da década",
            "claimant": "Político X",
            "claimDate": "2026-01-10T00:00:00Z",
            "claimReview": [
                {
                    "publisher": {"name": "Agência Exemplo", "site": "exemplo.org"},
                    "url": "https://exemplo.org/checagem/1",
                    "title": "É falso que a inflação de 2025 foi a maior da década",
                    "reviewDate": "2026-01-12T00:00:00Z",
                    "textualRating": "Falso",
                    "languageCode": "pt",
                },
                {"publisher": {"name": "Sem link"}},
            ],
        }
    ]
}).encode()


def test_parse_claim_review() -> None:
    (ev,) = parse_response(PAYLOAD)
    assert ev.source_type == "fact_check" and ev.relationship == "related"
    assert ev.data["rating"] == "Falso" and ev.data["publisher"] == "Agência Exemplo"
    assert "Classificação da agência: Falso" in ev.relevant_passage
    assert ev.published_at.isoformat() == "2026-01-12"


def test_empty_and_no_key() -> None:
    assert parse_response(b"{}") == []
    assert search("qualquer coisa", None) == []


def test_press_query_uses_or_and_names_first() -> None:
    q = build_query("Moraes manda prender ex-assessor de Bolsonaro em operação da PF")
    terms = q.split(" or ")
    assert terms[:2] == ["moraes", "bolsonaro"] and "or" in q
    assert len(terms) <= 6
    assert build_query("é de") is None
