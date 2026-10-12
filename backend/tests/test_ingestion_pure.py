"""Testes das funções puras de ingestão: não precisam de banco nem de rede."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.ingestion.normalize import (
    canonical_url,
    clean_text,
    content_hash,
    normalize_headline,
    parse_date,
    sanitize_published_at,
)
from app.ingestion.rss import FeedParseError, parse_feed

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("http://WWW.Exemplo.com.br/a/b/?utm_source=x&id=2#top", "https://www.exemplo.com.br/a/b?id=2"),
        ("https://exemplo.com.br/a/amp/", "https://exemplo.com.br/a"),
        ("https://exemplo.com.br/a?b=2&a=1&fbclid=z", "https://exemplo.com.br/a?a=1&b=2"),
        ("https://exemplo.com.br", "https://exemplo.com.br/"),
        ("https://exemplo.com.br//x//y/", "https://exemplo.com.br/x/y"),
    ],
)
def test_canonical_url(raw: str, expected: str) -> None:
    assert canonical_url(raw) == expected


def test_clean_text_strips_tags_and_entities() -> None:
    assert clean_text("<p>A &amp; B</p>\n  <b>c</b>") == "A & B c"


def test_normalize_headline_ignores_accents_and_punctuation() -> None:
    assert normalize_headline("Câmara APROVA: reforma!") == normalize_headline("camara aprova reforma")


def test_content_hash_stable() -> None:
    assert content_hash("Título", "Resumo") == content_hash("titulo", "resumo")
    assert content_hash("Título", "Resumo") != content_hash("Título", "Outro")


def test_parse_date_formats() -> None:
    assert parse_date("Mon, 12 Oct 2026 15:59:37 +0000") == datetime(2026, 10, 12, 15, 59, 37, tzinfo=UTC)
    assert parse_date("2026-10-12T12:00:00-03:00") == datetime(2026, 10, 12, 15, 0, tzinfo=UTC)
    assert parse_date("2026-10-12T09:30:00Z") == datetime(2026, 10, 12, 9, 30, tzinfo=UTC)
    assert parse_date("não é data") is None
    assert parse_date("") is None


def test_sanitize_rejects_far_future_but_keeps_none() -> None:
    now = datetime(2026, 10, 12, tzinfo=UTC)
    assert sanitize_published_at(datetime(2026, 12, 1, tzinfo=UTC), now) is None
    assert sanitize_published_at(datetime(2026, 10, 12, 1, tzinfo=UTC), now) is not None
    assert sanitize_published_at(None, now) is None


def test_parse_rss2() -> None:
    entries = parse_feed((FIXTURES / "rss2.xml").read_bytes())
    assert [e.title for e in entries] == [
        "Câmara aprova projeto & segue ao Senado",
        "Notícia sem data",
        "Data no formato Dublin Core",
    ]
    first = entries[0]
    assert first.summary == "Resumo curto da matéria."
    assert "NÃO deve ser guardado" not in (first.summary or "")
    assert first.published_at == datetime(2026, 10, 12, 15, 59, 37, tzinfo=UTC)
    assert entries[1].published_at is None
    assert entries[2].published_at == datetime(2026, 10, 12, 15, 0, tzinfo=UTC)


def test_parse_atom_prefers_alternate_link() -> None:
    (entry,) = parse_feed((FIXTURES / "atom.xml").read_bytes())
    assert entry.link == "https://exemplo.org/economia/inflacao#comentarios"
    assert entry.published_at == datetime(2026, 10, 12, 9, 30, tzinfo=UTC)
    assert entry.updated_at == datetime(2026, 10, 12, 11, 0, tzinfo=UTC)


def test_parse_feed_rejects_html() -> None:
    with pytest.raises(FeedParseError):
        parse_feed(b"<html><body>not a feed</body></html>")
    with pytest.raises(FeedParseError):
        parse_feed(b"<<<")
