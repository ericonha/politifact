"""Checagens já publicadas por agências (via Google Fact Check Tools, formato ClaimReview).

Opcional: só funciona com FACTCHECK_API_KEY (chave gratuita do Google Cloud,
API "Fact Check Tools"). Sem chave, a fonte é pulada e isso aparece nas limitações.

Guardamos o veredito da agência como ela publicou (textualRating) e o link.
O sistema não adota esse veredito automaticamente: ele é evidência de terceiro.
"""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime

from app.factcheck.sources import EvidenceItem

log = logging.getLogger(__name__)

ENDPOINT = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
TIMEOUT = 20
MAX_RESULTS = 5


class FactCheckSourceError(RuntimeError):
    pass


def _date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def parse_response(payload: bytes) -> list[EvidenceItem]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise FactCheckSourceError("resposta não é JSON") from exc
    items: list[EvidenceItem] = []
    for claim in data.get("claims", []) or []:
        for review in claim.get("claimReview", []) or []:
            url = review.get("url")
            if not url:
                continue
            pub = review.get("publisher") or {}
            publisher = pub.get("name") or pub.get("site") or "?"
            rating = (review.get("textualRating") or "").strip()
            claim_text = (claim.get("text") or "").strip()
            claimant = (claim.get("claimant") or "").strip()
            passage = f"{publisher} checou: “{claim_text}”" + (f" ({claimant})" if claimant else "") + \
                      (f". Classificação da agência: {rating}." if rating else ".")
            items.append(EvidenceItem(
                provider="factcheck", source_type="fact_check", source_url=url,
                source_title=review.get("title") or f"Checagem de {publisher}",
                relevant_passage=passage[:800], relationship="related", verification_status="third_party",
                published_at=_date(review.get("reviewDate")) or _date(claim.get("claimDate")),
                data={"publisher": publisher, "rating": rating, "claim_text": claim_text, "claimant": claimant,
                      "language": review.get("languageCode")},
            ))
    return items[:MAX_RESULTS]


def search(query: str, api_key: str | None) -> list[EvidenceItem]:
    if not api_key:
        return []
    params = urllib.parse.urlencode({"query": query[:300], "languageCode": "pt", "pageSize": MAX_RESULTS,
                                     "key": api_key})
    req = urllib.request.Request(f"{ENDPOINT}?{params}", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return parse_response(resp.read(2_000_000))
    except urllib.error.HTTPError as exc:
        raise FactCheckSourceError(f"Fact Check Tools respondeu {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise FactCheckSourceError(f"Fact Check Tools inacessível: {exc}") from exc
