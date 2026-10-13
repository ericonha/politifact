import Link from "next/link";
import { PageLayout, Sidebar } from "@/components/Sidebar";
import { TopicBadge } from "@/components/TopicTabs";
import {
  formatTime,
  getArticles,
  getCollectionStatus,
  getOutlets,
  getTopics,
  parseOutletChoice,
  parseTopic,
  parseWindow,
  timeAgo,
} from "@/lib/api";

type SP = { janela?: string; secao?: string; veiculo?: string; favoritos?: string };

export default async function ArticlesPage({ searchParams }: { searchParams: Promise<SP> }) {
  const sp = await searchParams;
  const win = parseWindow(sp.janela);
  const topic = parseTopic(sp.secao);
  const choice = parseOutletChoice(sp);
  const [articles, outlets, topics, status] = await Promise.all([
    getArticles(win, choice.outletId, topic, choice.favorites),
    getOutlets(),
    getTopics(win),
    getCollectionStatus(),
  ]);
  const names = new Map(outlets.map((o) => [o.id, o.name]));
  const english = new Set(outlets.filter((o) => o.language.startsWith("en")).map((o) => o.id));

  return (
    <PageLayout
      sidebar={
        <Sidebar
          title="Notícias"
          intro="Tudo o que foi coletado, da mais recente para a mais antiga, pela hora de publicação do veículo."
          basePath="/noticias"
          params={{ ...sp }}
          status={status}
          period
          topics={topics}
          outlets={outlets}
        />
      }
    >
      <p className="note" style={{ marginTop: 0 }}>
        {articles.length} {articles.length === 1 ? "notícia" : "notícias"} no período. Notícias sem data de
        publicação no feed não aparecem aqui.
      </p>

      {articles.length === 0 ? (
        <div className="empty">
          Nenhuma notícia com esses filtros. Veja se a coleta está rodando em <Link href="/coletas">Coletas</Link>.
        </div>
      ) : (
        <ul className="feed">
          {articles.map((a) => (
            <li key={a.id}>
              <div className="feed-when">
                <strong>{names.get(a.outlet_id) ?? "?"}</strong>
                <span title={formatTime(a.published_at)}>{timeAgo(a.published_at)}</span>
              </div>
              <div>
                {!topic && <TopicBadge topic={a.topic} />}
                <h2 className="feed-title">
                  {english.has(a.outlet_id) && <span className="lang-badge">EN</span>}
                  <a href={a.original_url} target="_blank" rel="noopener noreferrer">{a.headline}</a>
                </h2>
                {a.summary && <p>{a.summary}</p>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </PageLayout>
  );
}
