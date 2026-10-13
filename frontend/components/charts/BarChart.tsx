"use client";

import { useState } from "react";
import { compact } from "@/lib/chart-utils";
import { useWidth } from "./useWidth";

export type Bar = { key: string; label: string; value: number; color: string; note?: string };

// O valor já está escrito na ponta de cada barra; no hover a barra se destaca
// e o tooltip nativo mostra a observação, sem cobrir as outras barras.

type Props = { bars: Bar[]; ariaLabel: string; valueLabel: string };

const ROW = 36;
const THICK = 20;
const R = 4;

/** Caminho de barra horizontal: quadrada na base, ponta arredondada (4px). */
function barPath(x0: number, y: number, w: number): string {
  if (w <= 0) return "";
  const r = Math.min(R, w, THICK / 2);
  return `M${x0},${y} h${w - r} a${r},${r} 0 0 1 ${r},${r} v${THICK - 2 * r} a${r},${r} 0 0 1 ${-r},${r} h${-(w - r)} z`;
}

export function BarChart({ bars, ariaLabel, valueLabel }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<string | null>(null);

  const labelW = Math.min(160, Math.max(124, width * 0.32));
  const valueW = 48;
  const innerW = Math.max(10, width - labelW - valueW);
  const max = Math.max(1, ...bars.map((b) => b.value));
  const height = bars.length * ROW + 8;

  return (
    <div className="chart" ref={ref}>
      <div className="chart-plot">
        <svg width={width} height={height} role="img" aria-label={ariaLabel}>
          <line x1={labelW} x2={labelW} y1={0} y2={height} className="axis" />
          {bars.map((b, i) => {
            const y = i * ROW + (ROW - THICK) / 2 + 4;
            const w = (b.value / max) * innerW;
            const dim = active != null && active !== b.key;
            return (
              <g
                key={b.key}
                tabIndex={0}
                onPointerEnter={() => setActive(b.key)}
                onPointerLeave={() => setActive(null)}
                onFocus={() => setActive(b.key)}
                onBlur={() => setActive(null)}
                className="bar-row"
                aria-label={`${b.label}: ${b.value} ${valueLabel}`}
              >
                {/* alvo de hover maior que a barra: a linha inteira */}
                <title>{`${b.value} ${valueLabel} · ${b.label}${b.note ? ` — ${b.note}` : ""}`}</title>
                <rect x={0} y={i * ROW + 4} width={width} height={ROW} fill="transparent" />
                <text x={labelW - 10} y={y + THICK / 2} dy="0.32em" textAnchor="end" className="cat-label">
                  {b.label}
                </text>
                <path d={barPath(labelW, y, w)} fill={b.color} opacity={dim ? 0.45 : 1} />
                <text x={labelW + w + 6} y={y + THICK / 2} dy="0.32em" className="value-label">
                  {compact(b.value)}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
