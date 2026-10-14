"""Leitura determinística de uma afirmação: indicador, valor afirmado e período.

Cobre afirmações de NÍVEL ou VARIAÇÃO de cinco indicadores com dados públicos do
Banco Central (SGS). Afirmações de direção ("o desemprego caiu") ou comparação
("o maior desde 2015") são reconhecidas, mas ficam fora da checagem automática.
"""

import re
import unicodedata
from dataclasses import dataclass, field

MONTHS = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}


@dataclass(frozen=True)
class Indicator:
    key: str
    label: str
    unit: str  # "%" ou "R$"
    pattern: re.Pattern


INDICATORS = [
    Indicator("selic", "Selic (meta)", "%",
              re.compile(r"\bselic\b|taxa basica de juros|juros basicos")),
    Indicator("ipca", "Inflação (IPCA)", "%", re.compile(r"\binflacao\b|\bipca\b|\bdeflacao\b")),
    Indicator("desemprego", "Desemprego (desocupação)", "%",
              re.compile(r"\bdesemprego\b|\bdesocupacao\b|taxa de desocupacao")),
    Indicator("dolar", "Dólar (R$ por US$)", "R$", re.compile(r"\bdolar\b")),
    Indicator("pib", "PIB (variação real anual)", "%", re.compile(r"\bpib\b|produto interno bruto")),
]
BY_KEY = {i.key: i for i in INDICATORS}

_DIRECTION = re.compile(
    r"\b(subiu|subiram|caiu|cairam|aumentou|aumentaram|diminuiu|diminuiram|dobrou|triplicou|"
    r"maior|menor|recorde|pior|melhor|mais alt[oa]|mais baix[oa]|nunca)\b"
)
_NEGATIVE_BEFORE = re.compile(r"(queda|recuo|retracao|deflacao|encolheu|contracao)\s+(de\s+)?$")
_TWELVE_MONTHS = re.compile(r"\b(12|doze) meses\b")
# "Acumulado no ano" (janeiro até o mês) não tem série configurada: fica fora da checagem.
_YEAR_TO_DATE = re.compile(r"\bacumulad[oa] (no|neste|deste) ano\b|\bno acumulado do ano\b")
_LATEST = re.compile(r"\b(hoje|atual(mente)?|agora|neste momento|esta em|estao em|e de)\b")


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def _to_float(s: str) -> tuple[float, int]:
    """'1.234,56' / '4,8' / '13.75' -> (valor, casas decimais afirmadas)."""
    s = s.strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    decimals = len(s.split(".")[1]) if "." in s else 0
    return float(s), decimals


@dataclass
class ParsedClaim:
    indicator: str | None = None
    value: float | None = None
    decimals: int = 0
    unit: str | None = None
    period: str = "latest"  # latest | year | month
    year: int | None = None
    month: int | None = None
    twelve_months: bool = False
    direction_only: bool = False
    problems: list[str] = field(default_factory=list)

    @property
    def checkable(self) -> bool:
        """Dá para checar automaticamente contra uma série oficial."""
        return self.indicator is not None and self.value is not None and not self.problems

    @property
    def label(self) -> str | None:
        return BY_KEY[self.indicator].label if self.indicator else None

    def describe_period(self) -> str:
        if self.period == "month":
            name = next(k for k, v in MONTHS.items() if v == self.month)
            name = "março" if name == "marco" else name
            return f"{name} de {self.year}" + (" (acumulado em 12 meses)" if self.twelve_months else "")
        if self.period == "year":
            return str(self.year)
        return "valor mais recente" + (" (acumulado em 12 meses)" if self.twelve_months else "")

    def to_dict(self) -> dict:
        return {
            "indicator": self.indicator, "indicator_label": self.label, "value": self.value,
            "decimals": self.decimals, "unit": self.unit, "period": self.period, "year": self.year,
            "month": self.month, "twelve_months": self.twelve_months, "direction_only": self.direction_only,
            "period_label": self.describe_period(), "checkable": self.checkable, "problems": self.problems,
        }


def _find_value(text: str, unit: str) -> tuple[float, int, int] | None:
    """Primeiro valor da unidade certa: (valor, casas decimais, posição)."""
    if unit == "R$":
        m = re.search(r"r\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:[.,]\d+)?)", text) or \
            re.search(r"(\d+(?:[.,]\d+)?)\s*reais", text)
    else:
        m = re.search(r"(-?\d+(?:[.,]\d+)?)\s*(%|por cento|pontos? percentua)", text)
    if not m:
        return None
    value, decimals = _to_float(m.group(1))
    return value, decimals, m.start(1)


def parse(claim: str) -> ParsedClaim:
    t = fold(claim)
    p = ParsedClaim()

    found = [(m.start(), ind) for ind in INDICATORS if (m := ind.pattern.search(t))]
    if not found:
        p.problems.append("não fala de um indicador coberto pela checagem automática")
        return p
    if len({ind.key for _, ind in found}) > 1:
        p.problems.append("fala de mais de um indicador; separe em afirmações diferentes")
    ind = min(found)[1]
    p.indicator, p.unit = ind.key, ind.unit

    # Período
    month = re.search(r"\b(" + "|".join(MONTHS) + r")\s+(de\s+)?((?:19|20)\d{2})\b", t)
    if month:
        p.period, p.month, p.year = "month", MONTHS[month.group(1)], int(month.group(3))
    else:
        years = re.findall(r"\b((?:19|20)\d{2})\b(?!\s*%)", t)
        if years:
            p.period, p.year = "year", int(years[0])
            if len(set(years)) > 1:
                p.problems.append("cita mais de um ano; a checagem automática compara um período por vez")
    p.twelve_months = bool(_TWELVE_MONTHS.search(t))
    if ind.key == "ipca" and _YEAR_TO_DATE.search(t):
        p.problems.append("inflação acumulada no ano ainda não é coberta pela checagem automática")

    # Valor
    v = _find_value(t, ind.unit)
    if v is None:
        if _DIRECTION.search(t):
            p.direction_only = True
            p.problems.append("afirma uma direção ou comparação, não um valor; fora da checagem automática")
        else:
            p.problems.append("não traz um valor numérico para comparar")
        return p
    value, decimals, pos = v
    if ind.key in ("ipca", "pib") and _NEGATIVE_BEFORE.search(t[:pos]) and value > 0:
        value = -value
    if ind.key == "ipca" and "deflacao" in t and value > 0:
        value = -value
    p.value, p.decimals = value, decimals
    return p
