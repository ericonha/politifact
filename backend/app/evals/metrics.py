"""Métricas puras para a avaliação (sem rede, sem banco)."""

import math
from collections import Counter


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalo de confiança de Wilson para uma proporção. Com n pequeno ele é largo — de propósito."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, centre - half), min(1.0, centre + half)


def rate(k: int, n: int) -> dict:
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "value": (k / n) if n else None, "low": lo, "high": hi}


def confusion(pairs: list[tuple[str, str]], labels: list[str]) -> dict[str, dict[str, int]]:
    """pairs = [(esperado, previsto)]. Linhas: esperado; colunas: previsto."""
    out = {a: {b: 0 for b in labels} for a in labels}
    for exp, got in pairs:
        if exp in out and got in out[exp]:
            out[exp][got] += 1
    return out


def per_class(pairs: list[tuple[str, str]], labels: list[str]) -> dict[str, dict]:
    res = {}
    for lab in labels:
        tp = sum(1 for e, g in pairs if e == lab and g == lab)
        fp = sum(1 for e, g in pairs if e != lab and g == lab)
        fn = sum(1 for e, g in pairs if e == lab and g != lab)
        prec = tp / (tp + fp) if tp + fp else None
        rec = tp / (tp + fn) if tp + fn else None
        f1 = 2 * prec * rec / (prec + rec) if prec and rec else (0.0 if prec is not None and rec is not None else None)
        res[lab] = {"precision": prec, "recall": rec, "f1": f1, "support": tp + fn}
    return res


def macro_f1(per: dict[str, dict]) -> float | None:
    vals = [v["f1"] for v in per.values() if v["support"] and v["f1"] is not None]
    return sum(vals) / len(vals) if vals else None


def majority_baseline(expected: list[str]) -> float | None:
    if not expected:
        return None
    return Counter(expected).most_common(1)[0][1] / len(expected)


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    idx = min(len(s) - 1, max(0, round(q * (len(s) - 1))))
    return s[idx]
