"""Compara as manchetes de uma mesma história: o que cada veículo escolheu destacar.

Entrada: lista de {outlet, observable}. Saída: diferenças verificáveis no texto,
nunca uma conclusão sobre intenção ou viés.
"""

from collections import defaultdict


def compare(items: list[dict]) -> dict:
    """items: [{"outlet": str, "observable": dict}, ...] (uma entrada por notícia)."""
    outlets = sorted({it["outlet"] for it in items})
    n_outlets = len(outlets)

    # Quem aparece nas manchetes e em quais veículos
    actor_outlets: dict[str, set[str]] = defaultdict(set)
    actor_name: dict[str, str] = {}
    lead_by_outlet: dict[str, list[str]] = defaultdict(list)
    attribution_outlets: set[str] = set()
    question_outlets: set[str] = set()
    loaded_by_outlet: dict[str, list[str]] = defaultdict(list)

    for it in items:
        obs = it["observable"] or {}
        outlet = it["outlet"]
        for a in obs.get("headline_actors", []):
            actor_outlets[a["key"]].add(outlet)
            actor_name.setdefault(a["key"], a["name"])
        if obs.get("lead_actor"):
            lead_by_outlet[outlet].append(obs["lead_actor"])
        if obs.get("attribution_verbs"):
            attribution_outlets.add(outlet)
        if obs.get("is_question"):
            question_outlets.add(outlet)
        for term in obs.get("loaded_terms", []):
            if term.lower() not in (t.lower() for t in loaded_by_outlet[outlet]):
                loaded_by_outlet[outlet].append(term)

    actors = sorted(
        (
            {
                "key": key,
                "name": actor_name[key],
                "outlets": sorted(outs),
                "in_all": len(outs) == n_outlets,
            }
            for key, outs in actor_outlets.items()
        ),
        key=lambda a: (-len(a["outlets"]), a["name"]),
    )

    # Atores que só uma parte dos veículos citou na manchete (diferença de destaque)
    partial = [a for a in actors if not a["in_all"] and n_outlets > 1]

    distinct_leads = {name.lower() for names in lead_by_outlet.values() for name in names}

    return {
        "outlets": outlets,
        "actors": actors,
        "partial_actors": partial,
        "lead_actor_by_outlet": {k: v for k, v in sorted(lead_by_outlet.items())},
        "different_leads": len(distinct_leads) > 1,
        "attribution_outlets": sorted(attribution_outlets),
        "question_outlets": sorted(question_outlets),
        "loaded_terms_by_outlet": {k: v for k, v in sorted(loaded_by_outlet.items()) if v},
    }
