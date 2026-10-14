"""Perfil medido de um veículo no período, comparado à média dos outros veículos.

Não produz rótulo de orientação política. Mede, nas manchetes e resumos:
- volume ao longo do tempo;
- em que seções o veículo publica (parte das notícias dele em cada seção);
- quem ele põe nas manchetes (parte das manchetes que citam cada ator);
- como a IA leu o tom em relação aos atores principais (só leituras validadas, com n);
- forma das manchetes (fala atribuída, pergunta, aspas, termos de impacto);
- exclusividade (histórias que só ele cobriu entre os monitorados).
"""

from collections import Counter, defaultdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.coverage.metrics import Range, exclusive_counts, timeline
from app.coverage.profile_math import (
    MIN_ARTICLES_FOR_AVERAGE,
    average_share,
    fold,
    rate,
    tone_table,
)
from app.coverage.queries import _eligible_articles
from app.framing import llm as llm_mod
from app.framing import observable as obs_mod
from app.models import ArticleAnalysis, Outlet, StoryArticle
from app.topics import TOPICS

TOP_ACTORS = 10


def _latest_analyses(session: Session, article_ids: list[int], kind: str, version: str) -> dict[int, ArticleAnalysis]:
    out: dict[int, ArticleAnalysis] = {}
    if not article_ids:
        return out
    for an in session.scalars(
        select(ArticleAnalysis)
        .where(ArticleAnalysis.article_id.in_(article_ids), ArticleAnalysis.analysis_type == kind,
               ArticleAnalysis.prompt_version == version)
        .order_by(ArticleAnalysis.created_at)
    ):
        out[an.article_id] = an
    return out


def outlet_profile(session: Session, outlet: Outlet, r: Range, now: datetime) -> dict:
    outlets = session.scalars(select(Outlet).where(Outlet.active.is_(True))).all()
    peers = [o.id for o in outlets if o.outlet_group == outlet.outlet_group]
    articles = _eligible_articles(session, r.start, r.end)
    mine = [a for a in articles if a.outlet_id == outlet.id]
    peer_articles = [a for a in articles if a.outlet_id in peers]

    # --- Seções ---------------------------------------------------------------
    topic_per_outlet: dict[int, tuple[Counter, int]] = {}
    for oid in set(a.outlet_id for a in peer_articles) | {outlet.id}:
        rows = [a for a in peer_articles if a.outlet_id == oid] if oid != outlet.id else mine
        topic_per_outlet[oid] = (Counter(a.topic or "outros" for a in rows), len(rows))
    my_topics, my_total = topic_per_outlet[outlet.id]
    sections = [
        {
            "topic": t,
            "label": label,
            "count": my_topics.get(t, 0),
            "share": (my_topics.get(t, 0) / my_total) if my_total else None,
            "average_share": average_share(topic_per_outlet, t, exclude=outlet.id),
        }
        for t, label in TOPICS.items()
    ]

    # --- Manchetes: atores e forma (análise observável) -------------------------
    obs = _latest_analyses(session, [a.id for a in peer_articles], "observable", obs_mod.VERSION)
    actor_per_outlet: dict[int, tuple[Counter, int]] = {}
    names: dict[str, str] = {}
    form_flags: dict[int, dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    for a in peer_articles:
        an = obs.get(a.id)
        if an is None or not an.result:
            continue
        res = an.result
        counts, total = actor_per_outlet.get(a.outlet_id, (Counter(), 0))
        for actor in {x["key"]: x["name"] for x in res.get("headline_actors", [])}.items():
            counts[actor[0]] += 1
            names.setdefault(actor[0], actor[1])
        actor_per_outlet[a.outlet_id] = (counts, total + 1)
        f = form_flags[a.outlet_id]
        f["attribution"].append(bool(res.get("attribution_verbs")))
        f["question"].append(bool(res.get("is_question")))
        f["quote"].append(bool(res.get("has_quote")))
        f["loaded"].append(bool(res.get("loaded_terms")))

    my_actor_counts, my_analyzed = actor_per_outlet.get(outlet.id, (Counter(), 0))
    actors = [
        {
            "key": k,
            "name": names.get(k, k),
            "count": c,
            "share": c / my_analyzed if my_analyzed else None,
            "average_share": average_share(actor_per_outlet, k, exclude=outlet.id),
        }
        for k, c in my_actor_counts.most_common(TOP_ACTORS)
    ]

    form_labels = {
        "attribution": "Fala atribuída",
        "quote": "Aspas",
        "loaded": "Termo de impacto",
        "question": "Pergunta",
    }
    form = []
    for key, label in form_labels.items():
        mine_rate, n = rate(form_flags[outlet.id][key])
        others = [
            rate(flags[key])[0]
            for oid, flags in form_flags.items()
            if oid != outlet.id and len(flags[key]) >= MIN_ARTICLES_FOR_AVERAGE
        ]
        others = [x for x in others if x is not None]
        form.append({"key": key, "label": label, "share": mine_rate, "n": n,
                     "average_share": (sum(others) / len(others)) if others else None})

    # --- Tom (leitura da IA, só validada) ------------------------------------
    llm = _latest_analyses(session, [a.id for a in peer_articles], "llm", llm_mod.PROMPT_VERSION)
    my_rows, peer_rows = [], []
    for a in peer_articles:
        an = llm.get(a.id)
        if an is None or not an.result or (an.validation or {}).get("status") == "rejected":
            continue
        actor = an.result.get("main_actor")
        if not actor:
            continue
        (my_rows if a.outlet_id == outlet.id else peer_rows).append((actor, an.result.get("tone", "incerto")))
    tone = tone_table(my_rows)
    peer_neg: dict[str, tuple[int, int]] = {}
    for name, t in peer_rows:
        neg, n = peer_neg.get(fold(name), (0, 0))
        peer_neg[fold(name)] = (neg + (t == "negativo"), n + 1)
    for row in tone:
        neg, n = peer_neg.get(row["key"], (0, 0))
        row["peers_n"] = n
        row["peers_negative_share"] = (neg / n) if n >= 5 else None

    # --- Exclusividade -------------------------------------------------------
    ids_by_outlet: dict[int, set[int]] = defaultdict(set)
    for a in peer_articles:
        ids_by_outlet[a.outlet_id].add(a.id)
    links = session.execute(
        select(StoryArticle.story_id, StoryArticle.article_id)
        .where(StoryArticle.article_id.in_([a.id for a in peer_articles]))
    ).all() if peer_articles else []
    outlet_of = {a.id: a.outlet_id for a in peer_articles}
    story_outlets: dict[int, set[int]] = defaultdict(set)
    for sid, aid in links:
        story_outlets[sid].add(outlet_of[aid])
    excl = exclusive_counts(story_outlets)
    stories_per_outlet = Counter(o for s in story_outlets.values() for o in s)
    my_stories = stories_per_outlet.get(outlet.id, 0)
    peer_excl_rates = [
        excl.get(o, 0) / n for o, n in stories_per_outlet.items()
        if o != outlet.id and n >= MIN_ARTICLES_FOR_AVERAGE
    ]

    starts, series = timeline(((a.outlet_id, a.published_at) for a in mine), [outlet.id], r)

    return {
        "outlet": {"id": outlet.id, "name": outlet.name, "group": outlet.outlet_group, "language": outlet.language,
                   "favorite": outlet.favorite, "active": outlet.active, "collection_notes": outlet.collection_notes},
        "range": {"start": r.start, "end": r.end, "label": r.label, "bucket_seconds": int(r.bucket.total_seconds()),
                  "generated_at": now},
        "peers": {"group": outlet.outlet_group, "count": len([p for p in peers if p != outlet.id]),
                  "min_articles": MIN_ARTICLES_FOR_AVERAGE},
        "totals": {"articles": my_total, "analyzed_headlines": my_analyzed, "ai_readings": len(my_rows),
                   "stories": my_stories, "exclusive_stories": excl.get(outlet.id, 0)},
        "timeline": {"buckets": starts, "counts": series[outlet.id]},
        "sections": sections,
        "actors": actors,
        "form": form,
        "tone": tone,
        "exclusivity": {
            "share": (excl.get(outlet.id, 0) / my_stories) if my_stories else None,
            "average_share": (sum(peer_excl_rates) / len(peer_excl_rates)) if peer_excl_rates else None,
        },
    }
