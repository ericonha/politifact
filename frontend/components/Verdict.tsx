import { ASSESSMENT_LABELS, type Assessment } from "@/lib/api";

/** Ícone + texto (o significado nunca depende só da cor). */
function Icon({ a }: { a: Assessment }) {
  const common = { width: 14, height: 14, viewBox: "0 0 16 16", "aria-hidden": true as const };
  switch (a) {
    case "verdadeiro":
    case "provavelmente_verdadeiro":
      return <svg {...common}><path d="M3 8.5l3 3 7-7" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" /></svg>;
    case "falso":
    case "provavelmente_falso":
      return <svg {...common}><path d="M4 4l8 8M12 4l-8 8" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" /></svg>;
    case "impreciso":
      return <svg {...common}><path d="M2.5 9c2-3 3.5-3 5.5 0s3.5 3 5.5 0" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>;
    case "sem_evidencia":
      return <svg {...common}><path d="M5.5 6a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .8-1 1.5M8 12.5v.01" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>;
    default:
      return <svg {...common}><path d="M4 8h8" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" /></svg>;
  }
}

export function VerdictBadge({ assessment, size = "md" }: { assessment: Assessment; size?: "sm" | "md" | "lg" }) {
  return (
    <span className={`verdict v-${assessment} verdict-${size}`}>
      <span className="verdict-icon"><Icon a={assessment} /></span>
      {ASSESSMENT_LABELS[assessment] ?? assessment}
      {assessment.startsWith("provavelmente") && <span className="verdict-basis">só imprensa</span>}
    </span>
  );
}

const REVIEW: Record<string, string> = {
  pending_review: "Aguardando revisão",
  approved: "Revisada e aprovada",
  rejected: "Revisada e rejeitada",
};

export function ReviewChip({ status }: { status: string }) {
  return <span className={`review-chip r-${status}`}>{REVIEW[status] ?? status}</span>;
}
