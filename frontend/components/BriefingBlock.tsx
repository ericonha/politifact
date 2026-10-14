import Link from "next/link";
import { formatTime, timeAgo, type Briefing } from "@/lib/api";

function shorten(t: string, n = 70) {
  return t.length > n ? `${t.slice(0, n - 1)}…` : t;
}

/** Resumo de uma seção: panorama + pontos, cada ponto com as histórias de onde saiu. */
export function BriefingBlock({ b, headingLevel = 2 }: { b: Briefing; headingLevel?: 2 | 3 }) {
  const H = headingLevel === 2 ? "h2" : "h3";
  const dropped = b.validation?.problems.length ?? 0;
  return (
    <section className="briefing" aria-labelledby={`brief-${b.topic}`}>
      <H id={`brief-${b.topic}`} className="briefing-title">{b.label}</H>
      {b.overview && <p className="briefing-overview">{b.overview}</p>}
      <ul className="briefing-points">
        {b.points.map((p, i) => (
          <li key={i}>
            <p>{p.text}</p>
            <div className="briefing-sources">
              Fonte{p.stories.length > 1 ? "s" : ""}:{" "}
              {p.stories.map((s, k) => (
                <span key={s.id}>
                  {k > 0 && "; "}
                  <Link href={`/historias/${s.id}`}>{shorten(s.title)}</Link>{" "}
                  <span className="muted">({s.outlet_count} {s.outlet_count === 1 ? "veículo" : "veículos"})</span>
                </span>
              ))}
            </div>
          </li>
        ))}
      </ul>
      <p className="briefing-foot">
        Escrito por IA local ({b.model}) às {formatTime(b.generated_at)}, {timeAgo(b.generated_at)}, a partir das{" "}
        {b.story_count} histórias mais relevantes da seção.
        {dropped > 0 && (
          <span title={b.validation?.problems.join("\n")}>
            {" "}A checagem descartou {dropped} {dropped === 1 ? "trecho" : "trechos"} sem apoio no texto das notícias.
          </span>
        )}
      </p>
    </section>
  );
}
