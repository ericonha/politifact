import Link from "next/link";
import { notFound } from "next/navigation";
import { toggleFavorite } from "@/app/actions";
import { CompareBars } from "@/components/charts/CompareBars";
import { LineChart } from "@/components/charts/LineChart";
import { ToneBars } from "@/components/charts/ToneBars";
import { PageLayout, Sidebar } from "@/components/Sidebar";
import { BiasSections } from "@/components/BiasSections";
import { formatDate, getCollectionStatus, getOutletBias, getOutletProfile, getRatings } from "@/lib/api";

const WINDOWS = [
  { value: "7d", label: "7 dias" },
  { value: "30d", label: "30 dias" },
];

function pct(x: number | null) {
  return x == null ? "—" : `${Math.round(x * 100)}%`;
}

export default async function OutletProfilePage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ janela?: string }>;
}) {
  const { id } = await params;
  const { janela } = await searchParams;
  const outletId = Number(id);
  if (!Number.isInteger(outletId)) notFound();
  const win = janela === "30d" ? "30d" : "7d";

  const [{ data: p, error }, status, ratings, { data: bias }] = await Promise.all([
    getOutletProfile(outletId, win),
    getCollectionStatus(),
    getRatings().catch(() => []),
    getOutletBias(outletId, win),
  ]);
  if (!p) {
    if (error?.includes("não encontrado")) notFound();
    return <div className="empty">Não foi possível montar o perfil: {error}</div>;
  }
  const myRatings = ratings.filter((r) => r.outlet_id === outletId);
  const groupName = p.peers.group === "nacional" ? "nacionais" : "internacionais";
  const small = p.totals.articles < p.peers.min_articles;

  return (
    <PageLayout
      sidebar={
        <Sidebar
          title="Veículo"
          intro={<Link href="/veiculos">Todos os veículos</Link>}
          basePath={`/veiculos/${outletId}`}
          params={{ janela: win }}
          status={status}
          period
          windows={WINDOWS}
        />
      }
    >
      <div className="profile-head">
        <form action={toggleFavorite}>
          <input type="hidden" name="outlet_id" value={p.outlet.id} />
          <input type="hidden" name="favorite" value={p.outlet.favorite ? "false" : "true"} />
          <button type="submit" className={p.outlet.favorite ? "star on" : "star"} aria-pressed={p.outlet.favorite}
                  aria-label={p.outlet.favorite ? `Tirar ${p.outlet.name} dos favoritos` : `Favoritar ${p.outlet.name}`}>
            <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 3.5l2.6 5.3 5.9.9-4.25 4.1 1 5.85L12 16.9l-5.25 2.75 1-5.85L3.5 9.7l5.9-.9z" />
            </svg>
          </button>
        </form>
        <h2 className="lead-title" style={{ maxWidth: "none" }}>{p.outlet.name}</h2>
        {p.outlet.language.startsWith("en") && <span className="lang-badge">EN</span>}
      </div>

      <div className="profile-facts">
        <span><strong>{p.totals.articles}</strong> notícias nos {p.range.label}</span>
        <span><strong>{p.totals.stories}</strong> histórias, <strong>{p.totals.exclusive_stories}</strong> só dele</span>
        <span>comparado a {p.peers.count} veículos {groupName}</span>
        <span>
          {myRatings.length
            ? myRatings.map((r) => `${r.rating_label} segundo ${r.provider}`).join("; ")
            : "sem avaliação de orientação atribuída"}
        </span>
      </div>

      <p className="callout">
        Isto não é uma nota de viés nem um rótulo de esquerda ou direita. São medidas das manchetes e resumos
        deste veículo no período, lado a lado com a média dos outros veículos {groupName}. Diferença em relação à
        média descreve escolhas de pauta e de texto, não intenção.
        {small && <> <strong>Amostra pequena no período</strong>: veja 30 dias para números mais estáveis.</>}
      </p>

      <section className="card">
        <h2>Notícias publicadas</h2>
        <p className="sub">Por {p.range.bucket_seconds >= 86400 ? "dia" : "período de 6 horas"}, pela data de publicação.</p>
        <LineChart
          buckets={p.timeline.buckets}
          bucketSeconds={p.range.bucket_seconds}
          valueLabel="notícias"
          ariaLabel={`Notícias de ${p.outlet.name} ao longo do tempo`}
          series={[{ key: "o", label: p.outlet.name, color: "var(--series-1)", values: p.timeline.counts }]}
          height={200}
        />
      </section>

      <section className="card">
        <h2>Em que seções publica</h2>
        <p className="sub">Parte das notícias do veículo em cada seção.</p>
        <CompareBars
          ariaLabel="Seções: este veículo e média dos outros"
          rows={p.sections.filter((s) => s.count > 0 || (s.average_share ?? 0) > 0.02).map((s) => ({
            key: s.topic, label: s.label, share: s.share, average: s.average_share, detail: `${s.count} notícias`,
          }))}
        />
      </section>

      <section className="card">
        <h2>Quem aparece nas manchetes</h2>
        <p className="sub">
          Parte das manchetes que citam cada nome, entre {p.totals.analyzed_headlines} manchetes analisadas.
          Conta o nome escrito: &ldquo;ex-presidente&rdquo; no lugar do nome não conta.
        </p>
        {p.actors.length === 0 ? (
          <div className="empty">Nenhuma manchete analisada no período.</div>
        ) : (
          <CompareBars
            ariaLabel="Atores nas manchetes: este veículo e média dos outros"
            rows={p.actors.map((a) => ({
              key: a.key, label: a.name, share: a.share, average: a.average_share, detail: `${a.count} manchetes`,
            }))}
          />
        )}
      </section>

      <section className="card">
        <h2>Como as manchetes apresentam os principais atores</h2>
        <p className="sub">
          Leitura da IA local sobre o tom da manchete em relação ao ator principal. Só leituras que passaram na
          checagem (tom negativo ou positivo exige trecho literal do texto). {p.totals.ai_readings} leituras no período.
        </p>
        {p.tone.length === 0 ? (
          <div className="empty">
            Leituras insuficientes (é preciso pelo menos 3 por ator). Elas aparecem com o Ollama ligado, para
            histórias cobertas por 2 ou mais veículos.
          </div>
        ) : (
          <ToneBars rows={p.tone} />
        )}
      </section>

      <section className="card">
        <h2>Forma das manchetes</h2>
        <p className="sub">
          Parte das manchetes com cada recurso, medida por regras fixas, sem IA: fala atribuída (&ldquo;diz&rdquo;,
          &ldquo;critica&rdquo;…), aspas, termo de impacto e pergunta.
        </p>
        <CompareBars
          ariaLabel="Forma das manchetes: este veículo e média dos outros"
          rows={p.form.map((f) => ({ key: f.key, label: f.label, share: f.share, average: f.average_share, detail: `n=${f.n}` }))}
        />
      </section>

      <section className="card">
        <h2>Exclusividade</h2>
        <p className="sub">Parte das histórias do veículo que nenhum outro veículo monitorado cobriu no período.</p>
        <CompareBars
          ariaLabel="Exclusividade: este veículo e média dos outros"
          rows={[{ key: "excl", label: "Só ele cobriu", share: p.exclusivity.share, average: p.exclusivity.average_share,
                   detail: `${p.totals.exclusive_stories} de ${p.totals.stories} histórias` }]}
          max={1}
        />
        <p className="callout">
          Exclusividade alta pode ser pauta própria, cobertura de nicho (economia, regional) ou agrupamento
          que não juntou notícias parecidas. Exclusividade {pct(p.exclusivity.share)} não indica omissão de ninguém.
        </p>
      </section>

      {bias && <BiasSections b={bias} groupName={groupName} />}

      <details className="table-view">
        <summary>Como isto é calculado</summary>
        <ul className="limits">
          <li>Período: {formatDate(p.range.start)} a {formatDate(p.range.end)}, pela data de publicação. Duplicatas do mesmo veículo contam uma vez.</li>
          <li>&ldquo;Média dos outros&rdquo; é a média simples entre os veículos {groupName} com pelo menos {p.peers.min_articles} notícias no período (cada veículo pesa igual).</li>
          <li>Atores e forma das manchetes vêm da análise por regras (mesmas da página de cada história). Tom vem da leitura da IA local, só para histórias com 2+ veículos.</li>
          <li>As quatro medidas de &ldquo;Diferenças de pauta e de texto&rdquo; vêm de contagens e comparações fixas (sem IA): omissões entre histórias cobertas por 4+ veículos; atraso pela hora de publicação do feed; palavras por razão de chances log com a mesma história dos dois lados; edições pela comparação de versões coletadas.</li>
          <li>Avaliações de orientação, quando existirem, vêm de avaliadores externos identificados (página Veículos) e não entram em nenhum cálculo desta página.</li>
        </ul>
      </details>
    </PageLayout>
  );
}
