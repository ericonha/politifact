import Link from "next/link";
import { TopicBadge, TopicTabs } from "@/components/TopicTabs";
import { TOPIC_LABELS, WINDOWS, getOutlets, getStories, getTopics, parseTopic, parseWindow } from "@/lib/api";

export default async function StoriesPage({
  searchParams,
}: {
  searchParams: Promise<{ janela?: string; secao?: string }>;
}) {
  const { janela, secao } = await searchParams;
  const win = parseWindow(janela);
  const topic = parseTopic(secao);
  const [stories, allOutlets, topics] = await Promise.all([getStories(win, topic), getOutlets(), getTopics(win)]);
  const activeCount = allOutlets.filter((o) => o.active).length;
  const nameOf = new Map(allOutlets.map((o) => [o.id, o.name]));
  const href = (p: { janela?: string; secao?: string | null }) => {
    const q = new URLSearchParams({ janela: p.janela ?? win });
    const t = p.secao === null ? undefined : p.secao ?? topic;
    if (t) q.set("secao", t);
    return `/?${q}`;
  };

  return (
    <>
      <div className="toolbar">
        <h1>Histórias</h1>
        <div className="tabs">
          {WINDOWS.map((w) => (
            <Link
              key={w.value}
              href={href({ janela: w.value })}
              className={w.value === win ? "tab active" : "tab"}
            >
              {w.label}
            </Link>
          ))}
        </div>
      </div>

      <TopicTabs current={topic} topics={topics} href={(t) => href({ secao: t ?? null })} />

      <p className="note">
        {topic ? `${TOPIC_LABELS[topic]}: ` : ""}cobertura entre os {activeCount} veículos monitorados,
        não cobertura total da mídia. <Link href={`/cobertura?${new URLSearchParams({ janela: win, ...(topic ? { secao: topic } : {}) })}`}>Ver painel de cobertura →</Link>
      </p>

      {stories.length === 0 ? (
        <div className="empty">
          Nenhuma história neste período ainda. As notícias são agrupadas logo depois de cada
          coleta; veja as <Link href="/noticias">notícias coletadas</Link> e a{" "}
          <Link href="/revisao">fila de revisão</Link>.
        </div>
      ) : (
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>História</th>
                <th className="num-cell">Veículos</th>
                <th className="num-cell">Notícias</th>
              </tr>
            </thead>
            <tbody>
              {stories.map((s) => (
                <tr key={s.id}>
                  <td>
                    {!topic && <TopicBadge topic={s.topic} />}
                    <Link href={`/historias/${s.id}`} className="story-link">{s.title}</Link>
                    {s.summary && <div className="muted">{s.summary}</div>}
                    <div className="outlet-list">
                      {s.coverage.map((c) => `${nameOf.get(c.outlet_id) ?? c.outlet_name} (${c.article_count})`).join(" · ")}
                    </div>
                  </td>
                  <td className="num-cell">{s.outlet_count}</td>
                  <td className="num-cell">{s.article_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
