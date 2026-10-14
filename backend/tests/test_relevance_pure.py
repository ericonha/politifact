from datetime import UTC, datetime, timedelta

from app.relevance import relevance

NOW = datetime(2026, 10, 12, 22, tzinfo=UTC)


def test_reach_dominates() -> None:
    wide = relevance([1] * 10, 16, NOW, NOW)
    deep = relevance([20], 16, NOW, NOW)
    assert wide > deep


def test_one_outlet_cannot_inflate_volume() -> None:
    assert relevance([50], 16, NOW, NOW) == relevance([3], 16, NOW, NOW)


def test_recency_decays() -> None:
    fresh = relevance([1, 1, 1], 16, NOW, NOW)
    old = relevance([1, 1, 1], 16, NOW - timedelta(hours=24), NOW)
    assert fresh > old
    assert fresh - old < 15.1  # recência pesa no máximo 15 pontos


def test_bounds() -> None:
    assert relevance([], 16, NOW, NOW) == 0.0
    assert relevance([3] * 16, 16, NOW, NOW) == 100.0
