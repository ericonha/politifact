import Link from "next/link";
import { BarChart } from "@/components/charts/BarChart";
import { ColumnChart } from "@/components/charts/ColumnChart";
import { SmallMultiples } from "@/components/charts/SmallMultiples";
import { TopicBadge, TopicTabs } from "@/components/TopicTabs";
import {
  GROUPS,
  TOPIC_LABELS,
  WINDOWS,
  formatDate,
  getCoverage,
  parseGroup,
  parseTopic,
  parseWindow,
  type CoverageReport,
  type Group,
} from "@/lib/api";
import { bucketRangeLabel } from "@/lib/chart-utils";

type SP = { janela?: string; de?: string; ate?: string; secao?: string; grupo?: string };

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const ONE_HUE = "var(--series-1)";

function bucketText(seconds: number): string {
  if (seconds >= 86400) return "por dia";
  if (seconds >= 6 * 3600) return "a cada 6 horas";
  return "por hora";
}

function pct(x: number | null): string {
  return x == null ? "—" : `${Math.round(x * 100)}%`;
}

function coverageStatus(x: number | null): "good" | "warning" | "critical" | null {
  if (x == null) return null;
  if (x >= 0.95) return "good";
  if (x >= 0.7) return "warning";
  return "critical";
}

const STATUS_TEXT = { good: "completa", warning: "com lacunas", critical: "muitas lacunas" };

export default async function CoveragePage({ searchParams }: { searchParams: Promise<SP> }) {
  const sp = await searchParams;
  const topic = parseTopic(sp.secao);
  const group = parseGroup(sp.grupo);
  const custom = !!(sp.de && sp.ate && DATE_RE.test(sp.de) && DATE_RE.test(sp.ate));
  const win = parseWindow(sp.janela);
  const { data, error } = await getCoverage(
    custom ? { from: sp.de, to: sp.ate, topic, group } : { window: win, topic, group },
  );

  const href = (p: { janela?: string; secao?: string | null; grupo?: Group | null }) => {
    const q = new URLSearchParams();
    if (p.janela) q.set("janela", p.janela);
    else if (custom) {
      q.set("de", sp.de!);
      q.set("ate", sp.ate!);
    } else q.set("janela", win);
    const t = p.secao === null ? undefined : p.secao ?? topic;
    if (t) q.set("secao", t);
    const g = p.grupo === null ? undefined : p.grupo ?? group;
    if (g) q.set("grupo", g);
    return `/cobertura?${q}`;
  };

  return (
    <>
      <div className="toolbar">
        <h1>Cobertura{topic ? ` · ${TOPIC_LABELS[topic]}` : ""}</h1>
        <div className="tabs" aria-label="Grupo de veículos">
          {GROUPS.map((g) => (
            <Link
              key={g.label}
              href={href({ grupo: g.value ?? null })}
              className={g.value === group ? "tab active" : "tab"}
            >
              {g.label}
            </Link>
          ))}
        </div>
      </div>

      <div className="filter-row">
        <div className="tabs">
          {WINDOWS.map((w) => (
            <Link key={w.value} href={href({ janela: w.value })} className={!custom && w.value === win ? "tab active" : "tab"}>
              {w.label}
            </Link>
          ))}
        </div>
        <form action="/cobertura" method="get">
          <label>
            de <input type="date" name="de" defaultValue={custom ? sp.de : ""} required />
          </label>
          <label>
            até <input type="date" name="ate" defaultValue={custom ? sp.ate : ""} required />
          </label>
          {topic && <input type="hidden" name="secao" value={topic} />}
          {group && <input type="hidden" name="grupo" value={group} />}
          <button type="submit" className={custom ? "button small" : "button small secondary"}>Aplicar</button>
        </form>
      </div>

      <TopicTabs current={topic} href={(t) => href({ secao: t ?? null })} />

      {error || !data ? (
        <div className="empty">Não foi possível montar o painel: {error ?? "erro desconhecido"}</div>
      ) : (
        <Dashboard data={data} topic={topic} group={group} topicHref={(t) => href({ secao: t })} />
      )}
    </>
  );
}

function Dashboard({
  data,
  topic,
  group,
  topicHref,
}: {
  data: CoverageReport;
  topic?: string;
  group?: Group;
  topicHref: (topic: string) => string;
}) {
  const { totals, range } = data;
  const byVolume = [...data.outlets].sort((a, b) => b.article_count - a.article_count || a.name.localeCompare(b.name));
  const shown = byVolume.filter((o) => o.active || o.article_count > 0);
  const nameOf = new Map(data.outlets.map((o) => [o.id, o.name]));
  const seriesById = new Map(data.timeline.series.map((s) => [s.outlet_id, s.counts]));
  const active = data.outlets.filter((o) => o.active);
  const meanCovered = active.length
    ? active.reduce((sum, o) => sum + (o.covered_fraction ?? 0), 0) / active.length
    : null;
  const totalGapHours = active.reduce((s, o) => s + o.gap_hours, 0);
  const inactive = data.outlets.filter((o) => !o.active);
  const groupText = group === "nacional" ? "nacionais " : group === "internacional" ? "internacionais " : "";
  const mixed = !group && new Set(active.map((o) => o.group)).size > 1;

  return (
    <>
      <p className="note">
        {range.label} · {formatDate(range.start)} a {formatDate(range.end)}. Contagens entre os{" "}
        {totals.active_outlets} veículos {groupText}monitorados, não cobertura total da mídia.
      </p>
      {mixed && (
        <p className="callout">
          Nacionais e internacionais juntos: veículos estrangeiros publicam poucas notícias sobre o Brasil e
          parecem &ldquo;ignorar&rdquo; histórias numa comparação direta. Para comparar veículos, filtre um grupo.
        </p>
      )}

      <section className="kpis" aria-label="Resumo">
        <div className="kpi">
          <div className="kpi-label">Notícias</div>
          <div className="kpi-value">{totals.articles}</div>
          <div className="kpi-note">sem contar duplicatas do mesmo veículo</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Histórias</div>
          <div className="kpi-value">{totals.stories}</div>
          <div className="kpi-note">
            {totals.stories_all_active_outlets} cobertas por todos os {totals.active_outlets} veículos
          </div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Tempo com coleta</div>
          <div className="kpi-value">{pct(meanCovered)}</div>
          <div className="kpi-note">
            {totalGapHours > 0 ? `média dos veículos; lacunas somam ${totalGapHours.toFixed(1)} h` : "sem lacunas no período"}
          </div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Aguardando revisão</div>
          <div className="kpi-value">{totals.pending_review}</div>
          <div className="kpi-note">
            <Link href="/revisao">notícias fora das histórias</Link>
          </div>
        </div>
      </section>

      <section className="card">
        <h2>Notícias publicadas ao longo do tempo</h2>
        <p className="sub">
          Um gráfico por veículo, {bucketText(range.bucket_seconds)}, pela data de publicação, do maior volume para o menor.
        </p>
        <SmallMultiples
          buckets={data.timeline.buckets}
          bucketSeconds={range.bucket_seconds}
          valueLabel="notícias"
          ariaLabel={`Notícias por veículo ${bucketText(range.bucket_seconds)}`}
          items={shown.map((o) => ({
            key: String(o.id),
            label: o.name,
            sublabel: o.language.startsWith("en") ? "em inglês" : undefined,
            values: seriesById.get(o.id) ?? [],
          }))}
        />
        <details className="table-view">
          <summary>Ver tabela</summary>
          <div className="scroll">
            <table>
              <thead>
                <tr>
                  <th>Período</th>
                  {shown.map((o) => <th key={o.id} className="num-cell">{o.name}</th>)}
                </tr>
              </thead>
              <tbody>
                {data.timeline.buckets.map((b, i) => (
                  <tr key={b}>
                    <td>{bucketRangeLabel(b, range.bucket_seconds)}</td>
                    {shown.map((o) => <td key={o.id} className="num-cell">{seriesById.get(o.id)?.[i] ?? 0}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </section>

      <div className="grid-2">
        <section className="card">
          <h2>Volume por veículo</h2>
          <p className="sub">Notícias publicadas no período.</p>
          <BarChart
            valueLabel="notícias"
            ariaLabel="Notícias por veículo no período"
            bars={shown.map((o) => ({
              key: String(o.id),
              label: o.name,
              value: o.article_count,
              color: ONE_HUE,
              note: `${o.story_count} histórias, ${o.exclusive_story_count} só dele`,
            }))}
          />
        </section>
        <section className="card">
          <h2>Alcance das histórias</h2>
          <p className="sub">Quantas histórias foram cobertas por 1, 2, 3… veículos.</p>
          {data.reach_distribution.length === 0 ? (
            <div className="empty">Nenhuma história no período.</div>
          ) : (
            <ColumnChart
              valueLabel="histórias"
              ariaLabel="Histórias por número de veículos que as cobriram"
              columns={data.reach_distribution.map((r) => ({
                key: String(r.outlets),
                label: String(r.outlets),
                value: r.stories,
              }))}
            />
          )}
          <p className="sub" style={{ marginTop: 6 }}>Eixo horizontal: número de veículos que cobriram a história.</p>
        </section>
      </div>

      <section className="card">
        <h2>Por veículo</h2>
        <p className="sub">Volume, histórias exclusivas e qualidade da coleta no período.</p>
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>Veículo</th>
                <th className="num-cell">Notícias</th>
                <th className="num-cell">Histórias</th>
                <th className="num-cell">Só ele cobriu</th>
                <th>Tempo com coleta</th>
                <th className="num-cell">Coletas com falha</th>
                <th className="num-cell">Possíveis perdas</th>
                <th>Última coleta ok</th>
              </tr>
            </thead>
            <tbody>
              {byVolume.map((o) => {
                const st = coverageStatus(o.covered_fraction);
                return (
                  <tr key={o.id}>
                    <td>
                      {o.language.startsWith("en") && <span className="lang-badge">EN</span>}
                      {o.name}
                      {!group && <div className="muted">{o.group}</div>}
                      {!o.active && <div className="muted">sem coleta: {o.collection_notes ?? "desativado"}</div>}
                    </td>
                    <td className="num-cell">{o.article_count}</td>
                    <td className="num-cell">{o.story_count}</td>
                    <td className="num-cell">{o.exclusive_story_count}</td>
                    <td>
                      {st ? (
                        <span className={`pill pill-${st}`}>{pct(o.covered_fraction)} · {STATUS_TEXT[st]}</span>
                      ) : "—"}
                      {o.gaps.length > 0 && (
                        <div className="muted">
                          maior lacuna: {formatDate(o.gaps[0].start)} a {formatDate(o.gaps[0].end)}
                        </div>
                      )}
                    </td>
                    <td className="num-cell">{o.failed_runs}</td>
                    <td className="num-cell">{o.possible_overflow_runs}</td>
                    <td>{formatDate(o.last_success_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="callout">
          &ldquo;Só ele cobriu&rdquo; conta histórias com notícia de um único veículo entre os monitorados.
          Diferença de cobertura não prova omissão intencional, coordenação ou motivação política: pode ser
          lacuna de coleta, agrupamento errado, idioma diferente ou simplesmente pauta.
        </p>
      </section>

      {!topic && data.topics.length > 0 && <TopicMatrix data={data} outlets={shown} topicHref={topicHref} />}

      <section className="card">
        <h2>Histórias mais cobertas</h2>
        <p className="sub">Ordenadas por número de veículos e depois por volume. Marque 2 ou 3 para comparar.</p>
        {data.top_stories.length === 0 ? (
          <div className="empty">Nenhuma história no período.</div>
        ) : (
          <form action="/comparar" method="get">
            <div className="scroll">
              <table>
                <thead>
                  <tr>
                    <th aria-label="Selecionar" />
                    <th>História</th>
                    <th className="num-cell">Veículos</th>
                    <th className="num-cell">Notícias</th>
                  </tr>
                </thead>
                <tbody>
                  {data.top_stories.map((s) => (
                    <tr key={s.id}>
                      <td><input type="checkbox" name="ids" value={s.id} aria-label={`Comparar: ${s.title}`} /></td>
                      <td>
                        {!topic && <TopicBadge topic={s.topic} />}
                        <Link href={`/historias/${s.id}`} className="story-link">{s.title}</Link>
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
            <button type="submit" className="button small" style={{ marginTop: 12 }}>Comparar selecionadas</button>
          </form>
        )}
      </section>

      <section className="card">
        <h2>Limitações deste período</h2>
        <ul className="limits">
          {inactive.map((o) => (
            <li key={o.id}><strong>{o.name}</strong> não está sendo coletado ({o.collection_notes ?? "desativado"}).</li>
          ))}
          {active.filter((o) => o.gap_hours > 0).map((o) => (
            <li key={o.id}>
              {o.name}: {o.gap_hours.toFixed(1)} h sem coleta bem-sucedida (o computador desligado também conta).
              Notícias desse intervalo podem faltar.
            </li>
          ))}
          {active.filter((o) => o.possible_overflow_runs > 0).map((o) => (
            <li key={`of-${o.id}`}>
              {o.name}: em {o.possible_overflow_runs} coleta(s) todas as notícias do feed eram novas, então o
              feed pode ter “passado” notícias antes da coleta seguinte.
            </li>
          ))}
          {active.some((o) => o.language.startsWith("en")) && (
            <li>Veículos em inglês só se juntam às histórias em português quando os embeddings (Ollama) estão ligados.</li>
          )}
          {totals.undated_articles > 0 && (
            <li>{totals.undated_articles} notícias vieram sem data de publicação e ficaram fora das contagens.</li>
          )}
          {totals.duplicates_excluded > 0 && (
            <li>{totals.duplicates_excluded} duplicatas do mesmo veículo não foram contadas.</li>
          )}
          {totals.pending_review > 0 && (
            <li>{totals.pending_review} notícias aguardam revisão e não entram em nenhuma história.</li>
          )}
          {totals.not_clustered - totals.pending_review > 0 && (
            <li>{totals.not_clustered - totals.pending_review} notícias ainda não foram agrupadas (rodam após a próxima coleta).</li>
          )}
          <li>Seções são atribuídas pela categoria do feed, pelo caminho da URL ou por palavras-chave, nessa ordem; podem errar.</li>
        </ul>
        <details className="table-view">
          <summary>Como contamos</summary>
          <ul className="limits">
            <li>Notícia conta pela <strong>data de publicação</strong> informada pelo veículo, nunca pela hora em que a coletamos.</li>
            <li>Duplicata do mesmo veículo (mesmo texto ou título quase igual) conta uma vez. Republicação de outro veículo conta para quem republicou.</li>
            <li>História coberta por um veículo = pelo menos uma notícia dele, publicada no período, agrupada nela.</li>
            <li>Tempo com coleta = parte do período sem intervalos maiores que {2 * data.collection_interval_minutes} min entre coletas bem-sucedidas.</li>
            <li>Volume de notícias não é audiência: uma notícia muito lida e uma pouco lida contam igual.</li>
          </ul>
        </details>
      </section>
    </>
  );
}

function TopicMatrix({
  data,
  outlets,
  topicHref,
}: {
  data: CoverageReport;
  outlets: CoverageReport["outlets"];
  topicHref: (topic: string) => string;
}) {
  // Uma linha por veículo; cada célula = parte das notícias DAQUELE veículo na seção (soma 100% por linha).
  return (
    <section className="card">
      <h2>Seções por veículo</h2>
      <p className="sub">Que parte das notícias de cada veículo caiu em cada seção. Cor mais forte = parte maior.</p>
      <div className="scroll">
        <table className="matrix">
          <thead>
            <tr>
              <th>Veículo</th>
              {data.topics.map((t) => (
                <th key={t.topic} className="num-cell"><Link href={topicHref(t.topic)}>{t.label}</Link></th>
              ))}
            </tr>
          </thead>
          <tbody>
            {outlets.filter((o) => o.article_count > 0).map((o) => (
              <tr key={o.id}>
                <td>{o.name}</td>
                {data.topics.map((t) => {
                  const n = t.by_outlet[String(o.id)] ?? 0;
                  const share = o.article_count ? n / o.article_count : 0;
                  return (
                    <td
                      key={t.topic}
                      className="num-cell heat"
                      style={{ background: `color-mix(in srgb, var(--series-1) ${Math.round(share * 70)}%, transparent)` }}
                      title={`${o.name}: ${n} de ${o.article_count} notícias em ${t.label}`}
                    >
                      {n ? `${Math.round(share * 100)}%` : "—"}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
