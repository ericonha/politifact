import { formatDate, type StoryFraming } from "@/lib/api";

type Item = StoryFraming["items"][number];

function escapeRe(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Marca os termos de impacto dentro da manchete (texto tratado como dado, nunca HTML). */
function Highlighted({ text, terms }: { text: string; terms: string[] }) {
  if (!terms.length) return <>{text}</>;
  const re = new RegExp(`(?<![\\p{L}])(${terms.map(escapeRe).join("|")})(?![\\p{L}])`, "giu");
  const parts = text.split(re);
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 ? <mark key={i} title="termo de impacto">{part}</mark> : <span key={i}>{part}</span>,
      )}
    </>
  );
}

function Form({ o }: { o: Item["observable"] }) {
  const chips: string[] = [];
  if (o.attribution_verbs.length) chips.push(`fala atribuída (${o.attribution_verbs.join(", ")})`);
  if (o.has_quote) chips.push("aspas");
  if (o.is_question) chips.push("pergunta");
  if (o.has_exclamation) chips.push("exclamação");
  if (o.has_number) chips.push("número");
  if (!chips.length) return <span className="muted">relato direto</span>;
  return (
    <span className="chips">
      {chips.map((c) => <span key={c} className="chip">{c}</span>)}
    </span>
  );
}

function AiReading({ llm }: { llm: Item["llm"] }) {
  if (!llm) return <span className="muted">—</span>;
  if (llm.validation.status === "rejected") {
    return <span className="muted" title={llm.validation.problems.join("; ")}>resposta descartada pela validação</span>;
  }
  const evidence = llm.evidence.length ? `Trechos: “${llm.evidence.join("”, “")}”` : "Sem trecho que sustente um tom.";
  return (
    <div className="ai-reading">
      <div>{llm.angle}</div>
      <div className="muted">
        {llm.main_actor ? <>tom em relação a <strong>{llm.main_actor}</strong>: <strong>{llm.tone}</strong></> : <>tom: <strong>{llm.tone}</strong></>}
        {" · "}
        <span title={`${evidence}\nModelo: ${llm.model} · ${llm.prompt_version}`}>por quê?</span>
      </div>
      {llm.validation.status === "adjusted" && (
        <div className="muted" title={llm.validation.problems.join("; ")}>
          ajustada pela validação (o modelo disse “{llm.validation.model_tone}”)
        </div>
      )}
    </div>
  );
}

export function HeadlineComparison({ data }: { data: StoryFraming }) {
  const { comparison: c, items } = data;
  const multi = c.outlets.length > 1;
  const anyAi = items.some((i) => i.llm);

  const notes: React.ReactNode[] = [];
  if (multi && c.different_leads) {
    notes.push(
      <>
        Cada veículo pôs alguém diferente na frente da manchete:{" "}
        {Object.entries(c.lead_actor_by_outlet)
          .map(([outlet, leads]) => `${outlet} → ${[...new Set(leads)].join(" / ")}`)
          .join("; ")}
        .
      </>,
    );
  }
  for (const a of c.partial_actors.slice(0, 5)) {
    // Maioria cita: aponta quem NÃO cita (mais curto e mais claro).
    if (a.outlets.length > c.outlets.length / 2) {
      const missing = c.outlets.filter((o) => !a.outlets.includes(o));
      notes.push(<><strong>{a.name}</strong> não aparece na manchete de {missing.join(", ")}.</>);
    } else {
      notes.push(<>Só {a.outlets.join(", ")} {a.outlets.length === 1 ? "cita" : "citam"} <strong>{a.name}</strong> na manchete.</>);
    }
  }
  if (multi && c.attribution_outlets.length) {
    notes.push(<>Manchete em forma de fala atribuída (&ldquo;diz&rdquo;, &ldquo;critica&rdquo;…): {c.attribution_outlets.join(", ")}.</>);
  }
  if (c.question_outlets.length) notes.push(<>Manchete em forma de pergunta: {c.question_outlets.join(", ")}.</>);
  const loaded = Object.entries(c.loaded_terms_by_outlet);
  if (loaded.length) {
    notes.push(<>Termos de impacto: {loaded.map(([o, t]) => `${o} (${t.join(", ")})`).join("; ")}.</>);
  }

  return (
    <section className="card">
      <h2>Manchetes lado a lado</h2>
      <p className="sub">
        Como cada veículo apresentou a história. A análise olha só o título e o resumo e descreve o texto,
        não o veículo: não é uma nota de viés.
      </p>

      {notes.length > 0 && (
        <>
          <h3 className="h3">O que muda entre as manchetes</h3>
          <ul className="limits">{notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </>
      )}

      <div className="scroll" style={{ marginTop: 12 }}>
        <table className="headlines">
          <thead>
            <tr>
              <th>Veículo</th>
              <th>Manchete</th>
              <th>Em destaque</th>
              <th>Forma</th>
              <th>Leitura da IA</th>
            </tr>
          </thead>
          <tbody>
            {items.map((i) => (
              <tr key={i.article_id}>
                <td>
                  {i.language.startsWith("en") && <span className="lang-badge">EN</span>}
                  {i.outlet_name}
                  <div className="muted">{formatDate(i.published_at)}</div>
                </td>
                <td>
                  <a href={i.original_url} target="_blank" rel="noopener noreferrer" className="headline">
                    <Highlighted text={i.headline} terms={i.observable.loaded_terms} />
                  </a>
                </td>
                <td>{i.observable.lead_actor ?? <span className="muted">—</span>}</td>
                <td><Form o={i.observable} /></td>
                <td><AiReading llm={i.llm} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <details className="table-view">
        <summary>Como isto é feito</summary>
        <ul className="limits">
          <li>&ldquo;Não aparece na manchete&rdquo; compara nomes escritos: &ldquo;ex-presidente&rdquo; no lugar de &ldquo;Bolsonaro&rdquo; conta como não citar o nome.</li>
          <li><strong>Em destaque, forma e termos de impacto</strong> vêm de regras fixas sobre o texto (sem IA): o primeiro nome próprio da manchete, verbos de fala, aspas, pergunta, número e uma lista curta de palavras fortes.</li>
          <li><strong>Leitura da IA</strong> vem de um modelo local (Ollama). Todo tom diferente de &ldquo;neutro&rdquo; precisa de um trecho copiado literalmente da manchete ou do resumo; se o trecho não existe no texto, o tom vira &ldquo;incerto&rdquo;. Modelo e versão do prompt ficam registrados.</li>
          <li>Só histórias com 2 ou mais veículos recebem a leitura da IA, e só nas últimas 72 h.</li>
          {!anyAi && <li>Nenhuma leitura da IA ainda nesta história: ela aparece depois da próxima coleta, com o Ollama ligado.</li>}
        </ul>
      </details>
    </section>
  );
}
