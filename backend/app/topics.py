"""Seções temáticas (Política, Economia, Esportes...).

A seção de uma notícia vem, nesta ordem de confiança:
  1. "feed": a categoria que o próprio veículo declarou no RSS (<category>);
  2. "url":  o caminho da URL (ex.: /politica/..., /esportes/...);
  3. "keywords": palavras do título e do resumo (só quando 1 e 2 não dizem nada);
  4. "none": nada bateu -> "outros".
A origem fica gravada (topic_source), para dar para medir e corrigir depois.
A seção de uma história é a mais comum entre as suas notícias (ignorando "outros").
"""

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from urllib.parse import urlsplit

TOPICS: dict[str, str] = {
    "politica": "Política",
    "economia": "Economia",
    "negocios": "Negócios",
    "internacional": "Internacional",
    "brasil": "Brasil",
    "esportes": "Esportes",
    "saude": "Saúde",
    "ciencia-tecnologia": "Ciência e tecnologia",
    "cultura": "Cultura e entretenimento",
    "outros": "Outros",
}
OTHER = "outros"

# Nomes de seção usados por veículos (em slug, sem acento) -> seção canônica.
_SECTION_ALIASES: dict[str, str] = {}
for _topic, _names in {
    "politica": """politica politicas eleicoes eleicao poder governo congresso brasilia justica republica
        politics election elections us-politics""",
    "economia": """economia financas macroeconomia impostos tributos seu-dinheiro dinheiro
        economy economics finance-and-economics""",
    "negocios": """negocios empresas mercado mercados business investimentos investir agronegocio agro
        markets companies""",
    "internacional": """internacional mundo world america-latina europa oriente-medio estados-unidos eua asia
        africa the-americas americas international""",
    "brasil": """brasil nacional cotidiano cidades sao-paulo rio-de-janeiro distrito-federal seguranca educacao
        geral noticias-gerais ultimas-noticias brazil""",
    "esportes": "esportes esporte futebol sports sport formula-1 f1 olimpiadas copa-do-mundo football",
    "saude": "saude health bem-estar medicina",
    "ciencia-tecnologia": """ciencia tecnologia tech science meio-ambiente clima inovacao environment
        technology science-and-technology""",
    "cultura": """cultura entretenimento celebridades famosos tv tv-e-cinema cinema musica pop lifestyle
        estilo-de-vida viagem culture arts books film music""",
}.items():
    for _n in _names.split():
        _SECTION_ALIASES[_n] = _topic

# Radicais (6 primeiras letras, sem acento) que indicam cada seção no texto.
_KEYWORDS: dict[str, set[str]] = {
    "politica": set("""lula bolson congre senado senado camara deputa senado eleica eleito
        eleico candid partid stf suprem tse planal prefei govern ministe moraes tarcis
        impeac cpi votaca pleito urnas urna campan""".split()),
    "economia": set("""inflac juros selic pib copom dolar impost tribut fiscal ipca desemp
        empreg salari orcame arreca divida haddad recess cambio tarifa""".split()),
    "negocios": set("""empres acoes ibovesp lucro receit fusao aquisi startu varejo petrob
        ipo invest balanc dividen bilhoe montad""".split()),
    "internacional": set("""eua trump china russia ucrani israel gaza hamas ira otan onu europa
        argent venezu guerra putin biden xi milei papa vatica chines russo americ
        israel palest coreia japao franca alemanha reino""".split()),
    "esportes": set("""futebo copa campeo gol palmei corint flamen seleca tecnic olimpi tenis
        nba basque vasco gremio brasil fluminense botafo libert brasile atleta partid
        jogado""".split()) - {"brasil", "partid"},
    "saude": set("""saude doenca virus vacina hospit sus medico cancer dengue covid sarampo
        anvisa remedi tratam""".split()),
    "ciencia-tecnologia": set("""nasa cienti pesqui planeta clima ambien desmat tecnol intelig
        satel astron espaci fossil robo""".split()),
    "cultura": set("""ator atriz filme serie novela cantor cantora show musica festiv bbb famoso
        celebr netflix cinema livro artist oscar""".split()),
    "brasil": set("""polici crime prisao preso chuva acide escola educac transit incend assalt
        tirote enchen temporal enem""".split()),
}
# Radicais em inglês (veículos internacionais sem tradução).
_KEYWORDS_EN: dict[str, set[str]] = {
    "politica": set("lula bolson electi presid congre senate suprem court campai voters partie impeac".split()),
    "economia": set("inflat econom budget fiscal tariff unempl centra recess curren".split()),
    "negocios": set("compan shares market profit merger startu invest billio petrob".split()),
    "internacional": set("trump china russia ukrain israel gaza nato united argent venezu".split()),
    "esportes": set("footba soccer olympi tennis".split()),
    "saude": set("health diseas vaccin hospit dengue cancer".split()),
    "ciencia-tecnologia": set("scient climat amazon defore satell resear".split()),
    "cultura": set("film novel music artist festiv".split()),
}
for _t, _words in _KEYWORDS_EN.items():
    _KEYWORDS[_t] |= _words
_MIN_KEYWORD_SCORE = 2


def _slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def _stems(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return [w[:6] for w in re.findall(r"[a-z0-9]+", text) if len(w) >= 3]


@dataclass(frozen=True)
class TopicResult:
    topic: str
    source: str  # feed | url | keywords | none


def _section_topic(name: str) -> str | None:
    """Nome de seção -> seção canônica, tolerando variações de veículo:
    "eleicoes-2026" -> "eleicoes", "poder-economia" (Poder360) -> "economia"."""
    slug = _slug(name)
    candidates = [slug, re.sub(r"-?\d{4}$", "", slug)]
    if slug.startswith("poder-"):
        rest = slug.removeprefix("poder-")
        candidates += [rest, re.sub(r"-?\d{4}$", "", rest)]
    for c in candidates:
        if c in _SECTION_ALIASES:
            return _SECTION_ALIASES[c]
    return None


def from_categories(categories: list[str] | tuple[str, ...] | None) -> str | None:
    for cat in categories or ():
        topic = _section_topic(cat)
        if topic:
            return topic
    return None


def from_url(url: str) -> str | None:
    segments = [s for s in urlsplit(url).path.lower().split("/") if s]
    # Ignora prefixos de idioma/edição ("/portuguese/", "/br/").
    segments = [s for s in segments if s not in {"portuguese", "br", "pt", "pt-br", "en"}]
    for seg in segments[:3]:
        topic = _section_topic(seg)
        if topic:
            return topic
    return None


def from_keywords(headline: str, summary: str | None) -> str | None:
    """Título vale 2 pontos por palavra, resumo vale 1. Precisa de 2 pontos no mínimo."""
    scores: Counter[str] = Counter()
    for weight, text in ((2, headline), (1, summary or "")):
        for stem in _stems(text):
            for topic, words in _KEYWORDS.items():
                if stem in words:
                    scores[topic] += weight
    if not scores:
        return None
    (best, score), *rest = scores.most_common()
    if score < _MIN_KEYWORD_SCORE or (rest and rest[0][1] == score):
        return None  # fraco ou empatado: melhor admitir que não sabe
    return best


def classify(url: str, categories: list[str] | tuple[str, ...] | None, headline: str,
             summary: str | None, foreign: bool = False) -> TopicResult:
    """`foreign`: veículo estrangeiro. Para ele, "world"/"americas"/"brazil" só dizem
    *onde* aconteceu; para o leitor brasileiro, a seção vem do conteúdo, se der."""
    for topic, source in ((from_categories(categories), "feed"), (from_url(url), "url")):
        if not topic:
            continue
        if foreign and topic in {"internacional", "brasil"} and (kw := from_keywords(headline, summary)):
            return TopicResult(kw, "keywords")
        return TopicResult(topic, source)
    if topic := from_keywords(headline, summary):
        return TopicResult(topic, "keywords")
    return TopicResult(OTHER, "none")


def majority_topic(topics: list[str]) -> str:
    """Seção da história: a mais comum entre as notícias, ignorando "outros".

    Empate: vale a da notícia mais antiga (a lista vem em ordem de publicação).
    """
    known = [t for t in topics if t and t != OTHER]
    if not known:
        return OTHER
    counts = Counter(known)
    top = max(counts.values())
    return next(t for t in known if counts[t] == top)
