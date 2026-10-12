"""Parser de RSS 2.0 e Atom usando só a biblioteca padrão.

Guardamos apenas título, link, datas e um resumo curto. O texto completo
(content:encoded) é ignorado de propósito: armazenar matérias inteiras
depende de licença do veículo (seção 15 do plano).
"""

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
        entries.append(FeedEntry(title, link, guid, published, None, summary))
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
        entries.append(
            FeedEntry(title, link, _text(entry.find(f"{_ATOM}id")), published, updated, summary)
        )
    return entries


def parse_feed(data: bytes) -> list[FeedEntry]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise FeedParseError(f"XML inválido: {exc}") from exc

    if root.tag == "rss":
        channel = root.find("channel")
        if channel is None:
            raise FeedParseError("RSS sem <channel>")
        return _rss_items(channel)
    if root.tag == f"{_ATOM}feed":
        return _atom_entries(root)
    raise FeedParseError(f"Formato não reconhecido: <{root.tag}>")
