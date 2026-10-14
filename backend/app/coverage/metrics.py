"""Cálculos puros de cobertura: períodos, buckets de tempo, lacunas de coleta.

Todas as datas de entrada e saída são "aware" (com fuso). Os buckets são
alinhados à meia-noite de São Paulo, que é como o usuário lê o dia.
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")

PRESETS = {"24h": timedelta(hours=24), "3d": timedelta(days=3), "7d": timedelta(days=7), "30d": timedelta(days=30)}
MAX_CUSTOM_DAYS = 90


class RangeError(ValueError):
    pass


@dataclass(frozen=True)
class Range:
    start: datetime
    end: datetime
    bucket: timedelta
    label: str

    @property
    def duration(self) -> timedelta:
        return self.end - self.start


def choose_bucket(duration: timedelta) -> timedelta:
    """Até 3 dias: por hora; até 15 dias: a cada 6 h; acima: por dia (no máximo ~90 pontos)."""
    if duration <= timedelta(days=3):
        return timedelta(hours=1)
    if duration <= timedelta(days=15):
        return timedelta(hours=6)
    return timedelta(days=1)


def resolve_range(
    window: str | None,
    date_from: date | None,
    date_to: date | None,
    now: datetime,
) -> Range:
    """Preset (24h/3d/7d) ou intervalo de datas inclusivo no horário de São Paulo."""
    if date_from or date_to:
        if not (date_from and date_to):
            raise RangeError("informe as duas datas (de e até)")
        if date_from > date_to:
            raise RangeError("a data inicial é depois da final")
        if (date_to - date_from).days + 1 > MAX_CUSTOM_DAYS:
            raise RangeError(f"período máximo é de {MAX_CUSTOM_DAYS} dias")
        start = datetime.combine(date_from, time.min, TZ)
        end = min(datetime.combine(date_to + timedelta(days=1), time.min, TZ), now)
        if end <= start:
            raise RangeError("o período escolhido ainda não começou")
        label = f"{date_from:%d/%m/%Y} a {date_to:%d/%m/%Y}"
        return Range(start.astimezone(UTC), end.astimezone(UTC), choose_bucket(end - start), label)

    window = window or "24h"
    if window not in PRESETS:
        raise RangeError(f"janela inválida: {window}")
    span = PRESETS[window]
    labels = {"24h": "últimas 24 horas", "3d": "últimos 3 dias", "7d": "últimos 7 dias", "30d": "últimos 30 dias"}
    return Range(now - span, now, choose_bucket(span), labels[window])


def bucket_origin(start: datetime) -> datetime:
    """Meia-noite (horário de SP) do dia de `start`."""
    local = start.astimezone(TZ)
    return datetime.combine(local.date(), time.min, TZ)


def bucket_starts(r: Range) -> list[datetime]:
    origin = bucket_origin(r.start)
    steps = int((r.start - origin) / r.bucket)
    first = origin + steps * r.bucket
    out = []
    t = first
    while t < r.end:
        out.append(t.astimezone(UTC))
        t += r.bucket
    return out


def bucket_index(t: datetime, starts: list[datetime], bucket: timedelta) -> int | None:
    if not starts or t < starts[0] or t >= starts[-1] + bucket:
        return None
    return int((t - starts[0]) / bucket)


def timeline(
    items: Iterable[tuple[int, datetime]],
    keys: list[int],
    r: Range,
) -> tuple[list[datetime], dict[int, list[int]]]:
    """Conta itens (chave, momento) por bucket. Buckets vazios viram zero, nunca somem."""
    starts = bucket_starts(r)
    series = {k: [0] * len(starts) for k in keys}
    for key, t in items:
        if key not in series:
            continue
        i = bucket_index(t, starts, r.bucket)
        if i is not None:
            series[key][i] += 1
    return starts, series


@dataclass(frozen=True)
class Gap:
    start: datetime
    end: datetime

    @property
    def hours(self) -> float:
        return (self.end - self.start).total_seconds() / 3600


def collection_gaps(
    run_times: Iterable[datetime],
    start: datetime,
    end: datetime,
    max_interval: timedelta,
) -> list[Gap]:
    """Intervalos maiores que `max_interval` sem nenhuma coleta bem-sucedida.

    Inclui o começo do período (se a primeira coleta demorou) e o fim (se a
    última coleta foi há muito tempo). Ausência de notícia nesses trechos não
    significa ausência de cobertura.
    """
    points = sorted(t for t in run_times if start <= t <= end)
    edges = [start, *points, end]
    gaps = []
    for a, b in zip(edges, edges[1:]):
        if b - a > max_interval:
            gaps.append(Gap(a, b))
    return gaps


def covered_fraction(gaps: list[Gap], start: datetime, end: datetime) -> float:
    total = (end - start).total_seconds()
    if total <= 0:
        return 1.0
    missing = sum((g.end - g.start).total_seconds() for g in gaps)
    return max(0.0, 1.0 - missing / total)


def reach_distribution(story_outlets: dict[int, set[int]]) -> dict[int, int]:
    """Quantas histórias foram cobertas por 1, 2, 3... veículos."""
    return dict(sorted(Counter(len(o) for o in story_outlets.values() if o).items()))


def exclusive_counts(story_outlets: dict[int, set[int]]) -> Counter[int]:
    """Histórias que só um veículo cobriu, por veículo."""
    c: Counter[int] = Counter()
    for outlets in story_outlets.values():
        if len(outlets) == 1:
            c[next(iter(outlets))] += 1
    return c
