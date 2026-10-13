import Link from "next/link";
import { TopicBadge } from "@/components/TopicTabs";
import { timeAgo, type Story } from "@/lib/api";

/** Alcance em quadradinhos: um por veículo ativo; preenchidos = cobriram. */
export function ReachBar({ count, total }: { count: number; total: number }) {
  const n = Math.min(total, 12);
  const on = Math.min(count, n);
  return (
    <span className="reach-bar" aria-hidden="true">
      {Array.from({ length: n }, (_, i) => <i key={i} className={i < on ? "on" : undefined} />)}
    </span>
  );
}

export function StoryMeta({ story, activeOutlets }: { story: Story; activeOutlets: number }) {
  return (
    <div className="story-meta">
      <span title={`${story.outlet_count} de ${activeOutlets} veículos monitorados`}>
        <ReachBar count={story.outlet_count} total={activeOutlets} />
        <strong>{story.outlet_count}</strong> {story.outlet_count === 1 ? "veículo" : "veículos"}
      </span>
      <span>{story.article_count} {story.article_count === 1 ? "notícia" : "notícias"}</span>
      <span>atualizada {timeAgo(story.last_observed_at)}</span>
    </div>
  );
}

export function OutletNames({ story, names, max = 6 }: { story: Story; names: Map<number, string>; max?: number }) {
  const list = [...story.coverage].sort((a, b) => b.article_count - a.article_count)
    .map((c) => names.get(c.outlet_id) ?? c.outlet_name);
  const shown = list.slice(0, max);
  const rest = list.length - shown.length;
  return (
    <div className="outlet-names">
      {shown.join(", ")}{rest > 0 ? ` e mais ${rest}` : ""}
    </div>
  );
}

export function StoryCard({
  story,
  names,
  activeOutlets,
  showTopic,
}: {
  story: Story;
  names: Map<number, string>;
  activeOutlets: number;
  showTopic: boolean;
}) {
  return (
    <article className="story">
      {showTopic && <TopicBadge topic={story.topic} />}
      <h3 className="story-title"><Link href={`/historias/${story.id}`}>{story.title}</Link></h3>
      <StoryMeta story={story} activeOutlets={activeOutlets} />
      <OutletNames story={story} names={names} max={3} />
    </article>
  );
}
