import { toggleFavorite } from "@/app/actions";
import { PageLayout, Sidebar } from "@/components/Sidebar";
import { formatDate, getCollectionStatus, getOutlets, getRatings, type Outlet, type Rating } from "@/lib/api";

function RatingCell({ ratings }: { ratings: Rating[] }) {
  if (!ratings.length) return <span className="muted">nenhuma avaliação cadastrada</span>;
  const current = ratings.filter((r) => !r.valid_until);
  const shown = current.length ? current : ratings.slice(-1);
  return (
    <div>
      {shown.map((r) => (
        <div key={`${r.provider}-${r.assessed_at}`}>
          <strong>{r.rating_label}</strong>{" "}
          <span className="muted">
            segundo <a href={r.methodology_url} target="_blank" rel="noopener noreferrer">{r.provider}</a>,{" "}
            {formatDate(r.assessed_at).split(",")[0]}
          </span>
        </div>
      ))}
      {ratings.length > shown.length && <div className="muted">{ratings.length - shown.length} avaliação(ões) anterior(es) no histórico</div>}
    </div>
  );
}

function OutletTable({ outlets, ratings }: { outlets: Outlet[]; ratings: Map<number, Rating[]> }) {
  return (
    <div className="scroll">
      <table>
        <thead>
          <tr>
            <th>Veículo</th>
            <th>Situação</th>
            <th>Orientação (avaliação atribuída)</th>
            <th>Feeds</th>
            <th>Observações de coleta</th>
          </tr>
        </thead>
        <tbody>
          {outlets.map((o) => (
            <tr key={o.id}>
              <td>
                <form action={toggleFavorite} style={{ display: "inline" }}>
                  <input type="hidden" name="outlet_id" value={o.id} />
                  <input type="hidden" name="favorite" value={o.favorite ? "false" : "true"} />
                  <button type="submit" className={o.favorite ? "star on" : "star"} aria-pressed={o.favorite}
                          aria-label={o.favorite ? `Tirar ${o.name} dos favoritos` : `Favoritar ${o.name}`}
                          style={{ display: "inline-grid", verticalAlign: "middle", marginRight: 4 }}>
                    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M12 3.5l2.6 5.3 5.9.9-4.25 4.1 1 5.85L12 16.9l-5.25 2.75 1-5.85L3.5 9.7l5.9-.9z" />
                    </svg>
                  </button>
                </form>
                {o.language.startsWith("en") && <span className="lang-badge">EN</span>}
                <strong>{o.name}</strong>
                <div className="muted">{o.canonical_domain}</div>
              </td>
              <td>
                <span className={`pill ${o.active ? "pill-good" : "pill-critical"}`}>
                  {o.active ? "coletando" : "desativado"}
                </span>
              </td>
              <td><RatingCell ratings={ratings.get(o.id) ?? []} /></td>
              <td className="muted" style={{ wordBreak: "break-all" }}>{o.feed_urls.length ? o.feed_urls.join(", ") : "—"}</td>
              <td className="muted">{o.collection_notes ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default async function OutletsPage() {
  const [allOutlets, allRatings, status] = await Promise.all([getOutlets(), getRatings(), getCollectionStatus()]);
  const outlets = allOutlets.sort((a, b) => a.name.localeCompare(b.name));
  const ratings = new Map<number, Rating[]>();
  for (const r of allRatings) ratings.set(r.outlet_id, [...(ratings.get(r.outlet_id) ?? []), r]);
  const national = outlets.filter((o) => o.outlet_group === "nacional");
  const international = outlets.filter((o) => o.outlet_group === "internacional");

  return (
    <PageLayout
      sidebar={
        <Sidebar
          title="Veículos"
          intro="Os veículos monitorados, como cada um é coletado e quais são seus favoritos."
          basePath="/veiculos"
          params={{}}
          status={status}
        />
      }
    >
      <p className="note">
        {outlets.filter((o) => o.active).length} de {outlets.length} com coleta ativa. Para mudar feeds ou
        ativar um veículo, edite <code>backend/app/seed.py</code> e rode <code>docker compose up -d</code>.
      </p>
      <p className="callout">
        Orientação política só aparece quando vem de um avaliador externo identificado, com metodologia e data
        (arquivo <code>backend/data/outlet_ratings.json</code>). O sistema não classifica veículos sozinho, e a
        orientação de um veículo não diz nada sobre o enquadramento de cada notícia dele.
      </p>
      <section className="card">
        <h2>Nacionais</h2>
        <OutletTable outlets={national} ratings={ratings} />
      </section>
      <section className="card">
        <h2>Internacionais</h2>
        <p className="sub">Comparados entre si no painel de cobertura (filtro &ldquo;Internacionais&rdquo;).</p>
        <OutletTable outlets={international} ratings={ratings} />
      </section>
    </PageLayout>
  );
}
