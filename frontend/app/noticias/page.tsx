import Link from "next/link";
import { TopicBadge, TopicTabs } from "@/components/TopicTabs";
import { WINDOWS, formatDate, getArticles, getOutlets, getTopics, parseTopic, parseWindow } from "@/lib/api";

export default async function ArticlesPage({
  searchParams,
}: {
  searchParams: Promise<{ janela?: string; veiculo?: string; secao?: string }>;
}) {
  const { janela, veiculo, secao } = await searchParams;
  const win = parseWindow(janela);
  const topic = parseTopic(secao);
  const outletId = veiculo ? Number(veiculo) || undefined : undefined;
  const [articles, outlets, topics] = await Promise.all([
    getArticles(win, outletId, topic),
    getOutlets(),
    getTopics(win),
  ]);
  const names = new Map(outlets.map((o) => [o.id, o.name]));
  const english = new Set(outlets.filter((o) => o.language.startsWith("en")).map((o) => o.id));

  const href = (params: { janela?: string; veiculo?: number; secao?: string | null }) => {
    const q = new URLSearchParams();
    q.set("janela", params.janela ?? win);
    const v = "veiculo" in params ? params.veiculo : outletId;
    if (v) q.set("veiculo", String(v));
    const t = params.secao === null ? undefined : params.secao ?? topic;
    if (t) q.set("secao", t);
    return `/noticias?${q}`;
  };

  const counts = new Map<number, number>();
  for (const a of articles) counts.set(a.outlet_id, (counts.get(a.outlet_id) ?? 0) + 1);

  return (
    <>
      <div className="toolbar">
        <h1>Notícias coletadas</h1>
        <div className="tabs">
          {WINDOWS.map((w) => (
            <Link key={w.value} href={href({ janela: w.value })} className={w.value === win ? "tab active" : "tab"}>
              {w.label}
            </Link>
          ))}
        </div>
      </div>

      <TopicTabs current={topic} topics={topics} href={(t) => href({ secao: t ?? null })} />

      <form action="/noticias" method="get" className="filter-row">
        <input type="hidden" name="janela" value={win} />
        {topic && <input type="hidden" name="secao" value={topic} />}
        <label className="muted">
          Veículo{" "}
          <select name="veiculo" defaultValue={outletId ? String(outletId) : ""} className="select">
            <option value="">Todos os veículos</option>
            {["nacional", "internacional"].map((g) => (
              <optgroup key={g} label={g === "nacional" ? "Nacionais" : "Internacionais"}>
                {outlets.filter((o) => o.active && o.outlet_group === g).map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name}{!outletId ? ` (${counts.get(o.id) ?? 0})` : ""}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>
        <button type="submit" className="button small secondary">Filtrar</button>
      </form>

      <p className="note">
        {articles.length} notícias publicadas no período, pela data de publicação informada no feed.
        Notícias sem data de publicação não aparecem aqui.
      </p>

      {articles.length === 0 ? (
        <div className="empty">
          Nenhuma notícia neste período. Veja se a coleta está rodando em{" "}
          <Link href="/coletas">Coletas</Link>.
        </div>
      ) : (
        <ul className="articles">
          {articles.map((a) => (
            <li key={a.id}>
              <div className="meta">
                <span className="outlet">{names.get(a.outlet_id) ?? "?"}</span>
                {english.has(a.outlet_id) && <span className="lang-badge">EN</span>}
                {!topic && <TopicBadge topic={a.topic} />}
                <span>{formatDate(a.published_at)}</span>
              </div>
              <a href={a.original_url} target="_blank" rel="noopener noreferrer" className="headline">
                {a.headline}
              </a>
              {a.summary && <p className="muted">{a.summary}</p>}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
