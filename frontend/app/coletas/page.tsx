import { revalidatePath } from "next/cache";
import { formatDate, getCollectionRuns, getOutlets, triggerCollection } from "@/lib/api";

const STATUS_LABEL: Record<string, string> = {
  running: "Rodando",
  success: "Sucesso",
  partial: "Parcial",
  failed: "Falhou",
};

async function collectNow() {
  "use server";
  await triggerCollection();
  revalidatePath("/coletas");
}

export default async function CollectionRunsPage() {
  const [runs, outlets] = await Promise.all([getCollectionRuns(), getOutlets()]);
  const names = new Map(outlets.map((o) => [o.id, o.name]));
  const inactive = outlets.filter((o) => !o.active);

  return (
    <>
      <div className="toolbar">
        <h1>Coletas</h1>
        <form action={collectNow}>
          <button type="submit" className="button">Coletar agora</button>
        </form>
      </div>

      <p className="note">
        A coleta roda sozinha a cada 30 minutos. Recarregue a página para ver o resultado de uma coleta manual.
      </p>

      {inactive.length > 0 && (
        <div className="warning">
          <strong>Veículos sem coleta:</strong>{" "}
          {inactive.map((o) => `${o.name} (${o.collection_notes ?? "desativado"})`).join("; ")}
        </div>
      )}

      {runs.length === 0 ? (
        <div className="empty">Nenhuma coleta registrada ainda.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Início</th>
              <th>Veículo</th>
              <th>Status</th>
              <th className="num">Encontradas</th>
              <th className="num">Novas</th>
              <th className="num">Falhas</th>
              <th>Erros</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.id}>
                <td>{formatDate(r.started_at)}</td>
                <td>{r.outlet_id ? names.get(r.outlet_id) ?? r.outlet_id : "—"}</td>
                <td><span className={`status ${r.status}`}>{STATUS_LABEL[r.status] ?? r.status}</span></td>
                <td className="num">{r.records_discovered}</td>
                <td className="num">{r.records_inserted}</td>
                <td className="num">{r.records_failed}</td>
                <td className="muted errors">{r.error_summary ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
