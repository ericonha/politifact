import { PageLayout, Sidebar } from "@/components/Sidebar";
import Link from "next/link";
import { LineChart } from "@/components/charts/LineChart";
import { TopicBadge } from "@/components/TopicTabs";
import { formatDate, getCollectionStatus, getCompare, getStories } from "@/lib/api";
import { bucketRangeLabel, seriesColor } from "@/lib/chart-utils";

const MAX = 3;

function short(title: string, n = 48): string {
  return title.length > n ? `${title.slice(0, n - 1)}…` : title;
}

export default async function ComparePage({
  searchParams,
}: {
  searchParams: Promise<{ ids?: string | string[] }>;
}) {
  const { ids: raw } = await searchParams;
  const ids = [...new Set((Array.isArray(raw) ? raw : raw ? [raw] : []).map(Number).filter(Number.isInteger))];

  if (ids.length < 2) return <Picker selected={ids} />;
  if (ids.length > MAX) {
    return (
      <ComparePageLayout>
        <div className="empty">Escolha no máximo {MAX} histórias. <Link href="/cobertura">Voltar</Link></div>
      </ComparePageLayout>
    );
  }

  const { data, error } = await getCompare(ids);
  if (!data) {
    return (
      <ComparePageLayout>
        <div className="empty">Não foi possível comparar: {error}</div>
      </ComparePageLayout>
    );
  }

  const seriesOf = new Map(data.timeline.series.map((s) => [s.story_id, s.counts]));
  const outlets = [...new Set(data.stories.flatMap((s) => s.outlets.map((o) => o.outlet_name)))].sort();

  return (
    <ComparePageLayout>

      <section className="card">
        <h2>Notícias ao longo do tempo</h2>
        <p className="sub">Todas as notícias de cada história, somando os veículos.</p>
        <LineChart
          buckets={data.timeline.buckets}
          bucketSeconds={data.bucket_seconds}
          valueLabel="notícias"
          ariaLabel="Notícias por história ao longo do tempo"
          series={data.stories.map((s, i) => ({
            key: String(s.id),
            label: short(s.title, 32),
            color: seriesColor(i),
            values: seriesOf.get(s.id) ?? [],
          }))}
        />
        <details className="table-view">
          <summary>Ver tabela</summary>
          <table>
            <thead>
              <tr>
                <th>Período</th>
                {data.stories.map((s) => <th key={s.id} className="num-cell">{short(s.title, 24)}</th>)}
              </tr>
            </thead>
            <tbody>
              {data.timeline.buckets.map((b, i) => (
                <tr key={b}>
                  <td>{bucketRangeLabel(b, data.bucket_seconds)}</td>
                  {data.stories.map((s) => <td key={s.id} className="num-cell">{seriesOf.get(s.id)?.[i] ?? 0}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      </section>

      <section className="card">
        <h2>Quem cobriu</h2>
        <p className="sub">Notícias de cada veículo em cada história.</p>
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>Veículo</th>
                {data.stories.map((s, i) => (
                  <th key={s.id} className="num-cell">
                    <span className="swatch" style={{ background: seriesColor(i) }} />
                    {short(s.title, 28)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {outlets.map((name) => (
                <tr key={name}>
                  <td>{name}</td>
                  {data.stories.map((s) => {
                    const o = s.outlets.find((x) => x.outlet_name === name);
                    return <td key={s.id} className="num-cell">{o ? o.article_count : "—"}</td>;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="compare-grid">
        {data.stories.map((s, i) => (
          <section key={s.id} className="card">
            <h3>
              <span className="swatch" style={{ background: seriesColor(i) }} />
              <Link href={`/historias/${s.id}`}>{s.title}</Link>
            </h3>
            <p className="sub">{s.article_count} notícias</p>
            <p className="sub" style={{ marginBottom: 4 }}>Quem publicou primeiro:</p>
            <ol className="first-list">
              {s.outlets.map((o, k) => (
                <li key={o.outlet_id}>
                  <span>{k === 0 ? <strong>{o.outlet_name}</strong> : o.outlet_name}</span>
                  <span className="muted">{formatDate(o.first_published_at)}</span>
                </li>
              ))}
            </ol>
          </section>
        ))}
      </div>
    </ComparePageLayout>
  );
}

/** Menos de 2 histórias escolhidas: oferece as recentes para marcar. */
async function Picker({ selected }: { selected: number[] }) {
  const stories = (await getStories("3d")).slice(0, 40);
  const listed = new Set(stories.map((s) => s.id));
  const extra = selected.filter((id) => !listed.has(id));
  return (
    <ComparePageLayout>
      <p className="note">Marque 2 ou 3 histórias dos últimos 3 dias.</p>
      <form action="/comparar" method="get" className="card">
        {extra.map((id) => (
          <p key={id} className="note">
            <input type="hidden" name="ids" value={id} />
            Já escolhida: <Link href={`/historias/${id}`}>história {id}</Link>. Marque mais 1 ou 2.
          </p>
        ))}
        <ul className="articles">
          {stories.map((s) => (
            <li key={s.id}>
              <label style={{ display: "flex", gap: 10, alignItems: "baseline" }}>
                <input type="checkbox" name="ids" value={s.id} defaultChecked={selected.includes(s.id)} />
                <span>
                  <TopicBadge topic={s.topic} />
                  {s.title} <span className="muted">· {s.outlet_count} veículos, {s.article_count} notícias</span>
                </span>
              </label>
            </li>
          ))}
        </ul>
        <button type="submit" className="button small" style={{ marginTop: 12 }}>Comparar</button>
      </form>
    </ComparePageLayout>
  );
}


async function ComparePageLayout({ children }: { children: React.ReactNode }) {
  const status = await getCollectionStatus();
  return (
    <PageLayout
      sidebar={
        <Sidebar
          title="Comparar histórias"
          intro="Até 3 histórias lado a lado: quem cobriu, quando e quanto."
          basePath="/comparar"
          params={{}}
          status={status}
        />
      }
    >
      {children}
    </PageLayout>
  );
}
