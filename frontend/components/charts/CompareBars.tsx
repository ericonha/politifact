/** Barras horizontais "este veículo" com um traço marcando a média dos outros veículos.
 * Valores em texto ao lado (não dependem de cor nem de hover); tooltip nativo com detalhes. */

export type CompareRow = {
  key: string;
  label: string;
  share: number | null;
  average: number | null;
  detail?: string;
};

function pct(x: number | null) {
  return x == null ? "—" : `${Math.round(x * 100)}%`;
}

export function CompareBars({ rows, max, ariaLabel }: { rows: CompareRow[]; max?: number; ariaLabel: string }) {
  const top = max ?? Math.max(0.05, ...rows.flatMap((r) => [r.share ?? 0, r.average ?? 0]));
  return (
    <div className="cbars" role="table" aria-label={ariaLabel}>
      <div className="cbars-legend" aria-hidden="true">
        <span><i className="cb-swatch" /> este veículo</span>
        <span><i className="cb-tick-key" /> média dos outros veículos</span>
      </div>
      {rows.map((r) => {
        const diff = r.share != null && r.average != null ? r.share - r.average : null;
        return (
          <div className="cbar-row" role="row" key={r.key}
               title={`${r.label}: ${pct(r.share)} neste veículo; média dos outros ${pct(r.average)}${r.detail ? `. ${r.detail}` : ""}`}>
            <div className="cbar-label" role="rowheader">{r.label}</div>
            <div className="cbar-track" role="cell">
              {r.share != null && <div className="cbar-fill" style={{ width: `${(r.share / top) * 100}%` }} />}
              {r.average != null && <div className="cbar-avg" style={{ left: `${(r.average / top) * 100}%` }} />}
            </div>
            <div className="cbar-value" role="cell">
              <strong>{pct(r.share)}</strong>
              <span className="muted">
                {r.average == null ? " sem média" : ` média ${pct(r.average)}`}
                {diff != null && Math.abs(diff) >= 0.05 ? (diff > 0 ? " · acima" : " · abaixo") : ""}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
