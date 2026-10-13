import { getOutlets, type Outlet } from "@/lib/api";

function OutletTable({ outlets }: { outlets: Outlet[] }) {
  return (
    <div className="scroll">
      <table>
        <thead>
          <tr>
            <th>Veículo</th>
            <th>Situação</th>
            <th>Feeds</th>
            <th>Observações de coleta</th>
          </tr>
        </thead>
        <tbody>
          {outlets.map((o) => (
            <tr key={o.id}>
              <td>
                {o.language.startsWith("en") && <span className="lang-badge">EN</span>}
                <strong>{o.name}</strong>
                <div className="muted">{o.canonical_domain}</div>
              </td>
              <td>
                <span className={`pill ${o.active ? "pill-good" : "pill-critical"}`}>
                  {o.active ? "coletando" : "desativado"}
                </span>
              </td>
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
  const outlets = (await getOutlets()).sort((a, b) => a.name.localeCompare(b.name));
  const national = outlets.filter((o) => o.outlet_group === "nacional");
  const international = outlets.filter((o) => o.outlet_group === "internacional");

  return (
    <>
      <h1>Veículos monitorados</h1>
      <p className="note">
        {outlets.filter((o) => o.active).length} de {outlets.length} com coleta ativa. Para mudar feeds ou
        ativar um veículo, edite <code>backend/app/seed.py</code> e rode <code>docker compose up -d</code>.
      </p>
      <section className="card">
        <h2>Nacionais</h2>
        <OutletTable outlets={national} />
      </section>
      <section className="card">
        <h2>Internacionais</h2>
        <p className="sub">Comparados entre si no painel de cobertura (filtro &ldquo;Internacionais&rdquo;).</p>
        <OutletTable outlets={international} />
      </section>
    </>
  );
}
