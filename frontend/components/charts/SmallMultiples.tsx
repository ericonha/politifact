"use client";

import { useState, type KeyboardEvent, type PointerEvent } from "react";
import { bucketRangeLabel, compact, niceTicks, tickLabel } from "@/lib/chart-utils";
import { useWidth } from "./useWidth";

export type Multiple = { key: string; label: string; sublabel?: string; values: number[] };

type Props = {
  buckets: string[];
  bucketSeconds: number;
  items: Multiple[];
  ariaLabel: string;
  valueLabel: string;
  color?: string;
};

const CELL_H = 64;
const MIN_CELL_W = 220;

/**
 * Um gráfico pequeno por série, todos na MESMA escala (comparáveis entre si),
 * com uma cor só: com muitos veículos, a identidade vem do rótulo, não da cor.
 * O hover é compartilhado: apontar um momento mostra o valor de todos.
 */
export function SmallMultiples({ buckets, bucketSeconds, items, ariaLabel, valueLabel, color = "var(--series-1)" }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>(900);
  const [active, setActive] = useState<number | null>(null);

  const n = buckets.length;
  const cols = Math.max(1, Math.min(4, Math.floor(width / MIN_CELL_W)));
  const gap = 16;
  const cellW = (width - gap * (cols - 1)) / cols;
  const pad = { left: 2, right: 2, top: 6, bottom: 2 };
  const innerW = Math.max(10, cellW - pad.left - pad.right);
  const innerH = CELL_H - pad.top - pad.bottom;

  const max = Math.max(1, ...items.flatMap((s) => s.values));
  const yMax = niceTicks(max)[niceTicks(max).length - 1];
  const x = (i: number) => pad.left + (n <= 1 ? innerW / 2 : (i * innerW) / (n - 1));
  const y = (v: number) => pad.top + innerH - (v / yMax) * innerH;

  const spansDays = n > 0 && new Date(buckets[n - 1]).getTime() - new Date(buckets[0]).getTime() >= 86400_000;

  const onMove = (e: PointerEvent<SVGRectElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - rect.left - pad.left;
    setActive(n <= 1 ? 0 : Math.min(n - 1, Math.max(0, Math.round((px / innerW) * (n - 1)))));
  };
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "ArrowRight") setActive((a) => Math.min(n - 1, (a ?? -1) + 1));
    else if (e.key === "ArrowLeft") setActive((a) => Math.max(0, (a ?? n) - 1));
    else if (e.key === "Escape") setActive(null);
    else return;
    e.preventDefault();
  };

  const area = (vals: number[]) =>
    n === 0 ? "" : `M${x(0)},${y(0)} ` + vals.map((v, i) => `L${x(i)},${y(v)}`).join(" ") + ` L${x(n - 1)},${y(0)} Z`;

  return (
    <div className="chart" ref={ref}>
      <div className="sm-header" aria-live="polite">
        {active == null ? (
          <span className="muted">
            Escala igual em todos (máx. {compact(yMax)} {valueLabel} por período).{" "}
            {n > 0 && `${tickLabel(buckets[0], bucketSeconds, spansDays)} → ${tickLabel(buckets[n - 1], bucketSeconds, spansDays)}`}
          </span>
        ) : (
          <strong>{bucketRangeLabel(buckets[active], bucketSeconds)}</strong>
        )}
      </div>
      <div
        className="sm-grid"
        role="img"
        aria-label={ariaLabel}
        tabIndex={0}
        onKeyDown={onKey}
        onFocus={() => setActive((a) => a ?? n - 1)}
        onBlur={() => setActive(null)}
        style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`, columnGap: gap }}
      >
        {items.map((s) => {
          const total = s.values.reduce((a, b) => a + b, 0);
          const shown = active == null ? total : s.values[active] ?? 0;
          return (
            <div key={s.key} className="sm-cell">
              <div className="sm-title">
                <span className="sm-name">{s.label}</span>
                <span className="sm-value">
                  <strong>{shown}</strong>
                  <span className="muted">{active == null ? " no período" : ""}</span>
                </span>
              </div>
              {s.sublabel && <div className="sm-sub muted">{s.sublabel}</div>}
              <svg width={cellW} height={CELL_H}>
                <line x1={pad.left} x2={pad.left + innerW} y1={y(0)} y2={y(0)} className="axis" />
                <path d={area(s.values)} fill={color} opacity="0.1" />
                <polyline
                  points={s.values.map((v, i) => `${x(i)},${y(v)}`).join(" ")}
                  fill="none"
                  stroke={color}
                  strokeWidth="2"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
                {active != null && (
                  <>
                    <line x1={x(active)} x2={x(active)} y1={pad.top} y2={y(0)} className="crosshair" />
                    <circle cx={x(active)} cy={y(s.values[active] ?? 0)} r="4" fill={color} className="dot" />
                  </>
                )}
                <rect
                  x={0}
                  y={0}
                  width={cellW}
                  height={CELL_H}
                  fill="transparent"
                  onPointerMove={onMove}
                  onPointerLeave={() => setActive(null)}
                />
              </svg>
            </div>
          );
        })}
      </div>
    </div>
  );
}
