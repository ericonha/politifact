"use server";

import { revalidatePath } from "next/cache";
import { setFavorite } from "@/lib/api";

/** Marca ou desmarca um veículo como favorito (guardado no banco, vale para todas as telas). */
export async function toggleFavorite(formData: FormData) {
  const id = Number(formData.get("outlet_id"));
  const favorite = formData.get("favorite") === "true";
  if (!Number.isInteger(id)) return;
  await setFavorite(id, favorite);
  revalidatePath("/", "layout");
}
