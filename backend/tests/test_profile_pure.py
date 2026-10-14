from collections import Counter

from app.coverage.profile_math import average_share, fold, rate, tone_table


def test_average_is_per_outlet_not_pooled() -> None:
    per = {
        1: (Counter({"politica": 90}), 100),   # 90%
        2: (Counter({"politica": 1}), 10),     # 10%
        3: (Counter({"politica": 5}), 5),      # amostra pequena: fora
    }
    assert average_share(per, "politica") == 0.5
    assert average_share(per, "politica", exclude=1) == 0.1


def test_rate() -> None:
    assert rate([True, False, False, True]) == (0.5, 4)
    assert rate([]) == (None, 0)


def test_tone_table_groups_and_filters() -> None:
    rows = [("Lula", "negativo"), ("lula", "neutro"), ("Lúla", "neutro"), ("Moraes", "positivo"), ("x", "furioso")]
    t = tone_table(rows, min_n=2)
    assert t == [{"key": "lula", "name": "Lula", "n": 3, "negativo": 1, "neutro": 2, "positivo": 0, "incerto": 0}]


def test_fold() -> None:
    assert fold(" São Paulo ") == "sao paulo"
