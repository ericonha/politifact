import Link from "next/link";
import { WINDOWS, formatDate, getArticles, getOutlets, parseWindow } from "@/lib/api";

export default async function ArticlesPage({
  searchParams,
}: {
  searchParams: Promise<{ janela?: string; veiculo?: string }>;
}) {
  const { janela, veiculo } = await searchParams;
  const win = parseWindow(janela);
  const outletId = veiculo ? Number(veiculo) || undefined : undefined;
  const [articles, outlets] = await Promise.all([getArticles(win, outletId), getOutlets()]);
  const names = new Map(outlets.map((o) => [o.id, o.name]));

  const href = (params: { janela?: string; veiculo?: number }) => {
    const q = new URLSearchParams();
    q.set("janela", params.janela ?? win);
    const v = "veiculo" in params ? params.veiculo : outletId;
    if (v) q.set("veiculo", String(v));
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

      <div className="tabs filters">
        <Link href={href({ veiculo: undefined })} className={!outletId ? "tab active" : "tab"}>
          Todos
        </Link>
        {outlets.filter((o) => o.active).map((o) => (
          <Link key={o.id} href={href({ veiculo: o.id })} className={outletId === o.id ? "tab active" : "tab"}>
            {o.name}
            {!outletId && <span className="count">{counts.get(o.id) ?? 0}</span>}
          </Link>
        ))}
      </div>

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
