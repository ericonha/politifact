"""Características observáveis de uma manchete (regras transparentes, sem IA).

Nada aqui é um julgamento de viés: são fatos verificáveis no texto
(quem aparece primeiro, se é uma fala atribuída, se usa aspas, termos de impacto).
"""

import re
import unicodedata

from app.clustering.core import entity_mentions

VERSION = "observable-v1"

# Verbos que indicam fala atribuída ("Fulano diz que...", "Lula critica...").
_ATTRIBUTION = {
    "diz", "dizem", "disse", "afirma", "afirmam", "afirmou", "declara", "declarou", "acusa", "acusam",
    "critica", "criticam", "defende", "defendem", "nega", "negam", "admite", "alerta", "reclama",
    "rebate", "ataca", "atacam", "elogia", "promete", "ameaca", "sugere", "garante", "cobra", "pede",
    "minimiza", "ironiza", "responde", "says", "said", "claims", "accuses", "warns", "denies",
}

# Termos de impacto/avaliativos: palavras fortes que o veículo escolheu usar.
# Não indicam lado político; indicam ênfase. A lista é curta de propósito e
# pode ser ampliada aqui.
_LOADED = {
    "escandalo", "polemica", "polemico", "polemicos", "caos", "ataque", "ataques", "golpe", "golpista",
    "golpistas", "radical", "radicais", "extremista", "extremistas", "mentira", "mentiras", "desastre",
    "vexame", "humilha", "humilhacao", "detona", "dispara", "explode", "bomba", "chocante", "absurdo",
    "vergonha", "farra", "mamata", "privilegio", "privilegios", "ditadura", "censura", "perseguicao",
    "heroi", "vilao", "historico", "historica", "recorde", "tragedia", "escancara", "enquadra",
    "rombo", "fiasco", "derrota", "vitoria", "massacre", "terror", "panico", "bilionario", "sigilo",
    "blindagem", "manobra", "tratoraco", "fake", "desmonte", "aparelhamento", "lacra",
    "scandal", "chaos", "attack", "coup", "radical", "extremist", "lies", "disaster", "shocking",
}

_QUOTES = re.compile(r"[\"“”‘’«»]|(^|\s)'|'(\s|$)")


def _fold(word: str) -> str:
    word = unicodedata.normalize("NFKD", word)
    return "".join(c for c in word if not unicodedata.combining(c)).lower()


def _words(text: str) -> list[str]:
    return re.findall(r"[\wÀ-ÿ]+", text)


def analyze(headline: str, summary: str | None) -> dict:
    """Retorna um dicionário pequeno e estável (vai para JSONB e para a tela)."""
    words = _words(headline)
    folded = [_fold(w) for w in words]
    head_mentions = entity_mentions(headline)
    all_mentions = entity_mentions(f"{headline}. {summary or ''}")

    attribution = [w for w, f in zip(words, folded) if f in _ATTRIBUTION]
    loaded = [w for w, f in zip(words, folded) if f in _LOADED]
    loaded_summary = [w for w in _words(summary or "") if _fold(w) in _LOADED]

    return {
        "version": VERSION,
        "headline_words": len(words),
        "is_question": headline.strip().endswith("?"),
        "has_exclamation": "!" in headline,
        "has_quote": bool(_QUOTES.search(headline)),
        "has_number": bool(re.search(r"\d", headline)),
        "attribution_verbs": attribution,
        "lead_actor": head_mentions[0][1] if head_mentions else None,
        "lead_actor_key": head_mentions[0][0] if head_mentions else None,
        "headline_actors": [{"key": k, "name": n} for k, n in head_mentions],
        "actors": [{"key": k, "name": n} for k, n in all_mentions],
        "loaded_terms": loaded,
        "loaded_terms_summary": loaded_summary,
    }
