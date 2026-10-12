"""Métricas de agrupamento contra um gabarito montado à mão.

- B-cubed: para cada notícia, precisão = fração do seu cluster previsto que
  está no mesmo grupo do gabarito; recall = fração do seu grupo do gabarito
  que caiu no mesmo cluster previsto. Média sobre as notícias.
- Junções erradas: pares juntos na previsão mas separados no gabarito.
- Separações erradas: pares juntos no gabarito mas separados na previsão.
"""

from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations


@dataclass(frozen=True)
class ClusterMetrics:
    n_articles: int
    n_gold_stories: int
    n_pred_stories: int
    bcubed_precision: float
    bcubed_recall: float
    bcubed_f1: float
    wrong_merges: int
    wrong_splits: int
    gold_pairs: int


def _groups(labels: dict[int, object]) -> dict[object, set[int]]:
    g: dict[object, set[int]] = defaultdict(set)
    for item, label in labels.items():
        g[label].add(item)
    return g


def evaluate(gold: dict[int, object], pred: dict[int, object]) -> ClusterMetrics:
    items = sorted(set(gold) & set(pred))
    if not items:
        raise ValueError("nenhuma notícia em comum entre gabarito e previsão")
    gold = {i: gold[i] for i in items}
    pred = {i: pred[i] for i in items}
    gold_groups, pred_groups = _groups(gold), _groups(pred)

    precision = recall = 0.0
    for i in items:
        g, p = gold_groups[gold[i]], pred_groups[pred[i]]
        overlap = len(g & p)
        precision += overlap / len(p)
        recall += overlap / len(g)
    precision /= len(items)
    recall /= len(items)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    merges = splits = gold_pairs = 0
    for a, b in combinations(items, 2):
        same_gold = gold[a] == gold[b]
        same_pred = pred[a] == pred[b]
        gold_pairs += same_gold
        if same_pred and not same_gold:
            merges += 1
        elif same_gold and not same_pred:
            splits += 1

    return ClusterMetrics(
        n_articles=len(items),
        n_gold_stories=len(gold_groups),
        n_pred_stories=len(pred_groups),
        bcubed_precision=precision,
        bcubed_recall=recall,
        bcubed_f1=f1,
        wrong_merges=merges,
        wrong_splits=splits,
        gold_pairs=gold_pairs,
    )
