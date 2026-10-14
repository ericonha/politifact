import Link from "next/link";
import { submitClaimAction } from "@/app/actions";
import { PageLayout, Sidebar } from "@/components/Sidebar";
import { ReviewChip, VerdictBadge } from "@/components/Verdict";
import { getArticle, getCollectionStatus, getInvestigations, getOutlets, timeAgo } from "@/lib/api";

type SP = { artigo?: string; erro?: string; texto?: string };

const EXAMPLES = [
  "A Selic está em 13,75% ao ano.",
  "A inflação de 2025 foi de 4,26%.",
  "O desemprego ficou em 5,3% em agosto de 2026.",
];

const STATUS_TEXT = { queued: "na fila", running: "checando…", done: "pronta", failed: "falhou" } as const;

export default async function ChecagemPage({ searchParams }: { searchParams: Promise<SP> }) {
  const sp = await searchParams;
  const articleId = sp.artigo ? Number(sp.artigo) : NaN;
  const [recent, status, article, outlets] = await Promise.all([
    getInvestigations(),
    getCollectionStatus(),
    Number.isInteger(articleId) ? getArticle(articleId) : Promise.resolve(null),
    getOutlets(),
  ]);
  const outletName = article ? outlets.find((o) => o.id === article.outlet_id)?.name : undefined;

  return (
    <PageLayout
      sidebar={
        <Sidebar
          title="Checagem"
          intro="Cole uma afirmação ou escolha uma notícia. O sistema separa as afirmações, procura evidências e mostra de onde veio cada conclusão."
          basePath="/checagem"
          params={{}}
          status={status}
        />
      }
    >
      <section className="card check-form">
        {article ? (
          <>
            <h2>Checar esta notícia</h2>
            <p className="sub">
              {outletName ?? "Veículo"} · <a href={article.original_url} target="_blank" rel="noopener noreferrer">abrir a notícia</a>
            </p>
            <blockquote className="input-quote">
              <strong>{article.headline}</strong>
              {article.summary && <> {article.summary}</>}
            </blockquote>
            <form action={submitClaimAction}>
              <input type="hidden" name="article_id" value={article.id} />
              <button type="submit" className="button">Checar as afirmações desta notícia</button>{" "}
              <Link href="/checagem" className="muted">ou colar outro texto</Link>
            </form>
            <p className="note">Só o título e o resumo da notícia são checados: o sistema não guarda a matéria inteira.</p>
          </>
        ) : (
          <>
            <h2>O que você quer checar?</h2>
            <form action={submitClaimAction}>
              <label htmlFor="claim-text" className="sr-only">Afirmação</label>
              <textarea
                id="claim-text"
                name="text"
                rows={4}
                maxLength={4000}
                required
                minLength={10}
                defaultValue={sp.texto ?? ""}
                placeholder="Ex.: A inflação de 2025 foi de 4,26%."
              />
              {sp.erro && <p className="form-error" role="alert">{sp.erro}</p>}
              <div className="form-row">
                <button type="submit" className="button">Checar</button>
                <span className="muted">Até 4.000 caracteres. Um texto com várias frases vira várias afirmações.</span>
              </div>
            </form>
            <div className="examples">
              <span className="muted">Exemplos:</span>
              {EXAMPLES.map((e) => (
                <Link key={e} href={`/checagem?texto=${encodeURIComponent(e)}`} className="chip">{e}</Link>
              ))}
            </div>
          </>
        )}
      </section>

      <details className="table-view" open={recent.length === 0}>
        <summary>O que a checagem automática consegue verificar</summary>
        <ul className="limits">
          <li><strong>Números de cinco indicadores</strong>, comparados com séries públicas do Banco Central: Selic, inflação (IPCA do mês ou em 12 meses), desemprego, dólar e PIB. Aqui o veredito sai por regra, sem IA.</li>
          <li><strong>Checagens já publicadas</strong> por agências (com a chave FACTCHECK_API_KEY configurada): a IA local verifica se alguma trata exatamente da mesma afirmação, e a resposta passa por validação.</li>
          <li><strong>Notícias coletadas</strong>: a IA local classifica cada uma (apoia, contradiz ou não se aplica) e, se pelo menos 2 veículos apontam para o mesmo lado e nenhum para o outro, o resultado é <em>provavelmente verdadeiro</em> ou <em>provavelmente falso</em>, marcado como “só imprensa”. É um indício, não uma prova: “verdadeiro” e “falso” ficam para dados oficiais e checagens publicadas.</li>
          <li>Opiniões, previsões e perguntas são marcadas como <em>não checáveis</em>. Sem fonte que decida, ou com notícias divergentes, o resultado é <em>sem evidência suficiente</em>.</li>
          <li>Toda checagem começa aguardando revisão humana. Rechecar cria uma versão nova e mantém a anterior.</li>
        </ul>
      </details>

      <h2 className="front-section-title">Checagens recentes</h2>
      {recent.length === 0 ? (
        <div className="empty">Nenhuma checagem ainda.</div>
      ) : (
        <ul className="check-list">
          {recent.map((inv) => (
            <li key={inv.id}>
              <div className="check-list-head">
                <Link href={`/checagem/${inv.id}`} className="check-list-text">
                  {inv.input_type === "article" && <span className="lang-badge">NOTÍCIA</span>}
                  {inv.input_text.length > 160 ? `${inv.input_text.slice(0, 159)}…` : inv.input_text}
                </Link>
                <span className="muted">{timeAgo(inv.created_at)}</span>
              </div>
              {inv.status !== "done" ? (
                <span className={`status ${inv.status === "failed" ? "failed" : "running"}`}>{STATUS_TEXT[inv.status]}</span>
              ) : inv.claims.length === 0 ? (
                <span className="muted">{inv.error ?? "Nenhuma afirmação encontrada."}</span>
              ) : (
                <ul className="check-list-claims">
                  {inv.claims.map((c) => (
                    <li key={c.claim_id}>
                      <VerdictBadge assessment={c.assessment} size="sm" />
                      <span className="check-claim-text">{c.text}</span>
                      {c.review_status !== "pending_review" && <ReviewChip status={c.review_status} />}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
    </PageLayout>
  );
}
