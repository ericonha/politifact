"""Nota de relevância de uma história (0 a 100), transparente e sem IA.

O RSS não diz audiência nem posição na capa, então a relevância é estimada com:
- alcance (60%): quantos veículos cobriram, sobre os veículos ativos;
- volume (25%): quantas notícias, contando no máximo 3 por veículo (um veículo
  que publica muito não "infla" a história sozinho), em escala logarítmica;
- recência (15%): perde metade do peso a cada ~8 h desde a última notícia.
A seção não entra na nota: dar mais peso a Política que a Cultura seria uma
escolha editorial embutida no sistema.
"""

import math
from datetime import datetime

W_REACH, W_VOLUME, W_RECENCY = 0.60, 0.25, 0.15
PER_OUTLET_CAP = 3
VOLUME_SATURATION = 20  # notícias (já limitadas) para atingir o volume máximo
HALF_LIFE_HOURS = 8.0


def relevance(
    outlet_counts: list[int],
    active_outlets: int,
    last_seen: datetime | None,
    now: datetime,
) -> float:
    """outlet_counts: notícias de cada veículo que cobriu a história."""
    if not outlet_counts or active_outlets <= 0:
        return 0.0
    reach = min(1.0, len(outlet_counts) / active_outlets)
    capped = sum(min(PER_OUTLET_CAP, c) for c in outlet_counts)
    volume = min(1.0, math.log1p(capped) / math.log1p(VOLUME_SATURATION))
    if last_seen is None:
        recency = 0.0
    else:
        hours = max(0.0, (now - last_seen).total_seconds() / 3600)
        recency = 0.5 ** (hours / HALF_LIFE_HOURS)
    return round(100 * (W_REACH * reach + W_VOLUME * volume + W_RECENCY * recency), 1)
