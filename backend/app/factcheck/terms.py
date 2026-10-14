"""Palavras-chave de uma afirmação e filtro de relevância das notícias (puro, sem banco)."""

from app.clustering.core import _STOPWORDS, entity_mentions
from app.factcheck.parse import fold

MAX_TERMS = 6


def query_terms(claim: str) -> list[str]:
    """Palavras-chave da afirmação: nomes próprios primeiro, depois as palavras mais longas."""
    terms: list[str] = []
    for key, _ in entity_mentions(claim):
        for w in key.split():
            if len(w) > 2 and w not in terms:
                terms.append(w)
    words = sorted({w for w in fold(claim).replace("-", " ").split()
                    if w.isalpha() and len(w) >= 5 and w not in _STOPWORDS}, key=len, reverse=True)
    for w in words:
        if w not in terms:
            terms.append(w)
    return [t for t in terms if t.isalpha()][:MAX_TERMS]


def overlap_ok(terms: list[str], text: str) -> bool:
    """A notícia precisa conter pelo menos metade dos termos (mín. 2; radical de 5 letras).

    Evita trazer, por exemplo, uma pesquisa de governador por causa de um sobrenome em comum.
    """
    if not terms:
        return False
    hay = fold(text)
    hits = sum(1 for t in terms if t[:5] in hay)
    need = min(len(terms), max(2, (len(terms) + 1) // 2))
    return hits >= need
