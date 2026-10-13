// Utilitários dos gráficos: escalas, datas no fuso de SP e cores por veículo.

/** Ticks "redondos" (1, 2, 5 × 10^k) de 0 até cobrir `max`, com ~4 intervalos. */
export function niceTicks(max: number, target = 4): number[] {
  if (max <= 0) return [0, 1];
  const raw = max / target;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? 10 * mag;
  const top = Math.ceil(max / step) * step;
  const ticks: number[] = [];
  for (let v = 0; v <= top + step / 2; v += step) ticks.push(Math.round(v * 1e6) / 1e6);
  return ticks;
}

export function compact(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace(".0", "")}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1).replace(".0", "")}K`;
  return String(n);
}

const TZ = "America/Sao_Paulo";
const fmtDay = new Intl.DateTimeFormat("pt-BR", { timeZone: TZ, day: "2-digit", month: "2-digit" });
const fmtHour = new Intl.DateTimeFormat("pt-BR", { timeZone: TZ, hour: "2-digit", hour12: false });

function hourLabel(d: Date): string {
  return `${fmtHour.format(d).replace(/\D/g, "").padStart(2, "0")}h`;
}

/** Rótulo curto de eixo para o início de um bucket. */
export function tickLabel(iso: string, bucketSeconds: number, spansDays: boolean): string {
  const d = new Date(iso);
  if (bucketSeconds >= 86400) return fmtDay.format(d);
  if (!spansDays) return hourLabel(d);
  return `${fmtDay.format(d)} ${hourLabel(d)}`;
}

/** Rótulo do intervalo de um bucket, para o tooltip: "12/10, 14h–15h". */
export function bucketRangeLabel(iso: string, bucketSeconds: number): string {
  const a = new Date(iso);
  const b = new Date(a.getTime() + bucketSeconds * 1000);
  if (bucketSeconds >= 86400) return fmtDay.format(a);
  return `${fmtDay.format(a)}, ${hourLabel(a)}–${hourLabel(b)}`;
}

// Cores categóricas só para até 3 séries (ex.: comparar histórias). Com muitos
// veículos, os gráficos usam uma cor só e a identidade vem do rótulo.
const MAX_SLOTS = 8;

export function seriesColor(position: number): string {
  return `var(--series-${Math.min(MAX_SLOTS, position + 1)})`;
}
