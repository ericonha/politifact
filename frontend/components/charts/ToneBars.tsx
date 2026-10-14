/** Leitura de tom da IA por ator: barra 100% (negativo | neutro | positivo), divergente,
 * com "incerto" fora da barra. Sempre com o tamanho da amostra (n). */

import type { OutletProfile } from "@/lib/api";

type Row = OutletProfile["tone"][number];

const SEGMENTS = [
  { key: "negativo", label: "negativo", cls: "tone-neg" },
  { key: "neutro", label: "neutro", cls: "tone-neu" },
  { key: "positivo", label: "positivo", cls: "tone-pos" },
] as const;

function pct(n: number, d: number) {
  return d ? Math.round((n / d) * 100) : 0;
}

export function ToneBars({ rows }: { rows: Row[] }) {
  return (
    <div className="tone" role="table" aria-label="Tom das manchetes em relação a cada ator, segundo a IA">
      <div className="cbars-legend" aria-hidden="true">
        {SEGMENTS.map((s) => <span key={s.key}><i className={`tone-key ${s.cls}`} /> {s.label}</span>)}
      </div>
      {rows.map((r) => {
        const decided = r.negativo + r.neutro + r.positivo;
        return (
          <div className="tone-row" role="row" key={r.key}>
            <div className="cbar-label" role="rowheader">
              {r.name} <span className="muted">n={r.n}</span>
            </div>
            <div className="tone-track" role="cell"
                 title={`${r.name}: ${r.negativo} negativo, ${r.neutro} neutro, ${r.positivo} positivo, ${r.incerto} incerto`}>
              {SEGMENTS.map((s) => {
                const v = r[s.key];
                return v ? <div key={s.key} className={`tone-seg ${s.cls}`} style={{ flexGrow: v }} /> : null;
              })}
              {decided === 0 && <div className="tone-seg tone-none" style={{ flexGrow: 1 }} />}
            </div>
            <div className="cbar-value" role="cell">
              <strong>{pct(r.negativo, decided)}%</strong> <span className="muted">negativo</span>
              {r.incerto > 0 && <span className="muted">, {r.incerto} incerto</span>}
              {r.peers_negative_share != null && (
                <div className="muted">outros: {Math.round(r.peers_negative_share * 100)}% negativo (n={r.peers_n})</div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
