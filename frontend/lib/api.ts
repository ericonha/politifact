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
  relevance: number;
};

export type Briefing = {
  topic: string;
  label: string;
  generated_at: string;
  period_start: string;
  period_end: string;
  model: string;
  prompt_version: string;
  story_count: number;
  overview: string;
  points: { text: string; stories: { id: number; title: string; outlet_count: number }[] }[];
  validation: { status: "ok" | "adjusted" | "rejected"; problems: string[] } | null;
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

export type Share = { share: number | null; average_share: number | null };

export type OutletProfile = {
  outlet: { id: number; name: string; group: Group; language: string; favorite: boolean; active: boolean; collection_notes: string | null };
  range: { start: string; end: string; label: string; bucket_seconds: number; generated_at: string };
  peers: { group: Group; count: number; min_articles: number };
  totals: { articles: number; analyzed_headlines: number; ai_readings: number; stories: number; exclusive_stories: number };
  timeline: { buckets: string[]; counts: number[] };
  sections: ({ topic: string; label: string; count: number } & Share)[];
  actors: ({ key: string; name: string; count: number } & Share)[];
  form: ({ key: string; label: string; n: number } & Share)[];
  tone: {
    key: string; name: string; n: number; negativo: number; neutro: number; positivo: number; incerto: number;
    peers_n: number; peers_negative_share: number | null;
  }[];
  exclusivity: Share;
};

export const getOutletProfile = (id: number, window: "7d" | "30d") =>
  getOrError<OutletProfile>(`/api/outlets/${id}/profile?window=${window}`);

export type OutletBias = {
  outlet: { id: number; name: string; group: Group; language: string };
  range: { start: string; end: string; label: string; generated_at: string };
  peers: { group: Group; count: number; min_outlets_for_omission: number };
  omissions: {
    eligible_stories: number; covered: number; missed: number; omission_rate: number | null;
    average_rate: number | null; min_outlets: number;
    by_topic: { topic: string; label: string; eligible: number; missed: number; omission_rate: number }[];
    blind_spots: { story_id: number; title: string; topic: string | null; outlets_count: number; outlets: string[]; first_published_at: string | null }[];
  };
  delay: {
    stories: number; median_minutes: number | null; first_share: number | null;
    average_median_minutes: number | null; enough: boolean; tolerance_minutes: number;
  };
  vocabulary: {
    enough: boolean; docs_outlet: number; docs_others: number; min_docs: number; stories?: number;
    comparison_outlets: number; language: string;
    uses_more: VocabTerm[]; uses_less: VocabTerm[];
  };
  edits: {
    articles: number; edited: number; edited_share: number | null; average_edited_share: number | null;
    meaning_flagged: number; rewritten: number; declared: number; declared_share: number | null;
    peers_articles: number; peers_edited: number;
    examples: { article_id: number; url: string; original_headline: string; new_headline: string | null;
                kind: "possivel_sentido" | "reescrita" | "ajuste" | "resumo"; observed_at: string | null; declared: boolean }[];
  };
};
export type VocabTerm = { term: string; z: number; docs_outlet: number; outlet_share: number; others_share: number };

export const getOutletBias = (id: number, window: "7d" | "30d") =>
  getOrError<OutletBias>(`/api/outlets/${id}/bias?window=${window}`);

export const getBriefings = () => get<Briefing[]>("/api/briefings").catch(() => [] as Briefing[]);
export const triggerBriefings = (force = false) => post(`/api/briefings${force ? "?force=true" : ""}`);

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

// ---------------------------------------------------------------------------
// Fase 6: checagem de fatos
// ---------------------------------------------------------------------------

export type Assessment =
  | "verdadeiro" | "impreciso" | "falso"
  | "provavelmente_verdadeiro" | "provavelmente_falso"
  | "sem_evidencia" | "nao_checavel";

export type EvidenceRow = {
  id: number;
  provider: "bcb_sgs" | "factcheck" | "press" | string;
  source_type: "official_data" | "fact_check" | "press" | string;
  source_url: string;
  source_title: string | null;
  relevant_passage: string | null;
  relationship: "supports" | "contradicts" | "context" | "related" | string;
  verification_status: string;
  published_at: string | null;
  retrieved_at: string;
  data: Record<string, unknown> | null;
};

export type FactCheckVersion = {
  id: number;
  assessment: Assessment;
  assessment_label: string;
  explanation: string;
  limitations: string[];
  method: "rules" | "llm" | "none" | null;
  model: string | null;
  prompt_version: string | null;
  review_status: "pending_review" | "approved" | "rejected";
  reviewed_at: string | null;
  review_note: string | null;
  created_at: string;
  supersedes_id: number | null;
  evidence: EvidenceRow[];
};

export type ParsedClaim = {
  indicator: string | null;
  indicator_label: string | null;
  value: number | null;
  decimals?: number;
  unit: string | null;
  period_label: string;
  checkable: boolean;
  problems: string[];
};

export type ClaimDetail = {
  id: number;
  text: string;
  quote: string | null;
  type: string | null;
  parsed: ParsedClaim | null;
  article_id: number | null;
  current: FactCheckVersion | null;
  history: { id: number; assessment: Assessment; review_status: string; created_at: string; supersedes_id: number | null }[];
};

export type Investigation = {
  id: number;
  input_type: "text" | "article";
  input_text: string;
  status: "queued" | "running" | "done" | "failed";
  error: string | null;
  extraction: { method: string; model?: string; problems: string[] } | null;
  created_at: string;
  finished_at: string | null;
  article: { id: number; headline: string; original_url: string; outlet: string; published_at: string | null } | null;
  claims: ClaimDetail[];
};

export type InvestigationSummary = {
  id: number;
  input_type: "text" | "article";
  input_text: string;
  status: Investigation["status"];
  error: string | null;
  created_at: string;
  claims: { claim_id: number; text: string; assessment: Assessment; review_status: string }[];
};

async function postOrError<T>(path: string, body: unknown): Promise<{ data: T; error: null } | { data: null; error: string }> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (res.ok) return { data: (await res.json()) as T, error: null };
  let detail = `A API respondeu ${res.status}`;
  try {
    const b = await res.json();
    if (typeof b?.detail === "string") detail = b.detail;
  } catch {
    /* corpo não é JSON */
  }
  return { data: null, error: detail };
}

export const submitClaim = (body: { text?: string; article_id?: number; url?: string }) =>
  postOrError<{ investigation_id: number; job_id: string }>("/api/claims", body);
export const getInvestigations = () => get<InvestigationSummary[]>("/api/investigations?limit=30").catch(() => []);
export const getInvestigation = (id: number) => getOrError<Investigation>(`/api/investigations/${id}`);
export const recheckClaim = (claimId: number) => postOrError<{ job_id: string }>(`/api/claims/${claimId}/recheck`, {});
export const reviewFactCheck = (id: number, decision: "approved" | "rejected", note?: string) =>
  postOrError<{ id: number }>(`/api/fact-checks/${id}/review`, { decision, note });
export const getArticle = (id: number) => get<Article>(`/api/articles/${id}`).catch(() => null);

export const ASSESSMENT_LABELS: Record<Assessment, string> = {
  verdadeiro: "Verdadeiro",
  impreciso: "Impreciso",
  falso: "Falso",
  provavelmente_verdadeiro: "Provavelmente verdadeiro",
  provavelmente_falso: "Provavelmente falso",
  sem_evidencia: "Sem evidência suficiente",
  nao_checavel: "Não checável",
};
