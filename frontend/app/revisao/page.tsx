import Link from "next/link";
import { revalidatePath } from "next/cache";
import { formatDate, getReview, resolveReview, triggerProcessing } from "@/lib/api";

async function resolve(formData: FormData) {
  "use server";
  const decisionId = Number(formData.get("decision_id"));
  const action = formData.get("action") === "assign" ? "assign" : "new_story";
  await resolveReview(decisionId, action);
  revalidatePath("/revisao");
  revalidatePath("/");
}

async function processNow() {
  "use server";
  await triggerProcessing();
  revalidatePath("/revisao");
}

export default async function ReviewPage() {
  const items = await getReview();

  return (
    <>
      <div className="toolbar">
        <h1>Revisão do agrupamento</h1>
        <form action={processNow}>
          <button type="submit" className="button secondary">Agrupar notícias novas</button>
        </form>
      </div>
      <p className="note">
        Notícias parecidas com uma história, mas não o bastante para o sistema decidir sozinho.
        Enquanto não forem revisadas, elas não contam na cobertura. Cada escolha fica registrada.
      </p>

      {items.length === 0 ? (
        <div className="empty">Nada para revisar.</div>
      ) : (
        <ul className="review">
          {items.map((it) => (
            <li key={it.decision_id}>
              <div className="meta">
                <span className="outlet">{it.outlet_name}</span>
                <span>{formatDate(it.published_at)}</span>
                {it.score != null && <span>similaridade {it.score.toFixed(2)}</span>}
              </div>
              <a href={it.original_url} target="_blank" rel="noopener noreferrer" className="headline">
                {it.headline}
              </a>
              {it.candidate_story_id && (
                <p className="candidate">
                  Parece com:{" "}
                  <Link href={`/historias/${it.candidate_story_id}`}>{it.candidate_story_title}</Link>
                </p>
              )}
              <form action={resolve} className="actions">
                <input type="hidden" name="decision_id" value={it.decision_id} />
                {it.candidate_story_id && (
                  <button type="submit" name="action" value="assign" className="button">
                    Juntar a essa história
                  </button>
                )}
                <button type="submit" name="action" value="new_story" className="button secondary">
                  É outra história
                </button>
              </form>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
