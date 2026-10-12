import { getOutlets } from "@/lib/api";

export default async function OutletsPage() {
  const outlets = await getOutlets();

  return (
    <>
      <h1>Veículos monitorados</h1>
      <table>
        <thead>
          <tr>
            <th>Veículo</th>
            <th>Domínio</th>
            <th>Feeds</th>
            <th>Observações de coleta</th>
          </tr>
        </thead>
        <tbody>
          {outlets.map((o) => (
            <tr key={o.id}>
              <td><strong>{o.name}</strong></td>
              <td>{o.canonical_domain}</td>
              <td>{o.feed_urls.length ? o.feed_urls.join(", ") : "—"}</td>
              <td className="muted">{o.collection_notes ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
