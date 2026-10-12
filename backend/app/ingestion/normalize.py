"""Normalização de URLs, títulos e datas (etapa 2 do pipeline de ingestão)."""

import hashlib
import html
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Parâmetros de rastreamento que não mudam o conteúdo da página.
_TRACKING_PARAMS = {
    "fbclid", "gclid", "dclid", "msclkid", "igshid", "mc_cid", "mc_eid",
    "ref", "ref_src", "cmpid", "ocid", "at_medium", "at_campaign", "amp",
}
_TRACKING_PREFIXES = ("utm_", "at_", "xtor")

# Datas de publicação mais de 1 dia no futuro são tratadas como erro do feed.
MAX_FUTURE_SKEW = timedelta(days=1)


def canonical_url(url: str) -> str:
    """URL estável para deduplicação: https, host minúsculo, sem fragmento,
    sem parâmetros de rastreamento, sem barra final e sem sufixo /amp."""
    parts = urlsplit(url.strip())
    scheme = "https" if parts.scheme in ("http", "https", "") else parts.scheme
    host = (parts.hostname or "").lower()
    if parts.port and parts.port not in (80, 443):
        host = f"{host}:{parts.port}"

    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=False)
        if k.lower() not in _TRACKING_PARAMS and not k.lower().startswith(_TRACKING_PREFIXES)
    ]
    query.sort()

    path = re.sub(r"/{2,}", "/", parts.path or "/")
    path = re.sub(r"/amp/?$", "/", path)
    if len(path) > 1:
        path = path.rstrip("/")

    return urlunsplit((scheme, host, path, urlencode(query), ""))


def clean_text(value: str | None) -> str:
    """Remove tags HTML, decodifica entidades e colapsa espaços."""
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def normalize_headline(headline: str) -> str:
    """Forma comparável do título: sem acentos, minúscula, só letras e números."""
    text = unicodedata.normalize("NFKD", clean_text(headline))
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def content_hash(headline: str, summary: str | None = None) -> str:
    """Hash do conteúdo disponível (título + resumo normalizados).

    Usado na fase 3 para detectar republicações com URLs diferentes.
    """
    basis = normalize_headline(headline) + "\n" + normalize_headline(summary or "")
    return hashlib.sha256(basis.encode()).hexdigest()


def parse_date(value: str | None) -> datetime | None:
    """Aceita RFC 822 (RSS) e ISO 8601 (Atom). Retorna sempre em UTC, ou None."""
    if not value or not value.strip():
        return None
    value = value.strip()
    dt: datetime | None = None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        # Sem fuso informado: não dá para saber a hora real. Assume UTC e o
        # coletor registra isso como limitação do veículo.
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def sanitize_published_at(dt: datetime | None, now: datetime | None = None) -> datetime | None:
    """Descarta datas absurdas (muito no futuro). Nunca substitui por data de descoberta."""
    if dt is None:
        return None
    now = now or datetime.now(UTC)
    if dt > now + MAX_FUTURE_SKEW:
        return None
    return dt
