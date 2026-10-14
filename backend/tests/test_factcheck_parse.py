"""Leitura das afirmações (sem banco, sem rede)."""

import pytest

from app.factcheck.parse import parse


@pytest.mark.parametrize(
    ("text", "indicator", "value", "decimals", "period", "year", "month"),
    [
        ("A Selic está em 13,75% ao ano.", "selic", 13.75, 2, "latest", None, None),
        ("A inflação de 2025 foi de 4,26%.", "ipca", 4.26, 2, "year", 2025, None),
        ("A inflação de setembro de 2026 foi 0,82%", "ipca", 0.82, 2, "month", 2026, 9),
        ("O desemprego caiu para 5,3% em agosto de 2026", "desemprego", 5.3, 1, "month", 2026, 8),
        ("O dólar fechou a R$ 4,99 hoje", "dolar", 4.99, 2, "latest", None, None),
        ("O PIB cresceu 3% em 2024", "pib", 3.0, 0, "year", 2024, None),
        ("Houve deflação de 0,32% em agosto de 2026", "ipca", -0.32, 2, "month", 2026, 8),
        ("O PIB teve queda de 3,3% em 2020", "pib", -3.3, 1, "year", 2020, None),
        ("O PIB caiu 3,5% em 2020", "pib", -3.5, 1, "year", 2020, None),  # achado pela avaliação (o18)
        ("O PIB recuou cerca de 4% em 2020", "pib", -4.0, 0, "year", 2020, None),
        ("A taxa básica de juros é de 14 por cento", "selic", 14.0, 0, "latest", None, None),
    ],
)
def test_parse_values(text, indicator, value, decimals, period, year, month) -> None:
    p = parse(text)
    assert (p.indicator, p.value, p.decimals, p.period, p.year, p.month) == (
        indicator, value, decimals, period, year, month)
    assert p.checkable, p.problems


def test_twelve_months_flag() -> None:
    p = parse("A inflação acumulada em 12 meses está em 4,58%")
    assert p.indicator == "ipca" and p.twelve_months and p.period == "latest"


def test_direction_only_is_not_checkable() -> None:
    p = parse("O desemprego caiu no governo atual")
    assert p.direction_only and not p.checkable


def test_uncovered_claim() -> None:
    p = parse("O presidente viajou à China na semana passada")
    assert p.indicator is None and not p.checkable


def test_two_indicators_is_flagged() -> None:
    p = parse("A Selic está em 13,75% e a inflação em 4,5%")
    assert not p.checkable
    assert any("mais de um indicador" in x for x in p.problems)


def test_two_years_is_flagged() -> None:
    p = parse("A inflação foi de 4% entre 2023 e 2025")
    assert not p.checkable


def test_percent_like_year_is_not_a_year() -> None:
    p = parse("O dólar subiu 2025% ")  # absurdo, mas não pode virar o ano 2025
    assert p.year is None


def test_period_description() -> None:
    assert parse("A inflação de março de 2026 foi 0,5%").describe_period() == "março de 2026"


def test_year_to_date_inflation_is_not_treated_as_twelve_months() -> None:
    p = parse("A inflação acumulada no ano está em 3,1%")
    assert not p.twelve_months and not p.checkable
