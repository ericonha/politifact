"""Parser de RSS 2.0 e Atom usando só a biblioteca padrão.

Guardamos apenas título, link, datas e um resumo curto. O texto completo
(content:encoded) é ignorado de propósito: armazenar matérias inteiras
depende de licença do veículo (seção 15 do plano).
"""

import re
from dataclasses import dataclass
from datetime import datetime
from xml.etree import ElementTree as ET

from app.ingestion.normalize import clean_text, parse_date, truncate

SUMMARY_LIMIT = 500

_ATOM = "{http://www.w3.org/2005/Atom}"
_DC = "{http://purl.org/dc/elements/1.1/}"


class FeedParseError(ValueError):
    pass


@dataclass(frozen=True)
class FeedEntry:
    title: str
    link: str
    guid: str | None
    published_at: datetime | None
    updated_at: datetime | None
    summary: str | None
    categories: tuple[str, ...] = ()


def _text(el: ET.Element | None) -> str | None:
    if el is None or el.text is None:
        return None
    return el.text.strip() or None


def _rss_items(channel: ET.Element) -> list[FeedEntry]:
    entries = []
    for item in channel.findall("item"):
        title = clean_text(_text(item.find("title")))
        link = _text(item.find("link"))
        guid = _text(item.find("guid"))
        if not link and guid and guid.startswith("http"):
            link = guid
        if not title or not link:
            continue
        published = parse_date(_text(item.find("pubDate")) or _text(item.find(f"{_DC}date")))
        summary = truncate(clean_text(_text(item.find("description"))), SUMMARY_LIMIT) or None
        categories = tuple(c for c in (clean_text(_text(el)) for el in item.findall("category")) if c)
        entries.append(FeedEntry(title, link, guid, published, None, summary, categories))
    return entries


def _atom_link(entry: ET.Element) -> str | None:
    fallback = None
    for link in entry.findall(f"{_ATOM}link"):
        href = link.get("href")
        if not href:
            continue
        if link.get("rel", "alternate") == "alternate":
            return href.strip()
        fallback = fallback or href.strip()
    return fallback


def _atom_entries(feed: ET.Element) -> list[FeedEntry]:
    entries = []
    for entry in feed.findall(f"{_ATOM}entry"):
        title = clean_text(_text(entry.find(f"{_ATOM}title")))
        link = _atom_link(entry)
        if not title or not link:
            continue
        published = parse_date(_text(entry.find(f"{_ATOM}published")))
        updated = parse_date(_text(entry.find(f"{_ATOM}updated")))
        raw_summary = _text(entry.find(f"{_ATOM}summary"))
        summary = truncate(clean_text(raw_summary), SUMMARY_LIMIT) or None
        categories = tuple(
            c for c in (clean_text(el.get("label") or el.get("term")) for el in entry.findall(f"{_ATOM}category")) if c
        )
        entries.append(
            FeedEntry(title, link, _text(entry.find(f"{_ATOM}id")), published, updated, summary, categories)
        )
    return entries


# Prefixos comuns em feeds que às vezes são usados sem declarar o namespace
# (ex.: <media:content> sem xmlns:media). O XML fica inválido, mas o conteúdo é bom.
_KNOWN_NAMESPACES = {
    "media": "http://search.yahoo.com/mrss/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "atom": "http://www.w3.org/2005/Atom",
    "sy": "http://purl.org/rss/1.0/modules/syndication/",
    "slash": "http://purl.org/rss/1.0/modules/slash/",
    "wfw": "http://wellformedweb.org/CommentAPI/",
    "georss": "http://www.georss.org/georss",
}


def _declare_missing_namespaces(data: bytes) -> bytes:
    """Declara no elemento raiz os prefixos conhecidos usados sem declaração."""
    m = re.search(rb"<(rss|feed)\b[^>]*>", data)
    if not m:
        return data
    root_tag = m.group(0)
    used = set(re.findall(rb"</?([a-zA-Z][\w-]*):[a-zA-Z]", data))
    extra = b"".join(
        b' xmlns:' + p + b'="' + _KNOWN_NAMESPACES[p.decode()].encode() + b'"'
        for p in sorted(used)
        if p.decode() in _KNOWN_NAMESPACES and b"xmlns:" + p + b"=" not in root_tag
    )
    if not extra:
        return data
    return data[: m.end() - 1] + extra + data[m.end() - 1 :]


def parse_feed(data: bytes) -> list[FeedEntry]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        if "unbound prefix" not in str(exc):
            raise FeedParseError(f"XML inválido: {exc}") from exc
        try:
            root = ET.fromstring(_declare_missing_namespaces(data))
        except ET.ParseError as exc2:
            raise FeedParseError(f"XML inválido: {exc2}") from exc2

    if root.tag == "rss":
        channel = root.find("channel")
        if channel is None:
            raise FeedParseError("RSS sem <channel>")
        return _rss_items(channel)
    if root.tag == f"{_ATOM}feed":
        return _atom_entries(root)
    raise FeedParseError(f"Formato não reconhecido: <{root.tag}>")
