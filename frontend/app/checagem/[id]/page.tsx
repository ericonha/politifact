import Link from "next/link";
import { notFound } from "next/navigation";
import { recheckAction, reviewAction } from "@/app/actions";
import { AutoRefresh } from "@/components/AutoRefresh";
import { PageLayout, Sidebar } from "@/components/Sidebar";
import { ReviewChip, VerdictBadge } from "@/components/Verdict";
import {
  ASSESSMENT_LABELS,
  formatDate,
  getCollectionStatus,
  getInvestigation,
  timeAgo,
  type ClaimDetail,
  type EvidenceRow,
  type FactCheckVersion,
} from "@/lib/api";

const METHOD_TEXT: Record<string, string> = {
  rules: "Veredito por regra fixa, comparando o número afirmado com a série oficial. Sem IA.",
  llm: "Veredito a partir de checagens já publicadas, lidas por IA local e conferidas pela validação.",
  press: "Indício, não prova: a IA local classificou cada notícia (apoia, contradiz ou não se aplica), com trecho copiado da notícia, e uma regra exige pelo menos 2 veículos de um lado e nenhum do outro.",
  none: "Nenhuma fonte capaz de decidir foi encontrada.",
};

const REL: Record<string, { label: string; cls: string }> = {
  supports: { label: "confirma", cls: "rel-sup" },
  contradicts: { label: "contradiz", cls: "rel-con" },
  related: { label: "relacionada", cls: "rel-ctx" },
  context: { label: "contexto", cls: "rel-ctx" },
};

function claimedValue(p: ClaimDetail["parsed"]): string {
  if (!p || p.value == null) return "—";
  const n = p.value.toLocaleString("pt-BR", { minimumFractionDigits: p.decimals ?? 0, maximumFractionDigits: p.decimals ?? 4 });
  return p.unit === "R$" ? `R$ ${n}` : `${n}%`;
}

/** Compara sem pontuação e caixa: "x." e "x" são o mesmo trecho. */
function same(a: string, b: string): boolean {
  const n = (t: string) => t.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim();
  return n(a) === n(b);
}

function Rel({ r }: { r: string }) {
  const x = REL[r] ?? { label: r, cls: "rel-ctx" };
  return <span className={`rel ${x.cls}`}>{x.label}</span>;
}

function EvidenceGroup({ title, note, rows }: { title: string; note?: string; rows: EvidenceRow[] }) {
  if (!rows.length) return null;
  return (
    <div className="ev-group">
      <h4>{title}</h4>
      {note && <p className="sub">{note}</p>}
      <ul className="ev-list">
        {rows.map((e) => (
          <li key={e.id}>
            <div className="ev-head">
              <Rel r={e.relationship} />
              <a href={e.source_url} target="_blank" rel="noopener noreferrer" className="ev-title">
                {e.source_title ?? e.source_url}
              </a>
            </div>
            {e.data?.stance_quote ? (
              <p className="ev-passage">Trecho que justifica: “{String(e.data.stance_quote)}”</p>
            ) : e.relevant_passage && <p className="ev-passage">{e.relevant_passage}</p>}
            <div className="muted ev-meta">
              {e.published_at && <>de {formatDate(e.published_at).split(",")[0]} · </>}
              buscada {formatDate(e.retrieved_at)}
              {e.source_type === "fact_check" && e.data?.rating ? <> · classificação da agência: <strong>{String(e.data.rating)}</strong></> : null}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Version({ fc, claim, investigationId }: { fc: FactCheckVersion; claim: ClaimDetail; investigationId: number }) {
  const official = fc.evidence.filter((e) => e.source_type === "official_data");
  const published = fc.evidence.filter((e) => e.source_type === "fact_check");
  const press = fc.evidence.filter((e) => e.source_type === "press");
  const p = claim.parsed;
  return (
    <>
      <div className="verdict-row">
        <VerdictBadge assessment={fc.assessment} size="lg" />
        <ReviewChip status={fc.review_status} />
      </div>
      <p className="verdict-expl">{fc.explanation}</p>
      <p className="muted method-line">
        {fc.assessment !== "nao_checavel" && METHOD_TEXT[fc.method ?? "none"]}
        {fc.model ? ` Modelo: ${fc.model}.` : ""} Checada {timeAgo(fc.created_at)}.
      </p>

      {p?.indicator && (
        <dl className="parsed">
          <div><dt>Indicador</dt><dd>{p.indicator_label}</dd></div>
          <div><dt>Valor afirmado</dt><dd>{claimedValue(p)}</dd></div>
          <div><dt>Período</dt><dd>{p.period_label}</dd></div>
        </dl>
      )}

      <EvidenceGroup title="Dados oficiais" rows={official} />
      <EvidenceGroup title="Checagens já publicadas" note="Veredito das agências como elas publicaram." rows={published} />
      <EvidenceGroup title="Na imprensa" note="Notícias coletadas pelo sistema. Imprensa não é prova: quando vários veículos apontam para o mesmo lado, o resultado é só “provavelmente”." rows={press} />
      {official.length + published.length + press.length === 0 && fc.assessment !== "nao_checavel" && (
        <p className="muted">Nenhuma evidência encontrada.</p>
      )}

      {fc.limitations.length > 0 && (
        <div className="ev-group">
          <h4>Limitações</h4>
          <ul className="limits">{fc.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul>
        </div>
      )}

      <div className="review-box">
        <form action={reviewAction} className="review-form">
          <input type="hidden" name="fact_check_id" value={fc.id} />
          <input type="hidden" name="investigation_id" value={investigationId} />
          <label htmlFor={`note-${fc.id}`} className="sub">Revisão humana {fc.review_note ? `(nota atual: “${fc.review_note}”)` : ""}</label>
          <input id={`note-${fc.id}`} name="note" type="text" maxLength={1000} placeholder="Nota da revisão (opcional)" />
          <div className="form-row">
            <button type="submit" name="decision" value="approved" className="button small">Aprovar</button>
            <button type="submit" name="decision" value="rejected" className="button small secondary">Rejeitar</button>
          </div>
        </form>
        <form action={recheckAction}>
          <input type="hidden" name="claim_id" value={claim.id} />
          <input type="hidden" name="investigation_id" value={investigationId} />
          <button type="submit" className="button small secondary" title="Busca as evidências de novo e cria uma nova versão">
            Rechecar
          </button>
        </form>
      </div>
    </>
  );
}

export default async function InvestigationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const invId = Number(id);
  if (!Number.isInteger(invId)) notFound();
  const [{ data: inv, error }, status] = await Promise.all([getInvestigation(invId), getCollectionStatus()]);
  if (!inv) {
    if (error?.includes("não encontrada")) notFound();
    return <div className="empty">Não foi possível abrir a checagem: {error}</div>;
  }
  const running = inv.status === "queued" || inv.status === "running";

  return (
    <PageLayout
      sidebar={
        <Sidebar
          title="Checagem"
          intro={<Link href="/checagem">Todas as checagens · nova checagem</Link>}
          basePath={`/checagem/${inv.id}`}
          params={{}}
          status={status}
        />
      }
    >
      {running && <AutoRefresh seconds={4} />}
      <p className="kicker">Checagem nº {inv.id} · {formatDate(inv.created_at)}</p>
      <blockquote className="input-quote">
        {inv.article ? (
          <>
            <strong>{inv.article.headline}</strong>
            <div className="muted">
              {inv.article.outlet} · <a href={inv.article.original_url} target="_blank" rel="noopener noreferrer">abrir a notícia</a>
            </div>
          </>
        ) : (
          inv.input_text
        )}
      </blockquote>

      {running && (
        <div className="empty" role="status">
          {inv.status === "queued" ? "Na fila…" : "Checando…"} A página atualiza sozinha. Consultar o Banco Central e,
          se configurado, as checagens publicadas leva alguns segundos; com a IA local, um pouco mais.
        </div>
      )}
      {inv.status === "failed" && <div className="empty" role="alert">A checagem falhou: {inv.error}</div>}
      {inv.status === "done" && inv.claims.length === 0 && (
        <div className="empty">{inv.error ?? "Nenhuma afirmação encontrada no texto."}</div>
      )}

      {inv.extraction && inv.claims.length > 0 && (
        <p className="muted">
          {inv.claims.length} {inv.claims.length === 1 ? "afirmação" : "afirmações"}{" "}
          {inv.extraction.method === "llm" ? `separadas por IA local (${inv.extraction.model})` : "separadas por regras (frase a frase)"}.
          {inv.extraction.problems?.length ? ` ${inv.extraction.problems.length} descartada(s) pela validação.` : ""}
        </p>
      )}

      {inv.claims.map((c, i) => (
        <section key={c.id} className="card claim-card" aria-labelledby={`claim-${c.id}`}>
          <div className="claim-num">Afirmação {i + 1}</div>
          <h2 id={`claim-${c.id}`} className="claim-text">{c.text}</h2>
          {c.quote && !same(c.quote, c.text) && <p className="muted">Trecho original: “{c.quote}”</p>}
          {c.current ? <Version fc={c.current} claim={c} investigationId={inv.id} /> : <p className="muted">Sem checagem ainda.</p>}
          {c.history.length > 0 && (
            <details className="table-view">
              <summary>Versões anteriores ({c.history.length})</summary>
              <ul className="limits">
                {c.history.map((h) => (
                  <li key={h.id}>
                    {formatDate(h.created_at)}: <strong>{ASSESSMENT_LABELS[h.assessment]}</strong>
                    {h.review_status !== "pending_review" && <> · {h.review_status === "approved" ? "aprovada" : "rejeitada"}</>}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </section>
      ))}
    </PageLayout>
  );
}
