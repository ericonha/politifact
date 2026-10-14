"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { recheckClaim, reviewFactCheck, setFavorite, submitClaim } from "@/lib/api";

/** Marca ou desmarca um veículo como favorito (guardado no banco, vale para todas as telas). */
export async function toggleFavorite(formData: FormData) {
  const id = Number(formData.get("outlet_id"));
  const favorite = formData.get("favorite") === "true";
  if (!Number.isInteger(id)) return;
  await setFavorite(id, favorite);
  revalidatePath("/", "layout");
}

/** Pede uma checagem e abre a página dela. */
export async function submitClaimAction(formData: FormData) {
  const articleId = Number(formData.get("article_id"));
  const text = String(formData.get("text") ?? "").trim();
  const body = Number.isInteger(articleId) && articleId > 0 ? { article_id: articleId } : { text };
  const { data, error } = await submitClaim(body);
  if (!data) redirect(`/checagem?erro=${encodeURIComponent(error)}&texto=${encodeURIComponent(text.slice(0, 1500))}`);
  redirect(`/checagem/${data.investigation_id}`);
}

/** Refaz a checagem de uma afirmação (nova versão; a anterior fica no histórico). */
export async function recheckAction(formData: FormData) {
  const claimId = Number(formData.get("claim_id"));
  const inv = Number(formData.get("investigation_id"));
  if (Number.isInteger(claimId)) await recheckClaim(claimId);
  revalidatePath(`/checagem/${inv}`);
}

/** Revisão humana da versão atual da checagem. */
export async function reviewAction(formData: FormData) {
  const id = Number(formData.get("fact_check_id"));
  const inv = Number(formData.get("investigation_id"));
  const decision = formData.get("decision") === "approved" ? "approved" : "rejected";
  const note = String(formData.get("note") ?? "").trim() || undefined;
  if (Number.isInteger(id)) await reviewFactCheck(id, decision, note);
  revalidatePath(`/checagem/${inv}`);
  revalidatePath("/checagem");
}
