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
  outlet_group: "nacional" | "internacional";
  favorite: boolean;
};

export type CollectionStatus = {
  last_success_at: string | null;
  last_run_started_at: string | null;
  last_run_status: string | null;
  running: boolean;
  interval_minutes: number;
  next_expected_at: string | null;
  failing_outlets: string[];
};

export type Group = "nacional" | "internacional";
export const GROUPS: { value: Group | undefined; label: string }[] = [
  { value: undefined, label: "Todos" },
  { value: "nacional", label: "Nacionais" },
  { value: "internacional", label: "Internacionais" },
];
export function parseGroup(value: string | undefined): Group | undefined {
  return value === "nacional" || value === "internacional" ? value : undefined;
}

export type OutletCoverage = {
  outlet_id: number;
  outlet_name: string;
  article_count: number;
};

export type Story = {
  id: number;
  title: string;
  summary: string | null;
  topic: string | null;
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
  topic: string | null;
  topic_source: string | null;
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
  topic: string | null;
  topic_source: string | null;
};

export type Topic = { key: string; label: string; article_count: number };

// Mesma ordem e nomes de app/topics.py (backend). Usado para rótulos sem ida à API.
export const TOPIC_LABELS: Record<string, string> = {
  politica: "Política",
  economia: "Economia",
  negocios: "Negócios",
  internacional: "Internacional",
  brasil: "Brasil",
  esportes: "Esportes",
  saude: "Saúde",
  "ciencia-tecnologia": "Ciência e tecnologia",
  cultura: "Cultura e entretenimento",
  outros: "Outros",
};

export function parseTopic(value: string | undefined): string | undefined {
  return value && value in TOPIC_LABELS ? value : undefined;
}

export type OutletCoverageRow = {
  id: number;
  slug: string;
  name: string;
  group: Group;
  language: string;
  active: boolean;
  collection_notes: string | null;
  article_count: number;
  story_count: number;
  exclusive_story_count: number;
  covered_fraction: number | null;
  gap_hours: number;
  gaps: { start: string; end: string }[];
  failed_runs: number;
  possible_overflow_runs: number;
  last_success_at: string | null;
};

export type CoverageReport = {
  range: { start: string; end: string; label: string; bucket_seconds: number; generated_at: string };
  totals: {
    articles: number;
    stories: number;
    stories_all_active_outlets: number;
    active_outlets: number;
    duplicates_excluded: number;
    undated_articles: number;
    pending_review: number;
    not_clustered: number;
  };
  outlets: OutletCoverageRow[];
  timeline: { buckets: string[]; series: { outlet_id: number; counts: number[] }[] };
  reach_distribution: { outlets: number; stories: number }[];
  top_stories: Story[];
  topic: string | null;
  group: Group | null;
  topics: { topic: string; label: string; by_outlet: Record<string, number>; total: number }[];
  collection_interval_minutes: number;
};

export type CompareReport = {
  bucket_seconds: number;
  timeline: { buckets: string[]; series: { story_id: number; counts: number[] }[] };
  stories: {
    id: number;
    title: string;
    first_observed_at: string | null;
    last_observed_at: string | null;
    article_count: number;
    outlets: { outlet_id: number; outlet_name: string; article_count: number; first_published_at: string }[];
    articles: {
      article_id: number;
      outlet_name: string;
      headline: string;
      original_url: string;
      published_at: string;
      assignment_method: string;
    }[];
  }[];
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

/** Como `get`, mas devolve a mensagem de erro da API (422) em vez de lançar. */
async function getOrError<T>(path: string): Promise<{ data: T; error: null } | { data: null; error: string }> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (res.ok) return { data: (await res.json()) as T, error: null };
  let detail = `A API respondeu ${res.status}`;
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") detail = body.detail;
  } catch {
    /* corpo não é JSON */
  }
  return { data: null, error: detail };
}

function qs(params: Record<string, string | number | undefined | (string | number)[]>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === "") continue;
    for (const item of Array.isArray(v) ? v : [v]) q.append(k, String(item));
  }
  return q.toString();
}

export const getOutlets = () => get<Outlet[]>("/api/outlets");
export const getTopics = (window: Window) => get<Topic[]>(`/api/topics?window=${window}`);
export type OutletChoice = { outletId?: number; favorites?: boolean };

function outletParams(c?: OutletChoice) {
  return { outlet_id: c?.outletId, favorites: c?.favorites && !c?.outletId ? "true" : undefined };
}

export const getStories = (window: Window, topic?: string, choice?: OutletChoice) =>
  get<Story[]>(`/api/stories?${qs({ window, topic, ...outletParams(choice) })}`);
export const getArticles = (window: Window, outletId?: number, topic?: string, favorites?: boolean) =>
  get<Article[]>(`/api/articles?${qs({ window, limit: 300, topic, ...outletParams({ outletId, favorites }) })}`);
export const getCollectionStatus = () => get<CollectionStatus>("/api/collection-status").catch(() => null);
export const setFavorite = (outletId: number, favorite: boolean) =>
  post(`/api/outlets/${outletId}/favorite`, { favorite });
export const getCoverage = (p: {
  window?: string; from?: string; to?: string; topic?: string; group?: string; outlet_id?: number; favorites?: string;
}) =>
  getOrError<CoverageReport>(`/api/coverage?${qs(p)}`);
export type Observable = {
  headline_words: number;
  is_question: boolean;
  has_exclamation: boolean;
  has_quote: boolean;
  has_number: boolean;
  attribution_verbs: string[];
  lead_actor: string | null;
  headline_actors: { key: string; name: string }[];
  actors: { key: string; name: string }[];
  loaded_terms: string[];
  loaded_terms_summary: string[];
};

export type LlmFraming = {
  angle: string;
  main_actor: string | null;
  tone: "positivo" | "neutro" | "negativo" | "incerto";
  evidence: string[];
  voices: string[];
  validation: { status: "ok" | "adjusted" | "rejected"; problems: string[]; model_tone: string };
  model: string;
  prompt_version: string;
  created_at: string;
};

export type StoryFraming = {
  story_id: number;
  items: {
    article_id: number;
    outlet_name: string;
    language: string;
    headline: string;
    summary: string | null;
    original_url: string;
    published_at: string | null;
    observable: Observable;
    llm: LlmFraming | null;
  }[];
  comparison: {
    outlets: string[];
    actors: { key: string; name: string; outlets: string[]; in_all: boolean }[];
    partial_actors: { key: string; name: string; outlets: string[]; in_all: boolean }[];
    lead_actor_by_outlet: Record<string, string[]>;
    different_leads: boolean;
    attribution_outlets: string[];
    question_outlets: string[];
    loaded_terms_by_outlet: Record<string, string[]>;
  };
};

export type Rating = {
  outlet_id: number;
  provider: string;
  rating: string;
  rating_label: string;
  methodology_url: string;
  reference_url: string | null;
  assessed_at: string;
  valid_from: string | null;
  valid_until: string | null;
  confidence: number | null;
  notes: string | null;
};

export const getStoryFraming = (id: number) => get<StoryFraming>(`/api/stories/${id}/framing`);
export const getRatings = () => get<Rating[]>("/api/ratings");

export const getCompare = (ids: number[]) => getOrError<CompareReport>(`/api/compare?${qs({ ids })}`);
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

const timeFmt = new Intl.DateTimeFormat("pt-BR", { timeStyle: "short", timeZone: "America/Sao_Paulo" });

export function formatTime(value: string | null): string {
  return value ? timeFmt.format(new Date(value)) : "—";
}

/** "agora", "há 12 min", "há 3 h", "há 2 dias" (ou data, se mais antigo). */
export function timeAgo(value: string | null, now = Date.now()): string {
  if (!value) return "—";
  const min = Math.round((now - new Date(value).getTime()) / 60000);
  if (min < 1) return "agora";
  if (min < 60) return `há ${min} min`;
  const h = Math.round(min / 60);
  if (h < 24) return `há ${h} h`;
  const d = Math.round(h / 24);
  if (d <= 7) return `há ${d} ${d === 1 ? "dia" : "dias"}`;
  return formatDate(value);
}

/** Parâmetros de filtro de veículo vindos da URL (?veiculo=3 ou ?favoritos=1). */
export function parseOutletChoice(sp: { veiculo?: string; favoritos?: string }): OutletChoice {
  const id = sp.veiculo ? Number(sp.veiculo) : NaN;
  if (Number.isInteger(id) && id > 0) return { outletId: id };
  return { favorites: sp.favoritos === "1" };
}
