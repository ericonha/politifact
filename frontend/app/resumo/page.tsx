import Link from "next/link";
import { revalidatePath } from "next/cache";
import { BriefingBlock } from "@/components/BriefingBlock";
import { PageLayout, Sidebar } from "@/components/Sidebar";
import { TOPIC_LABELS, getBriefings, getCollectionStatus, triggerBriefings } from "@/lib/api";

async function generateNow() {
  "use server";
  await triggerBriefings();
  revalidatePath("/resumo");
}

export default async function BriefingPage() {
  const [briefings, status] = await Promise.all([getBriefings(), getCollectionStatus()]);
  const have = new Set(briefings.map((b) => b.topic));
  const missing = Object.entries(TOPIC_LABELS).filter(([k]) => k !== "outros" && !have.has(k));

  return (
    <PageLayout
      sidebar={
        <Sidebar
          title="Resumo"
          intro="O que está acontecendo em cada seção nas últimas 24 horas, escrito por IA local a partir das histórias mais relevantes."
          basePath="/resumo"
          params={{}}
          status={status}
        />
      }
    >
      <div className="briefing-head">
        <p className="note" style={{ margin: 0 }}>
          Cada ponto mostra de que histórias saiu. Números e nomes que não aparecem nas notícias citadas são
          descartados antes de publicar. Mesmo assim, confira nas fontes antes de repetir uma informação.
        </p>
        <form action={generateNow}>
          <button type="submit" className="button small secondary">Atualizar resumos</button>
        </form>
      </div>

      {briefings.length === 0 ? (
        <div className="empty">
          Nenhum resumo ainda. Eles são escritos depois de cada coleta, com o Ollama ligado e o modelo baixado
          (<code>ollama pull qwen2.5:7b</code>). Você também pode clicar em Atualizar resumos.
        </div>
      ) : (
        <nav className="briefing-toc" aria-label="Seções do resumo">
          {briefings.map((b) => <a key={b.topic} href={`#brief-${b.topic}`}>{b.label}</a>)}
        </nav>
      )}

      {briefings.map((b) => <BriefingBlock key={b.topic} b={b} />)}

      {briefings.length > 0 && missing.length > 0 && (
        <p className="note">
          Sem resumo agora: {missing.map(([, l]) => l).join(", ")}. Uma seção precisa de pelo menos 2 histórias
          nas últimas 24 horas. Veja as <Link href="/">histórias</Link>.
        </p>
      )}
    </PageLayout>
  );
}
