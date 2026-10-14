// Dados 100% FICTÍCIOS para as capturas de tela da demonstração. Nenhum veículo, pessoa ou número
// aqui é real: as cidades (Vale Verde, Pedra Alta), os veículos e os políticos são inventados.
// As páginas renderizadas são as reais (app/**), só que lendo este módulo no lugar de lib/api.
export * from "../lib/api";

const now = Date.now(), M = 60e3, H = 60 * M, D = 24 * H;
const iso = (ms: number) => new Date(now - ms).toISOString();

const OUT = [
  [1, "Jornal do Vale", "nacional"], [2, "Rádio Serra", "nacional"], [3, "Gazeta Norte", "nacional"],
  [4, "Diário da Capital", "nacional"], [5, "Correio do Sul", "nacional"], [6, "Tribuna Central", "nacional"],
  [7, "Harbor Post", "internacional"], [8, "Vale Wire", "internacional"],
] as const;
const name = (id: number) => OUT.find((o) => o[0] === id)![1];

export async function getCollectionStatus() {
  return { last_success_at: iso(7 * M), last_run_started_at: iso(8 * M), last_run_status: "success", running: false,
    interval_minutes: 30, next_expected_at: new Date(now + 22 * M).toISOString(), failing_outlets: [] };
}
export async function getOutlets() {
  return OUT.map(([id, n, g]) => ({ id, slug: n.toLowerCase().replace(/\s+/g, "-"), name: n, canonical_domain: `${id}.exemplo.invalid`,
    country: g === "nacional" ? "BR" : "US", language: g === "nacional" ? "pt-BR" : "en", feed_urls: [], collection_notes: null,
    active: true, outlet_group: g, favorite: id === 1 }));
}
export async function getTopics() {
  return [["politica", "Política", 48], ["economia", "Economia", 31], ["brasil", "Brasil", 27], ["esportes", "Esportes", 22],
    ["saude", "Saúde", 12], ["ciencia-tecnologia", "Ciência e tecnologia", 9], ["cultura", "Cultura e entretenimento", 8]]
    .map(([key, label, article_count]) => ({ key, label, article_count }));
}

const cov = (ids: number[]) => ids.map((id) => ({ outlet_id: id, outlet_name: name(id), article_count: 1 + (id % 2) }));
const STORIES = [
  { id: 1, title: "Prefeitura de Vale Verde reajusta tarifa de ônibus em 10%", topic: "politica", ids: [1, 2, 3, 4, 5, 6], ago: 3 * H,
    summary: "A passagem sobe de R$ 4,00 para R$ 4,40 a partir de segunda-feira; sindicato dos motoristas e oposição criticam o índice." },
  { id: 2, title: "Câmara aprova plano diretor de Pedra Alta após três anos de debate", topic: "politica", ids: [1, 2, 3, 5, 6], ago: 5 * H,
    summary: "O texto limita a altura de prédios no centro histórico e cria uma zona de preservação ambiental." },
  { id: 3, title: "Inflação em 12 meses fica em 4,8%, aponta instituto de pesquisa", topic: "economia", ids: [1, 3, 4, 6, 7], ago: 8 * H, summary: null },
  { id: 4, title: "Vale Verde FC vence a final e é campeão estadual", topic: "esportes", ids: [2, 3, 4, 5], ago: 11 * H, summary: null },
  { id: 5, title: "Hospital Regional abre 120 novos leitos de UTI", topic: "saude", ids: [1, 5, 8], ago: 14 * H, summary: null },
  { id: 6, title: "Universidade estadual inaugura supercomputador para pesquisa climática", topic: "ciencia-tecnologia", ids: [3, 7, 8], ago: 16 * H, summary: null },
  { id: 7, title: "Porto de Santa Alva bate recorde de cargas no trimestre", topic: "economia", ids: [4, 6, 7], ago: 18 * H, summary: null },
  { id: 8, title: "Festival de cinema de Rio Claro tem recorde de público", topic: "cultura", ids: [2, 6], ago: 20 * H, summary: null },
];
const toStory = (s: (typeof STORIES)[number]) => ({
  id: s.id, title: s.title, summary: s.summary, topic: s.topic, first_observed_at: iso(s.ago + 4 * H), last_observed_at: iso(s.ago),
  article_count: s.ids.length + 2, outlet_count: s.ids.length, coverage: cov(s.ids), relevance: 1 });
export async function getStories() { return STORIES.map(toStory); }
export async function getBriefings() { return []; }

const ARTICLES = [
  [1, 1, "Prefeitura de Vale Verde reajusta tarifa de ônibus em 10%", "A passagem sobe de R$ 4,00 para R$ 4,40 a partir de segunda.", 3 * H],
  [2, 2, "Tarifa de ônibus em Vale Verde sobe 10% e chega a R$ 4,40", "O reajuste foi publicado no diário oficial do município.", 3 * H - 8 * M],
  [3, 3, "Prefeito impõe aumento de 10% na passagem e irrita usuários", "Moradores dizem que o serviço não melhorou.", 2 * H + 40 * M],
  [4, 4, "Passagem de ônibus em Vale Verde passa a custar R$ 4,40", "Reajuste de 10% vale a partir de segunda-feira.", 2 * H + 20 * M],
  [5, 5, "Oposição vê reajuste de ônibus como golpe no bolso do trabalhador", "Vereadores prometem acionar a Justiça contra o aumento.", 2 * H],
  [6, 6, "Prefeitura explica reajuste da tarifa e cita custo do diesel", "Segundo a secretaria, o índice repõe a inflação do setor.", 1 * H + 30 * M],
] as const;
export async function getStory(id: number) {
  const s = STORIES.find((x) => x.id === id) ?? STORIES[0];
  return { ...toStory(s), articles: ARTICLES.map(([aid, oid, headline, summary, ago]) => ({
    article_id: aid, outlet_id: oid, outlet_name: name(oid), headline, summary, original_url: "https://exemplo.invalid/" + aid,
    published_at: iso(ago), assignment_method: aid === 1 ? "seed" : "auto", cluster_confidence: aid === 1 ? null : 0.78 + aid / 100,
    topic: "politica", topic_source: "rules" })) };
}

const obs = (words: number, lead: string | null, extra: object = {}) => ({
  headline_words: words, is_question: false, has_exclamation: false, has_quote: false, has_number: true, attribution_verbs: [],
  lead_actor: lead, headline_actors: lead ? [{ key: lead.toLowerCase(), name: lead }] : [], actors: [], loaded_terms: [], loaded_terms_summary: [], ...extra });
const llm = (angle: string, actor: string | null, tone: "positivo" | "neutro" | "negativo" | "incerto", evidence: string[], voices: string[]) => ({
  angle, main_actor: actor, tone, evidence, voices, validation: { status: "ok" as const, problems: [], model_tone: tone },
  model: "qwen2.5:7b", prompt_version: "framing-v1", created_at: iso(30 * M) });
export async function getStoryFraming(id: number) {
  const a = await getStory(id);
  const rows = [
    obs(9, "Prefeitura", { attribution_verbs: [] }), obs(11, "Tarifa"), obs(9, "Prefeito", { loaded_terms: ["impõe", "irrita"], loaded_terms_summary: ["impõe", "irrita"] }),
    obs(8, "Passagem"), obs(11, "Oposição", { loaded_terms: ["golpe"], loaded_terms_summary: ["golpe"], has_quote: false }), obs(10, "Prefeitura", { attribution_verbs: ["explica", "cita"] }),
  ];
  const llms = [
    llm("Prefeitura anuncia reajuste de 10% na tarifa de ônibus", "Prefeitura", "neutro", [], ["Prefeitura"]),
    llm("Tarifa sobe 10% e chega a R$ 4,40", null, "neutro", [], []),
    llm("Aumento imposto pelo prefeito gera descontentamento", "Prefeito", "negativo", ["impõe aumento de 10%", "irrita usuários"], ["moradores"]),
    llm("Nova tarifa passa a valer na segunda-feira", null, "neutro", [], []),
    llm("Oposição critica o reajuste e diz que prejudica trabalhadores", "Oposição", "negativo", ["golpe no bolso do trabalhador"], ["vereadores"]),
    llm("Prefeitura justifica o aumento pelo custo do diesel", "Prefeitura", "positivo", ["repõe a inflação do setor"], ["secretaria"]),
  ];
  return { story_id: id, items: a.articles.map((x, i) => ({ article_id: x.article_id, outlet_name: x.outlet_name, language: "pt-BR", headline: x.headline,
      summary: x.summary, original_url: x.original_url, published_at: x.published_at, observable: rows[i], llm: llms[i] })),
    comparison: { outlets: a.articles.map((x) => x.outlet_name),
      actors: [{ key: "prefeitura", name: "Prefeitura", outlets: ["Jornal do Vale", "Tribuna Central"], in_all: false }],
      partial_actors: [{ key: "oposicao", name: "Oposição", outlets: ["Correio do Sul"], in_all: false }],
      lead_actor_by_outlet: { "Jornal do Vale": ["Prefeitura"], "Gazeta Norte": ["Prefeito"], "Correio do Sul": ["Oposição"], "Tribuna Central": ["Prefeitura"] },
      different_leads: true, attribution_outlets: ["Tribuna Central"], question_outlets: [],
      loaded_terms_by_outlet: { "Gazeta Norte": ["impõe", "irrita"], "Correio do Sul": ["golpe"] } } };
}

// ----------------------------------------------------------------- veículo
export async function getRatings() { return []; }
const share = (s: number | null, a: number | null) => ({ share: s, average_share: a });
export async function getOutletProfile() {
  return { error: null, data: {
    outlet: { id: 3, name: "Gazeta Norte", group: "nacional", language: "pt-BR", favorite: false, active: true, collection_notes: null },
    range: { start: iso(7 * D), end: iso(0), label: "7 dias", bucket_seconds: 86400, generated_at: iso(0) },
    peers: { group: "nacional", count: 5, min_articles: 10 },
    totals: { articles: 210, analyzed_headlines: 200, ai_readings: 40, stories: 120, exclusive_stories: 14 },
    timeline: { buckets: Array.from({ length: 7 }, (_, i) => iso((6 - i) * D)), counts: [30, 32, 28, 31, 29, 30, 30] },
    sections: [{ topic: "politica", label: "Política", count: 90, ...share(0.43, 0.38) }, { topic: "esportes", label: "Esportes", count: 40, ...share(0.19, 0.21) },
      { topic: "economia", label: "Economia", count: 35, ...share(0.17, 0.2) }],
    actors: [{ key: "prefeito", name: "Prefeito", count: 40, ...share(0.2, 0.18) }, { key: "governador", name: "Governador", count: 22, ...share(0.11, 0.12) }],
    form: [{ key: "quote", label: "Aspas", n: 200, ...share(0.1, 0.08) }, { key: "number", label: "Números", n: 200, ...share(0.31, 0.27) }],
    tone: [{ key: "prefeito", name: "Prefeito", n: 12, negativo: 7, neutro: 4, positivo: 1, incerto: 0, peers_n: 40, peers_negative_share: 0.25 },
      { key: "governador", name: "Governador", n: 9, negativo: 2, neutro: 6, positivo: 1, incerto: 0, peers_n: 30, peers_negative_share: 0.2 }],
    exclusivity: share(0.12, 0.1) } };
}
export async function getOutletBias() {
  return { error: null, data: {
    outlet: { id: 3, name: "Gazeta Norte", group: "nacional", language: "pt-BR" },
    range: { start: iso(7 * D), end: iso(0), label: "7 dias", generated_at: iso(0) },
    peers: { group: "nacional", count: 5, min_outlets_for_omission: 4 },
    omissions: { eligible_stories: 64, covered: 52, missed: 12, omission_rate: 0.1875, average_rate: 0.22, min_outlets: 4,
      by_topic: [{ topic: "esportes", label: "Esportes", eligible: 8, missed: 4, omission_rate: 0.5 }, { topic: "politica", label: "Política", eligible: 30, missed: 5, omission_rate: 0.167 },
        { topic: "economia", label: "Economia", eligible: 6, missed: 2, omission_rate: 0.33 }],
      blind_spots: [{ story_id: 4, title: "Vale Verde FC vence a final e é campeão estadual", topic: "esportes", outlets_count: 4, outlets: ["Rádio Serra", "Diário da Capital", "Correio do Sul", "Tribuna Central"], first_published_at: iso(2 * D) },
        { story_id: 7, title: "Porto de Santa Alva bate recorde de cargas no trimestre", topic: "economia", outlets_count: 4, outlets: ["Diário da Capital", "Tribuna Central", "Harbor Post"], first_published_at: iso(D) }] },
    delay: { stories: 52, median_minutes: 74, first_share: 0.21, average_median_minutes: 55, enough: true, tolerance_minutes: 10 },
    vocabulary: { enough: true, docs_outlet: 62, docs_others: 410, min_docs: 25, stories: 62, comparison_outlets: 4, language: "pt-BR",
      uses_more: [{ term: "impõe", z: 3.4, docs_outlet: 21, outlet_share: 0.34, others_share: 0.15 }, { term: "polêmica", z: 2.5, docs_outlet: 9, outlet_share: 0.15, others_share: 0.05 }],
      uses_less: [{ term: "prefeitura", z: -2.8, docs_outlet: 6, outlet_share: 0.1, others_share: 0.28 }] },
    edits: { articles: 210, edited: 9, edited_share: 0.043, average_edited_share: 0.03, meaning_flagged: 2, rewritten: 4, declared: 3, declared_share: 0.33,
      peers_articles: 800, peers_edited: 24,
      examples: [{ article_id: 7, url: "https://exemplo.invalid/a", original_headline: "Prefeitura anuncia pacote de R$ 10 milhões para escolas",
                   new_headline: "Prefeitura anuncia pacote de R$ 12 milhões para escolas", kind: "possivel_sentido", observed_at: iso(H), declared: false },
                 { article_id: 8, url: "https://exemplo.invalid/b", original_headline: "Secretário confirma demissão", new_headline: "Secretário não confirma demissão e diz que fica",
                   kind: "possivel_sentido", observed_at: iso(2 * H), declared: true }] } } };
}

// ----------------------------------------------------------------- checagem
export async function getArticle() { return null; }
const ev = (id: number, source_type: string, relationship: string, title: string, passage: string, extra: object = {}) => ({
  id, provider: source_type === "official_data" ? "bcb_sgs" : "press", source_type, source_url: "https://exemplo.invalid/" + id, source_title: title,
  relevant_passage: passage, relationship, verification_status: "retrieved_by_system", published_at: iso(D), retrieved_at: iso(2 * M), data: extra });
const fc = (id: number, assessment: string, label: string, explanation: string, method: string, evidence: object[], limitations: string[], review = "pending_review") => ({
  id, assessment, assessment_label: label, explanation, limitations, method, model: method === "press" ? "qwen2.5:7b" : null,
  prompt_version: method === "press" ? "press-stance-v2" : "rules-v1", review_status: review, reviewed_at: null, review_note: null, created_at: iso(2 * M), supersedes_id: null, evidence });
const PRESS_LIM = ["Só jornais como fonte: veículos podem repetir a mesma informação ou o mesmo erro.", "Só título e resumo das notícias foram lidos, não a matéria inteira."];
export async function getInvestigation() {
  return { error: null, data: {
    id: 12, input_type: "text", status: "done", error: null, created_at: iso(3 * M), finished_at: iso(2 * M), article: null,
    input_text: "A prefeitura de Vale Verde reajustou a tarifa de ônibus em 10%. A deputada Marina Costa é a favor da PEC 12. A inflação de 2025 foi de 4,5%. O governador vai zerar a tarifa no ano que vem.",
    extraction: { method: "llm", model: "qwen2.5:7b", problems: [] },
    claims: [
      { id: 31, text: "A prefeitura de Vale Verde reajustou a tarifa de ônibus em 10%.", quote: "A prefeitura de Vale Verde reajustou a tarifa de ônibus em 10%", type: "numero", article_id: null,
        parsed: null, history: [],
        current: fc(41, "provavelmente_verdadeiro", "Provavelmente verdadeiro", "Com base só na imprensa monitorada (não há dado oficial nem checagem publicada sobre isso). 2 veículos (Jornal do Vale e Rádio Serra) noticiam algo que confirma a afirmação, e nenhum monitorado a contradiz. Exemplo, Jornal do Vale: “reajusta tarifa de ônibus em 10%”. É um indício, não uma prova.", "press",
          [ev(1, "press", "supports", "Jornal do Vale: Prefeitura de Vale Verde reajusta tarifa de ônibus em 10%", "A passagem sobe de R$ 4,00 para R$ 4,40 a partir de segunda.", { stance_quote: "reajusta tarifa de ônibus em 10%" }),
           ev(2, "press", "supports", "Rádio Serra: Tarifa de ônibus em Vale Verde sobe 10% e chega a R$ 4,40", "O reajuste foi publicado no diário oficial do município.", { stance_quote: "sobe 10% e chega a R$ 4,40" }),
           ev(3, "press", "context", "Gazeta Norte: Vale Verde inaugura novo terminal rodoviário", "A obra custou R$ 12 milhões.")], PRESS_LIM) },
      { id: 32, text: "A deputada Marina Costa é a favor da PEC 12.", quote: "A deputada Marina Costa é a favor da PEC 12", type: "fato", article_id: null, parsed: null, history: [],
        current: fc(42, "sem_evidencia", "Sem evidência", "Com base só na imprensa monitorada (não há dado oficial nem checagem publicada sobre isso). Só Gazeta Norte traz algo que confirma a afirmação. É preciso pelo menos 2 veículos diferentes para indicar um lado.", "press",
          [ev(4, "press", "supports", "Gazeta Norte: Deputada Marina Costa declara apoio à PEC 12", "Ela afirmou que votará pela aprovação.", { stance_quote: "declara apoio à PEC 12" })], PRESS_LIM) },
      { id: 33, text: "A inflação de 2025 foi de 4,5%.", quote: "A inflação de 2025 foi de 4,5%", type: "numero", article_id: null, history: [],
        parsed: { indicator: "ipca", indicator_label: "Inflação (IPCA)", value: 4.5, decimals: 1, unit: "%", period_label: "2025", checkable: true, problems: [] },
        current: fc(43, "impreciso", "Impreciso", "A afirmação diz 4,5% para Inflação (IPCA), 2025. Segundo a série 13522 do Banco Central (IPCA acumulado em 12 meses (%)), o valor foi 4,26% em 01/12/2025. O número afirmado está perto do oficial, mas fora do arredondamento: a afirmação é imprecisa.", "rules",
          [ev(5, "official_data", "contradicts", "DEMONSTRAÇÃO (valor ilustrativo) · Banco Central, SGS 13522", "Série 13522 (IPCA acumulado em 12 meses (%)): 4,26% em 01/12/2025.")],
          ["Checagens já publicadas por agências não foram consultadas (sem FACTCHECK_API_KEY).", "A checagem compara só o número; não avalia contexto, causa ou responsabilidade pelo resultado."]) },
      { id: 34, text: "O governador vai zerar a tarifa no ano que vem.", quote: "O governador vai zerar a tarifa no ano que vem", type: "previsao", article_id: null, parsed: null, history: [],
        current: fc(44, "nao_checavel", "Não checável", "A frase é uma previsão, não uma afirmação de fato que possa ser checada.", "none", [], []) },
    ] } };
}
export async function getInvestigations() {
  return [
    { id: 12, input_type: "text", status: "done", error: null, created_at: iso(3 * M), input_text: "A prefeitura de Vale Verde reajustou a tarifa de ônibus em 10%. A deputada Marina Costa…",
      claims: [{ claim_id: 31, text: "A prefeitura reajustou a tarifa em 10%", assessment: "provavelmente_verdadeiro", review_status: "pending_review" },
               { claim_id: 33, text: "A inflação de 2025 foi de 4,5%", assessment: "impreciso", review_status: "pending_review" },
               { claim_id: 32, text: "Marina Costa é a favor da PEC 12", assessment: "sem_evidencia", review_status: "approved" }] },
    { id: 10, input_type: "text", status: "done", error: null, created_at: iso(90 * M), input_text: "O desemprego em Pedra Alta é de 5%.",
      claims: [{ claim_id: 20, text: "O desemprego em Pedra Alta é de 5%.", assessment: "provavelmente_falso", review_status: "pending_review" }] },
  ];
}
