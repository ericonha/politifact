"""Medidas de viés de cobertura de um veículo, a partir do banco (ver bias_math.py).

Compara o veículo com os demais do MESMO grupo (nacional/internacional); o vocabulário compara só
veículos do mesmo idioma. Tudo "entre os veículos monitorados" e só no que os feeds RSS mostram.
"""

from collections import defaultdict
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.coverage.bias_math import (
    MAX_BLIND_SPOTS,
    MIN_OUTLETS_FOR_OMISSION,
    delay_stats,
    distinctive_terms,
    omission_stats,
    revision_stats,
    tokens,
)
from app.coverage.metrics import Range
from app.coverage.queries import _eligible_articles
from app.models import Article, ArticleRevision, Outlet, Story, StoryArticle
from app.topics import TOPICS

MIN_VOCAB_OUTLETS = 3  # histórias com pelo menos 3 veículos do mesmo idioma
MAX_EDIT_EXAMPLES = 6
_KIND_PRIORITY = {"possivel_sentido": 3, "reescrita": 2, "ajuste": 1, "resumo": 0}


def outlet_bias(session: Session, outlet: Outlet, r: Range, now: datetime) -> dict:
    outlets = session.scalars(select(Outlet).where(Outlet.active.is_(True))).all()
    names = {o.id: o.name for o in outlets}
    group = {o.id for o in outlets if o.outlet_group == outlet.outlet_group} | {outlet.id}
    same_lang = {o.id for o in outlets if o.outlet_group == outlet.outlet_group and o.language == outlet.language}
    same_lang.add(outlet.id)

    articles = [a for a in _eligible_articles(session, r.start, r.end) if a.outlet_id in group]
    ids = [a.id for a in articles]
    by_id = {a.id: a for a in articles}
    per_outlet_articles: dict[int, int] = defaultdict(int)
    for a in articles:
        per_outlet_articles[a.outlet_id] += 1

    # --- histórias: quem cobriu e quando saiu a primeira matéria de cada veículo ------------------
    links = session.execute(
        select(StoryArticle.story_id, StoryArticle.article_id).where(StoryArticle.article_id.in_(ids))
    ).all() if ids else []
    story_outlets: dict[int, set[int]] = defaultdict(set)
    first_art: dict[int, dict[int, tuple[datetime, int]]] = defaultdict(dict)  # story -> outlet -> (hora, article_id)
    for sid, aid in links:
        a = by_id[aid]
        story_outlets[sid].add(a.outlet_id)
        cur = first_art[sid].get(a.outlet_id)
        if cur is None or a.published_at < cur[0]:
            first_art[sid][a.outlet_id] = (a.published_at, aid)
    first_times = {sid: {o: t for o, (t, _) in d.items()} for sid, d in first_art.items()}
    story_start = {sid: min(t.values()) for sid, t in first_times.items()}

    # Profundidade do feed: a matéria mais antiga que temos de cada veículo. Histórias anteriores a isso
    # não podem contar como omissão dele, porque o feed nem mostraria.
    monitored_since = dict(session.execute(
        select(Article.outlet_id, func.min(Article.published_at)).where(Article.outlet_id.in_(group))
        .group_by(Article.outlet_id)
    ).all())

    # --- 1. omissões ------------------------------------------------------------------------------
    om = omission_stats(story_outlets, group, outlet.id, eligible_since=monitored_since, story_start=story_start)
    covered_ids, missed_ids = om.pop("covered_ids"), om.pop("missed_ids")
    story_rows = {
        s.id: s for s in session.scalars(select(Story).where(Story.id.in_(covered_ids + missed_ids)))
    } if (covered_ids or missed_ids) else {}
    by_topic = []
    for t, label in TOPICS.items():
        miss = sum(1 for sid in missed_ids if (story_rows[sid].topic or "outros") == t)
        cov = sum(1 for sid in covered_ids if (story_rows[sid].topic or "outros") == t)
        if miss + cov:
            by_topic.append({"topic": t, "label": label, "eligible": miss + cov, "missed": miss,
                             "omission_rate": miss / (miss + cov)})
    blind = []
    for sid in om.pop("blind_spot_ids")[:MAX_BLIND_SPOTS]:
        st = story_rows[sid]
        covering = sorted(names[o] for o in story_outlets[sid] if o in names)
        blind.append({"story_id": sid, "title": st.title, "topic": st.topic, "outlets_count": len(covering),
                      "outlets": covering[:6], "first_published_at": story_start.get(sid)})
    om["by_topic"] = sorted(by_topic, key=lambda x: -x["omission_rate"])
    om["blind_spots"] = blind

    # --- 2. atraso --------------------------------------------------------------------------------
    delay = delay_stats(first_times, group, outlet.id)

    # --- 3. vocabulário (mesma história, mesmo idioma) --------------------------------------------
    vocab_stories = [sid for sid, d in first_art.items() if len({o for o in d if o in same_lang}) >= MIN_VOCAB_OUTLETS
                     and outlet.id in d]
    # Todos os veículos do idioma na história, não só os que cobriram a minha: precisa de "outros" também.
    doc_ids = [aid for sid in vocab_stories for o, (_, aid) in first_art[sid].items() if o in same_lang]
    texts = {
        aid: tokens(f"{h} {s or ''}")
        for aid, h, s in session.execute(select(Article.id, Article.headline, Article.summary)
                                         .where(Article.id.in_(doc_ids)))
    } if doc_ids else {}
    mine_docs, other_docs = [], []
    for sid in vocab_stories:
        for o, (_, aid) in first_art[sid].items():
            if o not in same_lang:
                continue
            (mine_docs if o == outlet.id else other_docs).append((sid, texts.get(aid, set())))
    vocab = distinctive_terms(mine_docs, other_docs)
    vocab["comparison_outlets"] = len(same_lang) - 1
    vocab["language"] = outlet.language

    # --- 4. edições de manchete -------------------------------------------------------------------
    revs = session.execute(
        select(ArticleRevision.article_id, ArticleRevision.headline, ArticleRevision.change, ArticleRevision.observed_at)
        .where(ArticleRevision.article_id.in_(ids)).order_by(ArticleRevision.observed_at)
    ).all() if ids else []
    per_article: dict[int, dict] = {}
    for aid, headline, change, observed in revs:
        change = change or {}
        cur = per_article.setdefault(aid, {"headline_changed": False, "kind": "resumo", "declared": False,
                                           "similarity": 1.0, "new_headline": None, "observed_at": None})
        cur["declared"] |= bool(change.get("declared"))
        if change.get("headline_changed"):
            cur["headline_changed"] = True
            if _KIND_PRIORITY.get(change.get("kind"), 0) >= _KIND_PRIORITY[cur["kind"]]:
                cur.update(kind=change.get("kind"), similarity=change.get("similarity", 1.0),
                           new_headline=headline, observed_at=observed)
    by_outlet: dict[int, list[dict]] = defaultdict(list)
    for aid, c in per_article.items():
        by_outlet[by_id[aid].outlet_id].append(c)
    edits = revision_stats(dict(per_outlet_articles), by_outlet, outlet.id)
    flagged = sorted(
        ((aid, c) for aid, c in per_article.items()
         if by_id[aid].outlet_id == outlet.id and c["headline_changed"] and c["kind"] in ("possivel_sentido", "reescrita")),
        key=lambda x: (-_KIND_PRIORITY[x[1]["kind"]], x[1]["observed_at"] or now),
    )[:MAX_EDIT_EXAMPLES]
    if flagged:
        orig = {a.id: a for a in session.scalars(select(Article).where(Article.id.in_([aid for aid, _ in flagged])))}
        edits["examples"] = [
            {"article_id": aid, "url": orig[aid].original_url, "original_headline": orig[aid].headline,
             "new_headline": c["new_headline"], "kind": c["kind"], "observed_at": c["observed_at"],
             "declared": c["declared"]}
            for aid, c in flagged
        ]
    else:
        edits["examples"] = []
    peers_total = sum(per_outlet_articles[o] for o in group if o != outlet.id)
    edits["peers_articles"] = peers_total
    edits["peers_edited"] = sum(
        1 for o, lst in by_outlet.items() if o != outlet.id for c in lst if c["headline_changed"])

    return {
        "outlet": {"id": outlet.id, "name": outlet.name, "group": outlet.outlet_group, "language": outlet.language},
        "range": {"start": r.start, "end": r.end, "label": r.label, "generated_at": now},
        "peers": {"group": outlet.outlet_group, "count": len(group) - 1, "min_outlets_for_omission": MIN_OUTLETS_FOR_OMISSION},
        "omissions": om,
        "delay": delay,
        "vocabulary": vocab,
        "edits": edits,
    }
