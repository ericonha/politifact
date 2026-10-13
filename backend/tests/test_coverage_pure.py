"""Testes dos cálculos de cobertura (sem banco)."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.coverage.metrics import (
    Range,
    RangeError,
    bucket_starts,
    choose_bucket,
    collection_gaps,
    covered_fraction,
    exclusive_counts,
    reach_distribution,
    resolve_range,
    timeline,
)

NOW = datetime(2026, 10, 12, 23, 30, tzinfo=UTC)  # 20:30 em São Paulo


def test_presets() -> None:
    r = resolve_range("24h", None, None, NOW)
    assert r.end == NOW and r.duration == timedelta(hours=24)
    assert r.bucket == timedelta(hours=1)
    assert resolve_range("7d", None, None, NOW).bucket == timedelta(hours=6)


def test_custom_range_is_inclusive_in_sao_paulo_time() -> None:
    r = resolve_range(None, date(2026, 10, 1), date(2026, 10, 2), NOW)
    assert r.start == datetime(2026, 10, 1, 3, 0, tzinfo=UTC)  # 00:00 em SP
    assert r.end == datetime(2026, 10, 3, 3, 0, tzinfo=UTC)
    assert r.label == "01/10/2026 a 02/10/2026"


def test_custom_range_is_capped_at_now() -> None:
    r = resolve_range(None, date(2026, 10, 12), date(2026, 10, 12), NOW)
    assert r.end == NOW


@pytest.mark.parametrize(
    ("window", "date_from", "date_to"),
    [
        ("1y", None, None),
        (None, date(2026, 10, 2), None),
        (None, date(2026, 10, 5), date(2026, 10, 1)),
        (None, date(2026, 1, 1), date(2026, 10, 1)),
        (None, date(2026, 11, 1), date(2026, 11, 2)),
    ],
)
def test_invalid_ranges(window, date_from, date_to) -> None:
    with pytest.raises(RangeError):
        resolve_range(window, date_from, date_to, NOW)


def test_choose_bucket() -> None:
    assert choose_bucket(timedelta(days=3)) == timedelta(hours=1)
    assert choose_bucket(timedelta(days=10)) == timedelta(hours=6)
    assert choose_bucket(timedelta(days=30)) == timedelta(days=1)


def test_buckets_align_to_sao_paulo_midnight() -> None:
    r = Range(
        datetime(2026, 10, 12, 4, 20, tzinfo=UTC),  # 01:20 em SP
        datetime(2026, 10, 13, 4, 20, tzinfo=UTC),
        timedelta(hours=6),
        "x",
    )
    starts = bucket_starts(r)
    # 00:00 SP = 03:00 UTC; buckets às 00, 06, 12, 18 de SP
    assert starts[0] == datetime(2026, 10, 12, 3, 0, tzinfo=UTC)
    assert starts[1] == datetime(2026, 10, 12, 9, 0, tzinfo=UTC)
    assert starts[-1] < r.end


def test_timeline_fills_zeros_and_ignores_out_of_range() -> None:
    r = Range(datetime(2026, 10, 12, 3, tzinfo=UTC), datetime(2026, 10, 12, 6, tzinfo=UTC),
              timedelta(hours=1), "x")
    items = [
        (1, datetime(2026, 10, 12, 3, 10, tzinfo=UTC)),
        (1, datetime(2026, 10, 12, 3, 50, tzinfo=UTC)),
        (2, datetime(2026, 10, 12, 5, 0, tzinfo=UTC)),
        (2, datetime(2026, 10, 12, 9, 0, tzinfo=UTC)),  # fora
        (9, datetime(2026, 10, 12, 4, 0, tzinfo=UTC)),  # veículo desconhecido
    ]
    starts, series = timeline(items, [1, 2], r)
    assert len(starts) == 3
    assert series == {1: [2, 0, 0], 2: [0, 0, 1]}


def test_collection_gaps_include_edges() -> None:
    s = datetime(2026, 10, 12, 0, tzinfo=UTC)
    e = s + timedelta(hours=6)
    runs = [s + timedelta(minutes=10), s + timedelta(minutes=40), s + timedelta(hours=4)]
    gaps = collection_gaps(runs, s, e, timedelta(hours=1))
    assert [(g.start, g.end) for g in gaps] == [
        (s + timedelta(minutes=40), s + timedelta(hours=4)),
        (s + timedelta(hours=4), e),
    ]
    assert covered_fraction(gaps, s, e) == pytest.approx(1 - (200 / 60 + 2) / 6)


def test_no_runs_means_all_gap() -> None:
    s = datetime(2026, 10, 12, tzinfo=UTC)
    gaps = collection_gaps([], s, s + timedelta(hours=3), timedelta(hours=1))
    assert covered_fraction(gaps, s, s + timedelta(hours=3)) == 0.0


def test_reach_and_exclusives() -> None:
    stories = {10: {1, 2, 3}, 11: {1}, 12: {2}, 13: {1}, 14: {1, 3}, 15: set()}
    assert reach_distribution(stories) == {1: 3, 2: 1, 3: 1}
    assert exclusive_counts(stories) == {1: 2, 2: 1}
