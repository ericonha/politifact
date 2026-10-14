"use client";

import { useState, type KeyboardEvent, type PointerEvent } from "react";
import { bucketRangeLabel, compact, niceTicks, tickLabel } from "@/lib/chart-utils";
import { useWidth } from "./useWidth";

export type LineSeries = { key: string; label: string; color: string; values: number[] };

type Props = {
  buckets: string[];
  bucketSeconds: number;
  series: LineSeries[];
  height?: number;
  ariaLabel: string;
  valueLabel?: string; // ex.: "notícias"
};

const LABEL_MIN_GAP = 14;

export function LineChart({ buckets, bucketSeconds, series, height = 260, ariaLabel, valueLabel = "" }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);

  const n = buckets.length;
  const narrow = width < 520;
  const m = { top: 12, right: narrow ? 12 : 120, bottom: 28, left: 36 };
  const innerW = Math.max(10, width - m.left - m.right);
  const innerH = height - m.top - m.bottom;

  const max = Math.max(1, ...series.flatMap((s) => s.values));
  const ticks = niceTicks(max);
  const yMax = ticks[ticks.length - 1];
  const x = (i: number) => m.left + (n <= 1 ? innerW / 2 : (i * innerW) / (n - 1));
  const y = (v: number) => m.top + innerH - (v / yMax) * innerH;

  const spansDays = n > 0 && new Date(buckets[n - 1]).getTime() - new Date(buckets[0]).getTime() >= 86400_000;
  const tickEvery = Math.max(1, Math.ceil(n / Math.max(2, Math.floor(innerW / 90))));
  const xTicks = buckets.map((_, i) => i).filter((i) => i % tickEvery === 0);

  // Rótulos no fim das linhas só se não colidirem; senão a legenda faz o trabalho.
  const ends = series
    .map((s) => ({ s, y: y(s.values[n - 1] ?? 0) }))
    .sort((a, b) => a.y - b.y);
  const endLabelsFit =
    !narrow && series.length > 1 && ends.every((e, i) => i === 0 || e.y - ends[i - 1].y >= LABEL_MIN_GAP);

  const indexAt = (clientX: number, rect: DOMRect) => {
    if (n <= 1) return 0;
    const px = clientX - rect.left - m.left;
    return Math.min(n - 1, Math.max(0, Math.round((px / innerW) * (n - 1))));
  };
  const onMove = (e: PointerEvent<SVGRectElement>) => {
    const svg = e.currentTarget.ownerSVGElement;
    if (svg) setActive(indexAt(e.clientX, svg.getBoundingClientRect()));
  };
  const onKey = (e: KeyboardEvent<SVGSVGElement>) => {
    if (e.key === "ArrowRight") setActive((a) => Math.min(n - 1, (a ?? -1) + 1));
    else if (e.key === "ArrowLeft") setActive((a) => Math.max(0, (a ?? n) - 1));
    else if (e.key === "Escape") setActive(null);
    else return;
    e.preventDefault();
  };

  const tooltipLeft = active == null ? 0 : x(active);
  const flip = active != null && tooltipLeft > width - 200;

  return (
    <div className="chart" ref={ref}>
      {series.length > 1 && (
      <ul className="legend" aria-hidden="true">
        {series.map((s) => (
          <li key={s.key}>
            <svg width="16" height="8"><line x1="0" y1="4" x2="16" y2="4" stroke={s.color} strokeWidth="2" strokeLinecap="round" /></svg>
            {s.label}
          </li>
        ))}
      </ul>
      )}
      <div className="chart-plot">
        <svg
          width={width}
          height={height}
          role="img"
          aria-label={ariaLabel}
          tabIndex={0}
          onKeyDown={onKey}
          onFocus={() => setActive((a) => a ?? n - 1)}
          onBlur={() => setActive(null)}
        >
          {ticks.map((t) => (
            <g key={t}>
              <line x1={m.left} x2={m.left + innerW} y1={y(t)} y2={y(t)} className={t === 0 ? "axis" : "grid"} />
              <text x={m.left - 8} y={y(t)} dy="0.32em" textAnchor="end" className="tick">{compact(t)}</text>
            </g>
          ))}
          {xTicks.map((i) => (
            <text key={i} x={x(i)} y={height - 8} textAnchor={i === 0 ? "start" : "middle"} className="tick">
              {tickLabel(buckets[i], bucketSeconds, spansDays)}
            </text>
          ))}

          {active != null && (
            <line x1={x(active)} x2={x(active)} y1={m.top} y2={m.top + innerH} className="crosshair" />
          )}

          {series.map((s) => (
            <polyline
              key={s.key}
              points={s.values.map((v, i) => `${x(i)},${y(v)}`).join(" ")}
              fill="none"
              stroke={s.color}
              strokeWidth="2"
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          ))}

          {series.map((s) => {
            const i = active ?? n - 1;
            if (n === 0) return null;
            return (
              <circle key={s.key} cx={x(i)} cy={y(s.values[i] ?? 0)} r="4" fill={s.color} className="dot" />
            );
          })}

          {endLabelsFit && active == null &&
            ends.map(({ s, y: ly }) => (
              <text key={s.key} x={m.left + innerW + 10} y={ly} dy="0.32em" className="end-label">
                {s.label} <tspan className="end-value">{s.values[n - 1] ?? 0}</tspan>
              </text>
            ))}

          <rect
            x={m.left}
            y={m.top}
            width={innerW}
            height={innerH}
            fill="transparent"
            onPointerMove={onMove}
            onPointerLeave={() => setActive(null)}
          />
        </svg>

        {active != null && (
          <div
            className="tooltip"
            style={{ left: tooltipLeft, top: m.top, transform: flip ? "translateX(calc(-100% - 12px))" : "translateX(12px)" }}
            role="status"
          >
            <div className="tooltip-title">{bucketRangeLabel(buckets[active], bucketSeconds)}</div>
            {[...series]
              .sort((a, b) => (b.values[active] ?? 0) - (a.values[active] ?? 0))
              .map((s) => (
                <div key={s.key} className="tooltip-row">
                  <svg width="12" height="8" aria-hidden="true"><line x1="0" y1="4" x2="12" y2="4" stroke={s.color} strokeWidth="2" strokeLinecap="round" /></svg>
                  <strong>{s.values[active] ?? 0}</strong>
                  <span>{s.label}{valueLabel ? ` · ${valueLabel}` : ""}</span>
                </div>
              ))}
          </div>
        )}
      </div>
    </div>
  );
}
