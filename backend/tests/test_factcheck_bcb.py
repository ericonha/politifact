"""Série oficial: plano de consulta e comparação (sem rede)."""

from datetime import date

import pytest

from app.factcheck.parse import parse
from app.factcheck.sources import bcb
from app.factcheck.sources.bcb import Plan, Point, compare, fmt, parse_response, plan, to_evidence, url_for

TODAY = date(2026, 10, 13)


def test_parse_response_and_future_dates_are_ignored() -> None:
    # Formato real da API (série 432 traz datas futuras, até a próxima reunião do Copom).
    pts = parse_response(b'[{"data":"10/10/2026","valor":"13.75"},{"data":"02/11/2026","valor":"13.75"},'
                         b'{"data":"xx","valor":"1"}]')
    assert [p.day for p in pts] == [date(2026, 10, 10), date(2026, 11, 2)]
    p = parse("A Selic está em 13,75%")
    pl = plan(p, TODAY)
    c = compare(p, pl, pts, TODAY)
    assert c.reference_day == date(2026, 10, 10) and c.outcome == "match"


@pytest.mark.parametrize(
    ("text", "code", "mode"),
    [
        ("A Selic está em 13,75%", 432, "point"),
        ("A Selic foi de 15% em 2025", 432, "range"),
        ("A inflação de setembro de 2026 foi 0,82%", 433, "point"),
        ("A inflação de 12 meses em setembro de 2026 foi 4,58%", 13522, "point"),
        ("A inflação de 2025 foi de 4,26%", 13522, "point"),
        ("A inflação está em 4,5%", 13522, "point"),
        ("O desemprego foi 5,3% em agosto de 2026", 24369, "point"),
        ("O dólar chegou a R$ 6,10 em 2025", 1, "range"),
        ("O PIB cresceu 3,4% em 2024", 7326, "point"),
    ],
)
def test_plan_picks_series(text, code, mode) -> None:
    pl = plan(parse(text), TODAY)
    assert isinstance(pl, Plan), pl
    assert (pl.code, pl.mode) == (code, mode)


def test_plan_refuses_incomplete_year_and_future() -> None:
    assert isinstance(plan(parse("A inflação de 2026 foi de 4%"), TODAY), str)
    assert isinstance(plan(parse("A Selic será 10% em 2027"), TODAY), str)
    assert isinstance(plan(parse("O PIB de março de 2026 foi 1%"), TODAY), str)


def _cmp(text: str, points: list[tuple[date, float]]):
    p = parse(text)
    pl = plan(p, TODAY)
    return compare(p, pl, [Point(d, v) for d, v in points], TODAY)


def test_rounding_tolerance_by_claimed_precision() -> None:
    pts = [(date(2025, 12, 1), 4.26)]
    assert _cmp("A inflação de 2025 foi de 4,3%", pts).outcome == "match"     # 4,25..4,35
    assert _cmp("A inflação de 2025 foi de 4%", pts).outcome == "match"       # 3,5..4,5
    assert _cmp("A inflação de 2025 foi de 4,5%", pts).outcome == "close"     # 0,24 acima, < 10%
    assert _cmp("A inflação de 2025 foi de 6%", pts).outcome == "mismatch"


def test_range_mode_accepts_any_value_in_period() -> None:
    pts = [(date(2025, 1, 2), 12.25), (date(2025, 6, 20), 15.0), (date(2025, 12, 30), 15.0)]
    c = _cmp("A Selic foi de 15% em 2025", pts)
    assert c.outcome == "match" and (c.reference_min, c.reference_max) == (12.25, 15.0)
    assert _cmp("A Selic foi de 20% em 2025", pts).outcome == "mismatch"


def test_no_data() -> None:
    assert _cmp("A inflação de 2025 foi de 4%", []).outcome == "no_data"


def test_negative_values() -> None:
    pts = [(date(2026, 8, 1), -0.32)]
    assert _cmp("Houve deflação de 0,32% em agosto de 2026", pts).outcome == "match"
    assert _cmp("A inflação de agosto de 2026 foi de 0,32%", pts).outcome == "mismatch"


def test_evidence_text_and_url() -> None:
    p = parse("O dólar fechou a R$ 4,99 hoje")
    pl = plan(p, TODAY)
    c = compare(p, pl, [Point(date(2026, 10, 9), 4.9892)], TODAY)
    ev = to_evidence(p, pl, c)
    assert ev.relationship == "supports" and "R$ 4,9892" in ev.relevant_passage
    assert url_for(pl).startswith("https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados?formato=json")
    assert fmt(13.75, "%") == "13,75%" and fmt(5.0, "%") == "5%"


# --- fetch: novas tentativas em erros passageiros -----------------------------------------

def _plan():
    return bcb.Plan(code=432, start=date(2026, 8, 29), end=date(2026, 10, 13), mode="point", reference="x", note=None)


class _Resp:
    def __init__(self, body: bytes):
        self.body = body

    def read(self, n=-1):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http(code):
    import urllib.error
    return urllib.error.HTTPError("u", code, "x", {}, None)


def _fetch_with(monkeypatch, outcomes):
    import urllib.request
    calls = {"n": 0}

    def fake(req, timeout=None):
        o = outcomes[min(calls["n"], len(outcomes) - 1)]
        calls["n"] += 1
        if isinstance(o, Exception):
            raise o
        return _Resp(o)

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    monkeypatch.setattr(bcb, "_sleep", lambda s: None)
    return calls


def test_fetch_retries_on_502_then_succeeds(monkeypatch) -> None:
    calls = _fetch_with(monkeypatch, [_http(502), b'[{"data": "10/10/2026", "valor": "13.75"}]'])
    pts = bcb.fetch(_plan())
    assert calls["n"] == 2 and pts[0].value == 13.75


def test_fetch_gives_up_after_three_attempts(monkeypatch) -> None:
    calls = _fetch_with(monkeypatch, [_http(502)])
    with pytest.raises(bcb.SourceError) as e:
        bcb.fetch(_plan())
    assert calls["n"] == 3 and "502" in str(e.value) and "3 tentativas" in str(e.value)


def test_fetch_does_not_retry_on_client_error(monkeypatch) -> None:
    calls = _fetch_with(monkeypatch, [_http(400)])
    with pytest.raises(bcb.SourceError):
        bcb.fetch(_plan())
    assert calls["n"] == 1


def test_fetch_404_means_no_data(monkeypatch) -> None:
    assert _fetch_with(monkeypatch, [_http(404)]) and bcb.fetch(_plan()) == []
