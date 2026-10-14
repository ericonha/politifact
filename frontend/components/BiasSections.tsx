import Link from "next/link";
import { CompareBars } from "@/components/charts/CompareBars";
import { formatDate, type OutletBias } from "@/lib/api";

function pct(x: number | null | undefined) {
  return x == null ? "—" : `${Math.round(x * 100)}%`;
}

function duration(min: number | null) {
  if (min == null) return "—";
  if (min < 1) return "menos de 1 min";
  if (min < 90) return `${Math.round(min)} min`;
  if (min < 48 * 60) return `${Math.floor(min / 60)} h ${Math.round(min % 60)} min`;
  return `${Math.round(min / 1440)} dias`;
}

const KIND: Record<string, string> = {
  possivel_sentido: "número ou negação mudou",
  reescrita: "manchete reescrita",
  ajuste: "ajuste de palavras",
  resumo: "só o resumo",
};

/** As quatro medidas de diferença de pauta e de texto. Nenhuma é rótulo político. */
export function BiasSections({ b, groupName }: { b: OutletBias; groupName: string }) {
  const om = b.omissions;
  const dl = b.delay;
  const vo = b.vocabulary;
  const ed = b.edits;
  return (
    <>
      <h2 className="front-section-title">Diferenças de pauta e de texto</h2>
      <p className="callout" style={{ marginTop: 0 }}>
        Quatro medidas objetivas, sem IA decidindo o que é viés: o que o veículo deixou de cobrir, quando publicou,
        que palavras escolhe e se altera manchetes depois de publicar. Valem só para o que aparece nos feeds RSS dos
        veículos monitorados, e diferença não indica intenção.
      </p>

      <section className="card">
        <h2>O que deixou de cobrir</h2>
        <p className="sub">
          Entre as histórias cobertas por {om.min_outlets} ou mais veículos {groupName}, parte que este veículo não
          cobriu. {om.eligible_stories} histórias comparáveis no período.
        </p>
        {om.eligible_stories < 10 ? (
          <div className="empty">Poucas histórias comparáveis no período ({om.eligible_stories}). Veja 30 dias.</div>
        ) : (
          <>
            <CompareBars
              ariaLabel="Histórias que o veículo não cobriu e média dos outros"
              rows={[{ key: "omit", label: "Não cobriu", share: om.omission_rate, average: om.average_rate,
                       detail: `${om.missed} de ${om.eligible_stories} histórias` }]}
              max={1}
            />
            {om.by_topic.filter((t) => t.eligible >= 3).length > 0 && (
              <>
                <h3 className="sub-title">Por seção</h3>
                <CompareBars
                  ariaLabel="Histórias não cobertas por seção"
                  rows={om.by_topic.filter((t) => t.eligible >= 3).map((t) => ({
                    key: t.topic, label: t.label, share: t.omission_rate, average: null,
                    detail: `${t.missed} de ${t.eligible} histórias`,
                  }))}
                  max={1}
                />
              </>
            )}
            {om.blind_spots.length > 0 && (
              <>
                <h3 className="sub-title">Histórias mais cobertas que ele não cobriu</h3>
                <ul className="limits">
                  {om.blind_spots.map((s) => (
                    <li key={s.story_id}>
                      <Link href={`/historias/${s.story_id}`}>{s.title}</Link>{" "}
                      <span className="muted">— {s.outlets_count} veículos ({s.outlets.join(", ")}{s.outlets_count > s.outlets.length ? "…" : ""})</span>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </>
        )}
        <p className="callout">
          Não cobrir pode ser decisão editorial, mas também o feed RSS não mostrar a matéria, ou o agrupamento não
          ter juntado notícias parecidas. Histórias anteriores à matéria mais antiga que temos do veículo não contam.
        </p>
      </section>

      <section className="card">
        <h2>Quando publica</h2>
        <p className="sub">
          Atraso em relação ao primeiro, entre os veículos {groupName}, a publicar a mesma história (só histórias com 2 ou mais veículos).
        </p>
        {!dl.enough ? (
          <div className="empty">Poucas histórias em comum no período ({dl.stories}); são necessárias pelo menos 8.</div>
        ) : (
          <dl className="parsed">
            <div><dt>Atraso típico (mediana)</dt><dd>{duration(dl.median_minutes)}</dd></div>
            <div><dt>Média dos outros veículos</dt><dd>{duration(dl.average_median_minutes)}</dd></div>
            <div><dt>Publicou junto do primeiro (até {dl.tolerance_minutes} min)</dt><dd>{pct(dl.first_share)} de {dl.stories} histórias</dd></div>
          </dl>
        )}
        <p className="callout">
          Usa a hora de publicação informada no feed. Ser rápido não é melhor nem pior: veículos de agência
          publicam primeiro, e veículos de análise, depois.
        </p>
      </section>

      <section className="card">
        <h2>Palavras que escolhe</h2>
        <p className="sub">
          Palavras de título e resumo que este veículo usa em proporção bem diferente dos outros {vo.comparison_outlets}{" "}
          veículos do mesmo idioma, nas <strong>mesmas histórias</strong> (assim o assunto não pesa).
        </p>
        {!vo.enough ? (
          <div className="empty">
            Amostra insuficiente: {vo.docs_outlet} matérias dele e {vo.docs_others} dos outros em histórias com 3 ou mais
            veículos; são necessárias pelo menos {vo.min_docs} de cada lado.
          </div>
        ) : (
          <div className="vocab-cols">
            <div>
              <h3 className="sub-title">Usa mais que os outros</h3>
              {vo.uses_more.length === 0 ? <p className="muted">Nenhuma palavra se destaca.</p> : (
                <ul className="vocab-list">
                  {vo.uses_more.map((t) => (
                    <li key={t.term}><strong>{t.term}</strong>{" "}
                      <span className="muted">{pct(t.outlet_share)} das matérias dele, {pct(t.others_share)} das dos outros</span></li>
                  ))}
                </ul>
              )}
            </div>
            <div>
              <h3 className="sub-title">Usa menos que os outros</h3>
              {vo.uses_less.length === 0 ? <p className="muted">Nenhuma palavra se destaca.</p> : (
                <ul className="vocab-list">
                  {vo.uses_less.map((t) => (
                    <li key={t.term}><strong>{t.term}</strong>{" "}
                      <span className="muted">{pct(t.outlet_share)} das matérias dele, {pct(t.others_share)} das dos outros</span></li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
        <p className="callout">
          Uma palavra se destaca por escolha editorial, mas também por estilo da casa, formato (boletim, coluna) ou
          tema regional. Leia as palavras, não tire conclusão só da lista. Compara {vo.docs_outlet} matérias dele em {vo.stories ?? 0} histórias.
        </p>
      </section>

      <section className="card">
        <h2>Edições de manchete</h2>
        <p className="sub">
          Manchetes que o veículo alterou depois de publicar, detectadas quando a matéria reaparece no feed com
          título diferente. A primeira versão fica guardada.
        </p>
        {ed.articles === 0 ? (
          <div className="empty">Nenhuma notícia no período.</div>
        ) : (
          <>
            <CompareBars
              ariaLabel="Manchetes editadas e média dos outros"
              rows={[{ key: "edited", label: "Manchete alterada", share: ed.edited_share, average: ed.average_edited_share,
                       detail: `${ed.edited} de ${ed.articles} notícias` }]}
              max={Math.max(0.2, ed.edited_share ?? 0, ed.average_edited_share ?? 0)}
            />
            <dl className="parsed">
              <div><dt>Reescritas</dt><dd>{ed.rewritten}</dd></div>
              <div><dt>Número ou negação mudou</dt><dd>{ed.meaning_flagged}</dd></div>
              <div><dt>Avisaram a correção no texto</dt><dd>{ed.edited ? `${ed.declared} de ${ed.edited}` : "—"}</dd></div>
            </dl>
            {ed.examples.length > 0 && (
              <>
                <h3 className="sub-title">Exemplos (antes → depois)</h3>
                <ul className="edit-list">
                  {ed.examples.map((e) => (
                    <li key={e.article_id}>
                      <span className="rel rel-ctx">{KIND[e.kind] ?? e.kind}</span>{" "}
                      {e.observed_at && <span className="muted">{formatDate(e.observed_at)}</span>}
                      <div className="edit-before">{e.original_headline}</div>
                      <div className="edit-after">→ {e.new_headline}</div>
                      <a href={e.url} target="_blank" rel="noopener noreferrer" className="muted">abrir a matéria</a>
                    </li>
                  ))}
                </ul>
              </>
            )}
            {ed.edited === 0 && ed.peers_edited > 0 && (
              <p className="callout">
                Nenhuma edição detectada aqui, enquanto os outros veículos somam {ed.peers_edited}. O feed deste veículo
                pode simplesmente não mostrar alterações: ausência de edição detectada não prova que não houve.
              </p>
            )}
            <p className="callout">
              Só vê mudanças enquanto a matéria continua no feed (coleta a cada 30 minutos). &ldquo;Número ou negação
              mudou&rdquo; é um sinal automático para você ler as duas versões; não afirma que o sentido mudou.
            </p>
          </>
        )}
      </section>
    </>
  );
}
