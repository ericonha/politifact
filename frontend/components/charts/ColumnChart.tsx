"use client";

import { useState } from "react";
import { compact, niceTicks } from "@/lib/chart-utils";
import { useWidth } from "./useWidth";

export type Column = { key: string; label: string; value: number };

type Props = { columns: Column[]; ariaLabel: string; valueLabel: string; color?: string; height?: number };

const MAX_THICK = 24;
const R = 4;

/** Coluna: quadrada na base, topo arredondado (4px). */
function colPath(x: number, base: number, w: number, h: number): string {
  if (h <= 0) return "";
  const r = Math.min(R, h, w / 2);
  return `M${x},${base} v${-(h - r)} a${r},${r} 0 0 1 ${r},${-r} h${w - 2 * r} a${r},${r} 0 0 1 ${r},${r} v${h - r} z`;
}

export function ColumnChart({ columns, ariaLabel, valueLabel, color = "var(--series-1)", height = 220 }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<string | null>(null);

  const m = { top: 20, right: 8, bottom: 28, left: 36 };
  const innerW = Math.max(10, width - m.left - m.right);
  const innerH = height - m.top - m.bottom;
  const max = Math.max(1, ...columns.map((c) => c.value));
  const ticks = niceTicks(max);
  const yMax = ticks[ticks.length - 1];
  const band = innerW / Math.max(1, columns.length);
  const thick = Math.min(MAX_THICK, band * 0.6);
  const y = (v: number) => m.top + innerH - (v / yMax) * innerH;
  const base = m.top + innerH;

  return (
    <div className="chart" ref={ref}>
      <div className="chart-plot">
        <svg width={width} height={height} role="img" aria-label={ariaLabel}>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={m.left} x2={m.left + innerW} y1={y(t)} y2={y(t)} className={t === 0 ? "axis" : "grid"} />
              <text x={m.left - 8} y={y(t)} dy="0.32em" textAnchor="end" className="tick">{compact(t)}</text>
            </g>
          ))}
          {columns.map((c, i) => {
            const cx = m.left + band * i + band / 2;
            const h = base - y(c.value);
            const dim = active != null && active !== c.key;
            return (
              <g
                key={c.key}
                tabIndex={0}
                onPointerEnter={() => setActive(c.key)}
                onPointerLeave={() => setActive(null)}
                onFocus={() => setActive(c.key)}
                onBlur={() => setActive(null)}
                aria-label={`${c.label}: ${c.value} ${valueLabel}`}
              >
                <rect x={m.left + band * i} y={m.top} width={band} height={innerH} fill="transparent" />
                <path d={colPath(cx - thick / 2, base, thick, h)} fill={color} opacity={dim ? 0.45 : 1} />
                <text x={cx} y={y(c.value) - 6} textAnchor="middle" className="value-label">{compact(c.value)}</text>
                <text x={cx} y={height - 8} textAnchor="middle" className="tick">{c.label}</text>
              </g>
            );
          })}
        </svg>
        {active != null && (() => {
          const i = columns.findIndex((c) => c.key === active);
          const c = columns[i];
          const left = m.left + band * i + band / 2;
          return (
            <div className="tooltip" style={{ left, top: m.top, transform: "translateX(-50%)" }} role="status">
              <div className="tooltip-row"><strong>{c.value}</strong><span>{valueLabel} · {c.label}</span></div>
            </div>
          );
        })()}
      </div>
    </div>
  );
}
