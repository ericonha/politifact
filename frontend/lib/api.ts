// Todas as chamadas acontecem no servidor do Next.js (server components),
// então API_URL aponta para o nome do serviço dentro do Docker.
const API_URL = process.env.API_URL ?? "http://localhost:8000";

export type Outlet = {
  id: number;
  slug: string;
  name: string;
  canonical_domain: string;
  country: string;
  language: string;
  feed_urls: string[];
  collection_notes: string | null;
  active: boolean;
};

export type OutletCoverage = {
  outlet_id: number;
  outlet_name: string;
  article_count: number;
};

export type Story = {
  id: number;
  title: string;
  summary: string | null;
  first_observed_at: string | null;
  last_observed_at: string | null;
  article_count: number;
  outlet_count: number;
  coverage: OutletCoverage[];
};

export type StoryArticle = {
  article_id: number;
  outlet_id: number;
  outlet_name: string;
  headline: string;
  summary: string | null;
  original_url: string;
  published_at: string | null;
  assignment_method: "seed" | "auto" | "syndicated" | "manual";
  cluster_confidence: number | null;
};

export type StoryDetail = Story & { articles: StoryArticle[] };

export type ReviewItem = {
  decision_id: number;
  score: number | null;
  decided_at: string;
  article_id: number;
  outlet_name: string;
  headline: string;
  summary: string | null;
  original_url: string;
  published_at: string | null;
  candidate_story_id: number | null;
  candidate_story_title: string | null;
};

export type Article = {
  id: number;
  outlet_id: number;
  headline: string;
  summary: string | null;
  canonical_url: string;
  original_url: string;
  published_at: string | null;
  updated_at: string | null;
  first_seen_at: string;
  collected_at: string;
  collection_provider: string;
  processing_status: string;
};

export type CollectionRun = {
  id: number;
  provider: string;
  outlet_id: number | null;
  started_at: string;
  finished_at: string | null;
  records_discovered: number;
  records_inserted: number;
  records_failed: number;
  status: "running" | "success" | "partial" | "failed";
  error_summary: string | null;
};

export type Window = "24h" | "3d" | "7d";

export const WINDOWS: { value: Window; label: string }[] = [
  { value: "24h", label: "24 horas" },
  { value: "3d", label: "3 dias" },
  { value: "7d", label: "7 dias" },
];

export function parseWindow(value: string | undefined): Window {
  return WINDOWS.some((w) => w.value === value) ? (value as Window) : "24h";
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${path} respondeu ${res.status}`);
  return res.json() as Promise<T>;
}

export const getOutlets = () => get<Outlet[]>("/api/outlets");
export const getStories = (window: Window) => get<Story[]>(`/api/stories?window=${window}`);
export const getArticles = (window: Window, outletId?: number) =>
  get<Article[]>(`/api/articles?window=${window}&limit=300${outletId ? `&outlet_id=${outletId}` : ""}`);
export const getCollectionRuns = () => get<CollectionRun[]>("/api/collection-runs?limit=60");

export const getStory = (id: number) => get<StoryDetail>(`/api/stories/${id}`);
export const getReview = () => get<ReviewItem[]>("/api/review");

async function post(path: string, body?: unknown): Promise<void> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    cache: "no-store",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`API ${path} respondeu ${res.status}`);
}

export const resolveReview = (decisionId: number, action: "assign" | "new_story") =>
  post(`/api/review/${decisionId}`, { action });
export const triggerProcessing = () => post("/api/processing");

export async function triggerCollection(): Promise<void> {
  const res = await fetch(`${API_URL}/api/collection-runs`, { method: "POST", cache: "no-store" });
  if (!res.ok) throw new Error(`API respondeu ${res.status} ao disparar a coleta`);
}

const dateFmt = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "short",
  timeStyle: "short",
  timeZone: "America/Sao_Paulo",
});

export function formatDate(value: string | null): string {
  return value ? dateFmt.format(new Date(value)) : "—";
}
