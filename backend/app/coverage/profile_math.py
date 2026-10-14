"""Cálculos puros do perfil de um veículo (comparado à média dos outros).

"Média dos veículos" é a média SIMPLES entre veículos (cada veículo pesa igual),
não o total somado: assim os veículos que publicam muito não definem a média.
Veículos com poucas notícias no período ficam fora da média (amostra pequena).
"""

import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable

MIN_ARTICLES_FOR_AVERAGE = 10
TONES = ("negativo", "neutro", "positivo", "incerto")


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).lower().strip()


def shares(counts: Counter, total: int) -> dict[str, float]:
    return {k: v / total for k, v in counts.items()} if total else {}


def average_share(per_outlet: dict[int, tuple[Counter, int]], key: str, exclude: int | None = None) -> float | None:
    """Média simples, entre veículos com amostra suficiente, da fração `key`."""
    values = [
        counts.get(key, 0) / total
        for oid, (counts, total) in per_outlet.items()
        if oid != exclude and total >= MIN_ARTICLES_FOR_AVERAGE
    ]
    return sum(values) / len(values) if values else None


def rate(flags: Iterable[bool]) -> tuple[float | None, int]:
    flags = list(flags)
    return (sum(flags) / len(flags) if flags else None), len(flags)


def tone_table(rows: Iterable[tuple[str, str]], min_n: int = 3, top: int = 8) -> list[dict]:
    """rows: (nome do ator como o modelo escreveu, tom validado). Agrupa por nome normalizado."""
    by_key: dict[str, Counter] = defaultdict(Counter)
    display: dict[str, str] = {}
    for name, tone in rows:
        key = fold(name)
        if not key:
            continue
        display.setdefault(key, name)
        by_key[key][tone if tone in TONES else "incerto"] += 1
    table = [
        {"key": k, "name": display[k], "n": sum(c.values()), **{t: c.get(t, 0) for t in TONES}}
        for k, c in by_key.items()
        if sum(c.values()) >= min_n
    ]
    table.sort(key=lambda r: (-r["n"], r["name"]))
    return table[:top]
