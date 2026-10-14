"""Dados oficiais do Banco Central (Sistema Gerenciador de Séries Temporais, SGS).

API pública, sem chave: https://api.bcb.gov.br/dados/serie/bcdata.sgs.{código}/dados
Formato: [{"data": "dd/mm/aaaa", "valor": "13.75"}, ...] (ponto como decimal).

Séries usadas (códigos conferidos em 13/10/2026):
  432    Meta Selic definida pelo Copom (% a.a.), diária. ATENÇÃO: já traz datas
         futuras, até a próxima reunião; "valor atual" ignora datas depois de hoje.
  433    IPCA, variação mensal (%).
  13522  IPCA acumulado em 12 meses (%), mensal.
  24369  Taxa de desocupação, PNAD Contínua, trimestre móvel (%), mensal.
  1      Dólar, câmbio livre, venda (R$), diário.
  7326   PIB, variação real anual (%), uma observação por ano (data 01/01/aaaa).

plan() e compare() são puros (testáveis); fetch() faz a requisição.
"""

import calendar
import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.factcheck.parse import ParsedClaim
from app.factcheck.sources import EvidenceItem

log = logging.getLogger(__name__)

BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
USER_AGENT = "PolitiFactBR/0.6 (projeto pessoal; checagem de fatos)"
TIMEOUT = 20

SERIES = {
    432: "Meta Selic definida pelo Copom (% ao ano)",
    433: "IPCA, variação mensal (%)",
    13522: "IPCA acumulado em 12 meses (%)",
    24369: "Taxa de desocupação, PNAD Contínua, trimestre móvel (%)",
    1: "Dólar, câmbio livre, venda (R$)",
    7326: "PIB, variação real anual (%)",
}


class SourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class Plan:
    code: int
    start: date
    end: date
    mode: str  # point (um valor de referência) | range (qualquer valor no período)
    reference: str  # texto curto: o que está sendo comparado
    note: str | None = None


@dataclass(frozen=True)
class Point:
    day: date
    value: float


def _month_bounds(y: int, m: int) -> tuple[date, date]:
    return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])


def plan(p: ParsedClaim, today: date) -> Plan | str:
    """Que série e que intervalo consultar. Retorna o motivo (str) se não houver como."""
    if not p.checkable:
        return "afirmação fora da checagem automática"
    y, m = p.year, p.month
    if y is not None and y > today.year:
        return "o período citado ainda não aconteceu"
    recent = (today - timedelta(days=400), today)

    if p.indicator == "selic":
        if p.period == "month":
            return Plan(432, *_month_bounds(y, m), "range", f"meta Selic em {p.describe_period()}")
        if p.period == "year":
            return Plan(432, date(y, 1, 1), min(date(y, 12, 31), today), "range", f"meta Selic em {y}")
        return Plan(432, today - timedelta(days=45), today, "point", "meta Selic vigente hoje")

    if p.indicator == "ipca":
        if p.period == "month":
            code = 13522 if p.twelve_months else 433
            what = "IPCA acumulado em 12 meses" if p.twelve_months else "IPCA do mês"
            return Plan(code, *_month_bounds(y, m), "point", f"{what}, {p.describe_period()}")
        if p.period == "year":
            if y >= today.year:
                return "o ano citado ainda não terminou; a inflação anual só existe com dezembro divulgado"
            return Plan(13522, *_month_bounds(y, 12), "point", f"IPCA acumulado em {y} (12 meses até dezembro)")
        return Plan(13522, *recent, "point", "IPCA acumulado em 12 meses mais recente",
                    note=None if p.twelve_months else "sem período na afirmação: comparado ao acumulado em 12 meses")

    if p.indicator == "desemprego":
        if p.period == "month":
            return Plan(24369, *_month_bounds(y, m), "point",
                        f"desocupação no trimestre terminado em {p.describe_period()}")
        if p.period == "year":
            return Plan(24369, date(y, 1, 1), date(y, 12, 31), "range", f"desocupação ao longo de {y}")
        return Plan(24369, *recent, "point", "desocupação mais recente divulgada")

    if p.indicator == "dolar":
        if p.period == "month":
            return Plan(1, *_month_bounds(y, m), "range", f"dólar em {p.describe_period()}")
        if p.period == "year":
            return Plan(1, date(y, 1, 1), min(date(y, 12, 31), today), "range", f"dólar em {y}")
        return Plan(1, today - timedelta(days=10), today, "point", "dólar no último dia útil")

    if p.indicator == "pib":
        if p.period == "month":
            return "o PIB anual não tem valor mensal; cite o ano"
        if p.period == "year":
            return Plan(7326, date(y, 1, 1), date(y, 12, 31), "point", f"PIB de {y}")
        return Plan(7326, date(today.year - 3, 1, 1), today, "point", "PIB do último ano divulgado")

    return "indicador sem série configurada"


def url_for(pl: Plan) -> str:
    return (f"{BASE.format(code=pl.code)}?formato=json"
            f"&dataInicial={pl.start:%d/%m/%Y}&dataFinal={pl.end:%d/%m/%Y}")


def parse_response(payload: bytes) -> list[Point]:
    try:
        rows = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SourceError(f"resposta do Banco Central não é JSON: {payload[:120]!r}") from exc
    if not isinstance(rows, list):
        raise SourceError(f"resposta inesperada do Banco Central: {str(rows)[:120]}")
    points = []
    for r in rows:
        try:
            points.append(Point(datetime.strptime(r["data"], "%d/%m/%Y").date(), float(r["valor"])))
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(points, key=lambda pt: pt.day)


RETRY_WAITS = (1.0, 3.0)  # segundos antes da 2ª e da 3ª tentativa
_TRANSIENT = {429, 500, 502, 503, 504}


def _sleep(seconds: float) -> None:  # separado para os testes não esperarem
    time.sleep(seconds)


def fetch(pl: Plan) -> list[Point]:
    """Consulta o SGS. O serviço dá 502/503 esporádicos: tenta até 3 vezes em erros passageiros."""
    url = url_for(pl)
    last = "sem tentativa"
    for attempt in range(len(RETRY_WAITS) + 1):
        if attempt:
            _sleep(RETRY_WAITS[attempt - 1])
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return parse_response(resp.read(2_000_000))
        except urllib.error.HTTPError as exc:
            # O SGS responde 404 quando não há dado no intervalo.
            if exc.code == 404:
                return []
            last = f"Banco Central respondeu {exc.code}"
            if exc.code not in _TRANSIENT:
                raise SourceError(last) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = f"Banco Central inacessível: {exc}"
        log.warning("BCB %s (tentativa %d/%d)", last, attempt + 1, len(RETRY_WAITS) + 1)
    raise SourceError(f"{last} (após {len(RETRY_WAITS) + 1} tentativas)")


@dataclass(frozen=True)
class Comparison:
    outcome: str  # match | close | mismatch | no_data
    reference_value: float | None = None
    reference_min: float | None = None
    reference_max: float | None = None
    reference_day: date | None = None
    first_day: date | None = None
    last_day: date | None = None
    n_points: int = 0


def tolerance(decimals: int) -> float:
    """Arredondamento do número afirmado: "5%" cobre 4,5 a 5,5; "4,8%" cobre 4,75 a 4,85."""
    return 0.5 * 10 ** (-decimals)


def _classify(claimed: float, decimals: int, lo: float, hi: float) -> str:
    tol = tolerance(decimals) + 1e-9
    if lo - tol <= claimed <= hi + tol:
        return "match"
    gap = (lo - claimed) if claimed < lo else (claimed - hi)
    ref = max(abs(lo), abs(hi), 1e-9)
    if gap <= max(2 * tolerance(decimals), 0.10 * ref):
        return "close"
    return "mismatch"


def compare(p: ParsedClaim, pl: Plan, points: list[Point], today: date) -> Comparison:
    pts = [pt for pt in points if pl.start <= pt.day <= min(pl.end, today)]  # nunca datas futuras (série 432)
    if not pts or p.value is None:
        return Comparison("no_data")
    if pl.mode == "point":
        ref = pts[-1]
        return Comparison(_classify(p.value, p.decimals, ref.value, ref.value), reference_value=ref.value,
                          reference_day=ref.day, first_day=ref.day, last_day=ref.day, n_points=1)
    lo, hi = min(pt.value for pt in pts), max(pt.value for pt in pts)
    return Comparison(_classify(p.value, p.decimals, lo, hi), reference_min=lo, reference_max=hi,
                      first_day=pts[0].day, last_day=pts[-1].day, n_points=len(pts))


def fmt(v: float, unit: str | None, decimals: int | None = None) -> str:
    """Número no formato brasileiro. Com `decimals`, mantém as casas como foram escritas."""
    raw = f"{v:,.{decimals}f}" if decimals is not None else f"{v:,.4f}".rstrip("0").rstrip(".")
    s = raw.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}" if unit == "R$" else f"{s}%"


def to_evidence(p: ParsedClaim, pl: Plan, c: Comparison) -> EvidenceItem:
    name = SERIES[pl.code]
    if c.outcome == "no_data":
        passage = f"Nenhum dado da série {pl.code} ({name}) entre {pl.start:%d/%m/%Y} e {pl.end:%d/%m/%Y}."
        rel = "context"
    elif c.reference_value is not None:
        passage = (f"Série {pl.code} ({name}): {fmt(c.reference_value, p.unit)} "
                   f"em {c.reference_day:%d/%m/%Y}.")
        rel = "supports" if c.outcome == "match" else "contradicts"
    else:
        passage = (f"Série {pl.code} ({name}): entre {fmt(c.reference_min, p.unit)} e "
                   f"{fmt(c.reference_max, p.unit)} de {c.first_day:%d/%m/%Y} a {c.last_day:%d/%m/%Y} "
                   f"({c.n_points} observações).")
        rel = "supports" if c.outcome == "match" else "contradicts"
    return EvidenceItem(
        provider="bcb_sgs", source_type="official_data", source_url=url_for(pl),
        source_title=f"Banco Central, SGS {pl.code}: {name}", relevant_passage=passage, relationship=rel,
        verification_status="retrieved_by_system", published_at=c.last_day,
        data={
            "series": pl.code, "series_name": name, "mode": pl.mode, "reference": pl.reference, "note": pl.note,
            "start": pl.start.isoformat(), "end": pl.end.isoformat(), "outcome": c.outcome,
            "claimed": p.value, "claimed_decimals": p.decimals, "unit": p.unit,
            "reference_value": c.reference_value, "reference_min": c.reference_min,
            "reference_max": c.reference_max,
            "reference_day": c.reference_day.isoformat() if c.reference_day else None,
            "first_day": c.first_day.isoformat() if c.first_day else None,
            "last_day": c.last_day.isoformat() if c.last_day else None, "n_points": c.n_points,
        },
    )
