import Link from "next/link";
import { TOPIC_LABELS, type Topic } from "@/lib/api";

type Props = {
  current?: string;
  /** Monta o link mantendo os outros filtros da página. */
  href: (topic?: string) => string;
  /** Contagem por seção no período; seções com zero notícias ficam esmaecidas. */
  topics?: Topic[];
};

/** Abas de seção: Todas · Política · Economia · ... (filtros da página, acima do conteúdo). */
export function TopicTabs({ current, href, topics }: Props) {
  const counts = new Map(topics?.map((t) => [t.key, t.article_count]));
  return (
    <nav className="topic-tabs" aria-label="Seções">
      <Link href={href(undefined)} className={!current ? "topic active" : "topic"} aria-current={!current ? "page" : undefined}>
        Todas
      </Link>
      {Object.entries(TOPIC_LABELS).map(([key, label]) => {
        const n = counts.get(key);
        const empty = topics && !n && current !== key;
        return (
          <Link
            key={key}
            href={href(key)}
            className={`topic${current === key ? " active" : ""}${empty ? " empty" : ""}`}
            aria-current={current === key ? "page" : undefined}
          >
            {label}
            {n ? <span className="count">{n}</span> : null}
          </Link>
        );
      })}
    </nav>
  );
}

export function TopicBadge({ topic }: { topic: string | null | undefined }) {
  if (!topic || topic === "outros") return null;
  return <span className={`topic-badge t-${topic}`}>{TOPIC_LABELS[topic] ?? topic}</span>;
}
