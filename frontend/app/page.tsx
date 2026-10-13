import Link from "next/link";
import { PageLayout, Sidebar } from "@/components/Sidebar";
import { OutletNames, StoryCard, StoryMeta } from "@/components/StoryParts";
import { TopicBadge } from "@/components/TopicTabs";
import {
  TOPIC_LABELS,
  getCollectionStatus,
  getOutlets,
  getStories,
  getTopics,
  parseOutletChoice,
  parseTopic,
  parseWindow,
} from "@/lib/api";

type SP = { janela?: string; secao?: string; veiculo?: string; favoritos?: string };

export default async function StoriesPage({ searchParams }: { searchParams: Promise<SP> }) {
  const sp = await searchParams;
  const win = parseWindow(sp.janela);
  const topic = parseTopic(sp.secao);
  const choice = parseOutletChoice(sp);
  const [stories, outlets, topics, status] = await Promise.all([
    getStories(win, topic, choice),
    getOutlets(),
    getTopics(win),
    getCollectionStatus(),
  ]);
  const names = new Map(outlets.map((o) => [o.id, o.name]));
  const activeOutlets = outlets.filter((o) => o.active).length;
  const outletName = choice.outletId ? names.get(choice.outletId) : undefined;

  const [lead, ...rest] = stories;
  const second = rest.slice(0, 2);
  const others = rest.slice(2);

  const scope = [
    topic ? TOPIC_LABELS[topic] : null,
    outletName ? `cobertas por ${outletName}` : choice.favorites ? "cobertas pelos seus favoritos" : null,
  ].filter(Boolean).join(", ");

  return (
    <PageLayout
      sidebar={
        <Sidebar
          title="Histórias"
          intro="Os assuntos do período, agrupando as notícias de todos os veículos. Primeiro, os que mais veículos cobriram."
          basePath="/"
          params={{ ...sp }}
          status={status}
          period
          topics={topics}
          outlets={outlets}
        />
      }
    >
      {stories.length === 0 ? (
        <div className="empty">
          Nenhuma história {scope ? `(${scope}) ` : ""}neste período. As notícias são agrupadas logo depois
          de cada coleta; veja as <Link href="/noticias">notícias coletadas</Link> ou a{" "}
          <Link href="/revisao">fila de revisão</Link>.
        </div>
      ) : (
        <>
          {scope && <p className="note" style={{ marginTop: 0 }}>Mostrando: {scope}.</p>}

          <article className="lead">
            {!topic && <TopicBadge topic={lead.topic} />}
            <h2 className="lead-title"><Link href={`/historias/${lead.id}`}>{lead.title}</Link></h2>
            {lead.summary && <p className="lead-summary">{lead.summary}</p>}
            <StoryMeta story={lead} activeOutlets={activeOutlets} />
            <OutletNames story={lead} names={names} max={10} />
          </article>

          {second.length > 0 && (
            <div className="second-row">
              {second.map((s) => (
                <StoryCard key={s.id} story={s} names={names} activeOutlets={activeOutlets} showTopic={!topic} />
              ))}
            </div>
          )}

          {others.length > 0 && (
            <>
              <h2 className="front-section-title">Mais histórias</h2>
              <div className="story-grid">
                {others.map((s) => (
                  <StoryCard key={s.id} story={s} names={names} activeOutlets={activeOutlets} showTopic={!topic} />
                ))}
              </div>
            </>
          )}

          <p className="note" style={{ marginTop: 24 }}>
            Contagens entre os {activeOutlets} veículos monitorados, não cobertura total da mídia.{" "}
            <Link href={`/cobertura?${new URLSearchParams({ janela: win, ...(topic ? { secao: topic } : {}) })}`}>
              Ver o painel de cobertura
            </Link>
          </p>
        </>
      )}
    </PageLayout>
  );
}
