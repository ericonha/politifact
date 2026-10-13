"""Núcleo do agrupamento: características, similaridade e decisão.

Ideia geral (agrupamento incremental):
  Para cada notícia nova, em ordem de publicação, compara com as histórias
  ativas (com notícia nas últimas `story_window_hours`). O score contra uma
  história é a média das 2 maiores similaridades com as notícias dela, o que
  reduz o "efeito corrente" (A parecido com B, B com C, e A nada a ver com C).

  score >= assign_threshold        -> entra na história
  score <  new_story_threshold     -> cria história nova
  no meio                          -> ambígua: fica fora e vai para revisão

Similaridade por par, em escala 0–1:
  com embeddings dos dois lados: 0.65*emb + 0.20*léxico + 0.15*entidades
  sem embedding:                 0.60*léxico + 0.40*entidades
Cada componente é reescalado para que "mesma história" fique perto de 1.
Os pesos e limiares são palpites iniciais: ajuste com `app.clustering.evaluate`.
"""

import math
import re
import unicodedata
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta

ALGORITHM_VERSION = "incremental-v1"

_STOPWORDS = set(
    """
    a o as os um uma uns umas de do da dos das em no na nos nas por pelo pela pelos pelas
    para pra com sem sob sobre entre ate apos ante contra desde e ou mas nem que se ja nao
    sim mais menos muito muita muitos muitas pouco ao aos a as este esta estes estas esse
    essa esses essas isso isto aquele aquela aquilo seu sua seus suas meu minha nosso nossa
    ele ela eles elas eu tu voce voces nos vos lhe lhes me te foi ser sao era eram sera
    estar esta estao estava tem ter tinha teve ha havia diz dizem disse afirma afirmou
    apos durante quando onde como porque qual quais quem cujo cuja vai vao pode podem deve
    devem fica ficam faz fazem novo nova novos novas veja video ao vivo hoje ontem amanha
    ano anos dia dias semana mes meses brasil brasileiro brasileira
    """.split()
)

# Palavras que começam frase em maiúscula mas não são nomes próprios.
_TITLES = {"governo", "presidente", "ministro", "ministra", "deputado", "deputada", "senador", "senadora"}
_CAPITALIZED_NOISE = _STOPWORDS | _TITLES | {"brazil", "brazilian", "brazilians", "the"}
# Só estas são removidas do início de um nome composto ("O Banco Central" -> "banco central");
# verbos como "são" ficam, para não estragar "São Paulo".
_LEADING_NOISE = {"o", "a", "os", "as", "um", "uma", "em", "no", "na", "nos", "nas",
                  "de", "do", "da", "para", "com", "e", "ex"} | _TITLES

_STEM_LEN = 6


def _strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def tokens(text: str) -> frozenset[str]:
    """Tokens de conteúdo: sem acento, minúsculos, sem stopwords, com um radical
    simples (6 primeiras letras), para "aprova", "aprovado" e "aprovação" baterem."""
    words = re.findall(r"[a-z0-9]+", _strip_accents(text).lower())
    return frozenset(
        w[:_STEM_LEN] for w in words if (len(w) >= 3 or w.isdigit()) and w not in _STOPWORDS
    )


def entity_mentions(text: str) -> list[tuple[str, str]]:
    """Como `entities_ordered`, mas devolve (chave normalizada, forma como aparece no texto)."""
    return _entities(text)


def entities_ordered(text: str) -> list[str]:
    return [key for key, _ in _entities(text)]


def _entities(text: str) -> list[tuple[str, str]]:
    """Nomes próprios e siglas por heurística (sem modelo de NER), na ordem em que aparecem.

    Pega sequências de palavras com inicial maiúscula ("Banco Central",
    "Alexandre de Moraes") e siglas ("STF", "PT"). Sem repetição.
    """
    found: list[tuple[int, str, str]] = []
    pattern = r"[A-ZÀ-Ý][\wÀ-ÿ'-]*(?:\s+(?:(?:de|da|do|dos|das)\s+)?[A-ZÀ-Ý][\wÀ-ÿ'-]*)*"
    for match in re.finditer(pattern, text):
        phrase = match.group(0).strip()
        norm = _strip_accents(phrase).lower()
        if len(norm) < 2 or norm in _CAPITALIZED_NOISE:
            continue
        parts = norm.split()
        surface_parts = phrase.split()
        while len(parts) > 1 and parts[0] in _LEADING_NOISE:
            parts.pop(0)
            surface_parts.pop(0)
        joined = " ".join(parts)
        if joined not in _CAPITALIZED_NOISE:
            found.append((match.start(), joined, " ".join(surface_parts)))
    for match in re.finditer(r"\b[A-Z]{2,6}\b", text):
        found.append((match.start(), match.group(0).lower(), match.group(0)))
    seen: set[str] = set()
    ordered: list[tuple[str, str]] = []
    for _, key, surface in sorted(found):
        if key not in seen:
            seen.add(key)
            ordered.append((key, surface))
    return ordered


def entities(text: str) -> frozenset[str]:
    return frozenset(entities_ordered(text))


@dataclass(frozen=True)
class Features:
    article_id: int
    outlet_id: int
    time: datetime
    tokens: frozenset[str]
    entities: frozenset[str]
    embedding: tuple[float, ...] | None = None


def make_features(
    article_id: int,
    outlet_id: int,
    time: datetime,
    headline: str,
    summary: str | None,
    embedding: list[float] | tuple[float, ...] | None = None,
) -> Features:
    text = f"{headline}. {summary or ''}"
    return Features(
        article_id=article_id,
        outlet_id=outlet_id,
        time=time,
        tokens=tokens(text),
        entities=entities(text),
        embedding=tuple(embedding) if embedding is not None else None,
    )


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def cosine(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _rescale(value: float, low: float, high: float) -> float:
    """Mapeia [low, high] em [0, 1], cortando fora do intervalo."""
    if high <= low:
        return 0.0
    return min(1.0, max(0.0, (value - low) / (high - low)))


@dataclass(frozen=True)
class Params:
    assign_threshold: float = 0.60
    new_story_threshold: float = 0.45
    story_window_hours: float = 48.0
    # Reescala dos componentes (valor típico de "não relacionado" -> 0, "mesma história" -> 1).
    emb_low: float = 0.50
    emb_high: float = 0.85
    lex_low: float = 0.05
    lex_high: float = 0.40
    ent_low: float = 0.0
    ent_high: float = 0.50
    w_emb: float = 0.65
    w_lex: float = 0.20
    w_ent: float = 0.15
    w_lex_only: float = 0.60
    w_ent_only: float = 0.40

    def with_thresholds(self, assign: float, new_story: float) -> "Params":
        return replace(self, assign_threshold=assign, new_story_threshold=new_story)


def pair_score(a: Features, b: Features, p: Params) -> float:
    lex = _rescale(jaccard(a.tokens, b.tokens), p.lex_low, p.lex_high)
    ent = _rescale(jaccard(a.entities, b.entities), p.ent_low, p.ent_high)
    # Vetores de modelos diferentes (tamanhos diferentes) não são comparáveis.
    if a.embedding is not None and b.embedding is not None and len(a.embedding) == len(b.embedding):
        emb = _rescale(cosine(a.embedding, b.embedding), p.emb_low, p.emb_high)
        return p.w_emb * emb + p.w_lex * lex + p.w_ent * ent
    return p.w_lex_only * lex + p.w_ent_only * ent


@dataclass
class StoryState:
    story_id: int
    members: list[Features] = field(default_factory=list)

    @property
    def last_time(self) -> datetime:
        return max(m.time for m in self.members)

    def score(self, f: Features, p: Params) -> float:
        sims = sorted((pair_score(f, m, p) for m in self.members), reverse=True)
        top = sims[:2]
        return sum(top) / len(top) if top else 0.0


@dataclass(frozen=True)
class Decision:
    kind: str  # "assigned" | "new_story" | "ambiguous"
    story_id: int | None  # história escolhida (assigned) ou melhor candidata (ambiguous)
    score: float


def decide(f: Features, stories: list[StoryState], p: Params) -> Decision:
    horizon = f.time - timedelta(hours=p.story_window_hours)
    best_id, best = None, 0.0
    for story in stories:
        if not story.members or story.last_time < horizon:
            continue
        s = story.score(f, p)
        if s > best:
            best_id, best = story.story_id, s
    if best_id is not None and best >= p.assign_threshold:
        return Decision("assigned", best_id, best)
    if best_id is not None and best >= p.new_story_threshold:
        return Decision("ambiguous", best_id, best)
    return Decision("new_story", None, best)


def cluster_offline(items: list[Features], p: Params) -> dict[int, int]:
    """Agrupa uma lista inteira do zero (usado na avaliação).

    Retorna article_id -> id de cluster. Notícias ambíguas viram cluster
    próprio, que é o que o usuário veria antes de revisar.
    """
    stories: list[StoryState] = []
    labels: dict[int, int] = {}
    for f in sorted(items, key=lambda x: (x.time, x.article_id)):
        d = decide(f, stories, p)
        if d.kind == "assigned":
            target = next(s for s in stories if s.story_id == d.story_id)
            target.members.append(f)
            labels[f.article_id] = d.story_id  # type: ignore[assignment]
        else:
            new_id = len(stories) + 1
            stories.append(StoryState(new_id, [f]))
            labels[f.article_id] = new_id
    return labels


# --- Deduplicação ----------------------------------------------------------

NEAR_DUP_HEADLINE_JACCARD = 0.85
NEAR_DUP_WINDOW = timedelta(hours=48)


def headline_tokens(headline: str) -> frozenset[str]:
    """Tokens do título sem radical e com stopwords, para comparar títulos quase iguais."""
    return frozenset(re.findall(r"[a-z0-9]+", _strip_accents(headline).lower()))


@dataclass(frozen=True)
class DedupCandidate:
    article_id: int
    outlet_id: int
    time: datetime
    content_hash: str | None
    headline_tokens: frozenset[str]


def find_duplicate(item: DedupCandidate, earlier: list[DedupCandidate]) -> tuple[int, str] | None:
    """Procura um artigo anterior que seja o mesmo conteúdo.

    - "exact": mesmo hash de título + resumo (mesmo veículo ou republicação de outro);
    - "near_headline": mesmo veículo, título quase idêntico em até 48 h (URL mudou).
    Retorna (id do original, método) ou None.
    """
    for other in earlier:
        if other.article_id == item.article_id:
            continue
        if item.content_hash and item.content_hash == other.content_hash:
            return other.article_id, "exact"
    for other in earlier:
        if other.article_id == item.article_id or other.outlet_id != item.outlet_id:
            continue
        if abs(item.time - other.time) > NEAR_DUP_WINDOW:
            continue
        if jaccard(item.headline_tokens, other.headline_tokens) >= NEAR_DUP_HEADLINE_JACCARD:
            return other.article_id, "near_headline"
    return None
