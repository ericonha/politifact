import Link from "next/link";
import { notFound } from "next/navigation";
import { TopicBadge } from "@/components/TopicTabs";
import { formatDate, getStory, type StoryArticle } from "@/lib/api";

const METHOD_LABEL: Record<StoryArticle["assignment_method"], string> = {
  seed: "primeira notícia",
  auto: "agrupada automaticamente",
  syndicated: "republicação",
  manual: "agrupada à mão",
};

export default async function StoryPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const storyId = Number(id);
  if (!Number.isInteger(storyId)) notFound();

  const story = await getStory(storyId).catch(() => null);
  if (!story) notFound();

  const byOutlet = new Map<string, StoryArticle[]>();
  for (const a of story.articles) {
    const list = byOutlet.get(a.outlet_name) ?? [];
    list.push(a);
    byOutlet.set(a.outlet_name, list);
  }

  return (
    <>
      <p className="muted"><Link href="/">← Histórias</Link></p>
      <TopicBadge topic={story.topic} />
      <h1>{story.title}</h1>
      <p className="note">
        {story.article_count} notícias em {story.outlet_count} veículos · de{" "}
        {formatDate(story.first_observed_at)} a {formatDate(story.last_observed_at)}
      </p>

      <p className="note">
        <Link href={`/comparar?ids=${story.id}`}>Comparar com outra história →</Link>
      </p>

      <div className="outlet-columns">
        {[...byOutlet.entries()].map(([outlet, articles]) => (
          <section key={outlet} className="outlet-column">
            <h2>{outlet} <span className="count">{articles.length}</span></h2>
            <ul className="articles">
              {articles.map((a) => (
                <li key={a.article_id}>
                  <div className="meta">
                    <span>{formatDate(a.published_at)}</span>
                    <span>
                      {METHOD_LABEL[a.assignment_method]}
                      {a.cluster_confidence != null && ` (${a.cluster_confidence.toFixed(2)})`}
                    </span>
                  </div>
                  <a href={a.original_url} target="_blank" rel="noopener noreferrer" className="headline">
                    {a.headline}
                  </a>
                  {a.summary && <p className="muted">{a.summary}</p>}
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </>
  );
}
