# PolitiFact BR

Plataforma pessoal para acompanhar como os veículos brasileiros cobrem as histórias do dia e, nas fases finais, checar afirmações de políticos com evidências rastreáveis.

O plano completo está no documento de arquitetura (fases 1 a 7). Este repositório está na **fase 6: checagem de fatos**.

## Escopo atual

- **Nacionais (13 ativos):** Jovem Pan, CNN Brasil, Agência Brasil, Poder360, Metrópoles, CartaCapital, Gazeta do Povo, Revista Oeste, InfoMoney, g1, Folha de S.Paulo, Veja e UOL. Band desativada (sem RSS público).
- **Internacionais (6):** BBC News Brasil, Bloomberg Línea Brasil, DW Brasil e RFI Brasil (em português); The Economist (seção The Americas) e The Guardian (página Brasil), em inglês, sem tradução.
- Feeds de g1, Folha, Veja, UOL, DW, RFI, Economist e Guardian não puderam ser verificados na configuração; se falharem, o motivo aparece em **Coletas**. A lista completa e as notas estão em `backend/app/seed.py` e na tela **Veículos**.
- Fora: Bloomberg em inglês (robots.txt proíbe coleta), Reuters e AP (sem RSS público), O Globo e Estadão (fora do escopo do MVP), classificação política dos veículos.
- Coleta a cada 30 minutos (`COLLECT_INTERVAL_MINUTES`).
- Tudo roda localmente, com custo próximo de zero.

## Stack

| Componente | Tecnologia |
|---|---|
| Frontend | Next.js + TypeScript |
| API | Python + FastAPI |
| Banco | PostgreSQL 16 + pgvector |
| Fila | Redis + RQ (worker em Python) |
| Ambiente | Docker Compose |

## Como rodar

Pré-requisito: Docker (no Mac, Docker Desktop ou Colima).

```bash
docker compose up --build
```

(O `.env.example` só é necessário se você rodar a API fora do Docker.)

- Frontend: http://localhost:3000
- API: http://localhost:8000/docs
- Health check: http://localhost:8000/api/health

Ao subir, o serviço `migrate` aplica as migrações e cadastra os veículos (ele roda de novo a cada `docker compose up`); só depois a API e o worker começam. Se o banco estiver atrasado em relação ao código, `/api/health` mostra `migration_pending` e os jobs param com uma mensagem explicando o que fazer. O serviço `scheduler` dispara uma coleta logo no início e depois a cada 30 minutos; ao fim de cada coleta, as notícias novas são deduplicadas e agrupadas em histórias.

Quando mudar dependências (`pyproject.toml` ou `package.json`), suba com `--build`.

### Embeddings com Ollama (opcional, recomendado)

O agrupamento funciona sem Ollama (por palavras e nomes próprios), mas fica melhor com embeddings:

```bash
brew install ollama
ollama serve          # ou abra o app Ollama
ollama pull bge-m3    # modelo multilíngue, ~1,2 GB
docker compose exec api python -m app.clustering.embeddings   # testa a conexão
```

Para desligar: `EMBEDDINGS_ENABLED=false` no ambiente da API e do worker.

### Análise de enquadramento com IA local (fase 5, opcional)

A comparação de manchetes funciona sem IA (regras sobre o texto). A "leitura da IA" usa um modelo local no mesmo Ollama:

```bash
ollama pull qwen2.5:7b      # ~4,7 GB; troque em LLM_MODEL se quiser outro
docker compose exec api python -m app.framing.pipeline          # roda agora (regras + IA)
docker compose exec api python -m app.framing.pipeline --no-llm # só regras
```

Roda sozinha depois de cada agrupamento, só para histórias com 2+ veículos nas últimas 72 h, até 30 notícias por vez (`LLM_ARTICLES_PER_RUN`). Para desligar: `LLM_ENABLED=false`.

### Checagem de fatos (fase 6)

Na tela **Checagem**, cole uma afirmação (ou clique em "Checar" numa notícia). O sistema:

1. separa o texto em afirmações (IA local, com o trecho original conferido literalmente; sem IA, frase a frase);
2. lê cada afirmação por regras: indicador, valor e período;
3. busca evidências:
   - **dados oficiais do Banco Central** (API pública do SGS, sem chave) para Selic, inflação (IPCA do mês ou em 12 meses), desemprego, dólar e PIB;
   - **checagens já publicadas** por agências (Google Fact Check Tools), só se houver chave;
   - **notícias já coletadas**, só como contexto;
4. decide o veredito (verdadeiro, impreciso, falso, sem evidência suficiente ou não checável) e deixa a checagem aguardando revisão humana.

Para consultar checagens publicadas, crie uma chave da API "Fact Check Tools" no Google Cloud e ponha no `.env` da raiz:

```
FACTCHECK_API_KEY=sua-chave
```

Pela API: `POST /api/claims` com `{"text": "..."}`, `{"article_id": 123}` ou `{"url": "link de notícia já coletada"}`; depois `GET /api/investigations/{id}`.

### Diferenças de pauta e de texto por veículo

Na página de cada veículo (`/veiculos/<id>`), abaixo do perfil, quatro medidas objetivas, sem IA decidindo o que é viés e sem rótulo de esquerda ou direita. Endpoint: `GET /api/outlets/{id}/bias?window=7d|30d`.

- **O que deixou de cobrir:** entre histórias cobertas por 4 ou mais veículos do grupo (nacional ou internacional), a parte que o veículo não cobriu, por seção, e as histórias mais cobertas que ele ignorou. Não conta histórias anteriores à matéria mais antiga que temos do veículo.
- **Quando publica:** atraso em relação ao primeiro veículo do grupo na mesma história (mediana; parte das vezes em que publicou até 10 min depois do primeiro).
- **Palavras que escolhe:** razão de chances log da presença de cada palavra por matéria, com prior informativo, comparando o veículo com os outros do mesmo idioma **nas mesmas histórias** (cada história pesa igual dos dois lados). Exige 25 matérias de cada lado e 3 ocorrências.
- **Edições de manchete:** a coleta agora guarda a versão nova quando uma matéria reaparece no feed com título ou resumo diferente (tabela `article_revisions`; a primeira versão nunca é sobrescrita). Cada mudança é classificada por regras: só resumo, ajuste, reescrita, ou "número ou negação mudou" (sinal para ler as duas versões, não afirma mudança de sentido) e se o texto avisa a correção.

Limites: só vale para o que os feeds RSS mostram, coletado a cada 30 minutos. Edições só são vistas enquanto a matéria continua no feed; um feed que nunca mostra alterações não prova que não houve. Edições só passam a ser registradas depois desta versão; o histórico anterior não existe.

### Avaliações de orientação política dos veículos

O sistema não classifica veículos sozinho. Avaliações entram em `backend/data/outlet_ratings.json`, sempre com avaliador, metodologia e data (instruções dentro do arquivo); o serviço `migrate` carrega a cada `docker compose up`. O arquivo começa vazio.

### Coleta manual

```bash
docker compose exec api python -m app.ingestion.collector   # roda e mostra o resultado no terminal
```

Ou clique em **Coletar agora** na tela Coletas.

### Agrupamento manual

```bash
docker compose exec api python -m app.clustering.pipeline           # agrupa as notícias novas
docker compose exec api python -m app.clustering.pipeline --reset --yes   # apaga TODAS as histórias e reagrupa
```

O `--reset` apaga também as correções feitas na tela Revisão. Use só para testar parâmetros.

### Conjunto de teste do agrupamento

```bash
# 1. exporta as 100 notícias mais recentes para backend/data/gabarito.csv
docker compose exec api python -m app.clustering.evaluate export --n 100 -o data/gabarito.csv
# 2. abra o CSV numa planilha e preencha a coluna "historia" (mesmo rótulo = mesma história)
# 3. mede o agrupamento e testa vários limiares
docker compose exec api python -m app.clustering.evaluate run data/gabarito.csv --sweep
```

O resultado mostra precisão (baixa = junta histórias diferentes), recall (baixo = separa a mesma história), F1, e quantos pares foram juntados ou separados por engano.

### Seções (Política, Economia, Esportes...)

Cada notícia recebe uma seção, nesta ordem: categoria declarada no feed, caminho da URL (`/politica/...`) ou palavras-chave do título e do resumo. A origem fica em `articles.topic_source`. A seção de uma história é a mais comum entre as suas notícias. As regras estão em `backend/app/topics.py`; depois de mudá-las:

```bash
docker compose exec api python -m app.topics_backfill --all
```

### Mudar feeds ou ativar um veículo

Edite `backend/app/seed.py` e rode `docker compose up -d` (o serviço `migrate` roda o seed de novo e atualiza os veículos existentes).

### Testes

Com o stack rodando:

```bash
docker compose exec api pytest
```

## Estrutura

```
backend/
  app/
    main.py        endpoints da API
    models.py      esquema do banco (seção 9 do plano)
    seed.py        veículos monitorados e seus feeds
    ingestion/     normalização, parser RSS/Atom, download e coletor
    clustering/    deduplicação, embeddings, agrupamento, avaliação
    coverage/      métricas de cobertura (períodos, linha do tempo, lacunas)
    topics.py      classificação em seções
    framing/       enquadramento: regras observáveis, comparação, LLM local com validação
    ratings.py     avaliações atribuídas de veículos (lidas de data/outlet_ratings.json)
    factcheck/     checagem: extração, leitura do número, fontes (BCB, checagens, imprensa), veredito
    tasks.py       jobs do worker (coleta e agrupamento, com lock no Redis)
    scheduler.py   agenda a coleta periódica
    worker.py      worker de jobs (RQ); `python -m app.worker checks` atende só a fila das checagens
  alembic/         migrações
  tests/
frontend/
  app/             páginas (histórias, resumo, checagem, cobertura, comparar, notícias, revisão, coletas, veículos)
  components/      gráficos em SVG (sem biblioteca externa) e abas de seção
  lib/api.ts       cliente da API
docker-compose.yml
```

## Decisões já tomadas

- Datas separadas para publicação, atualização, descoberta e coleta. A janela de tempo usa sempre a data de **publicação**.
- Contagens são "entre os veículos monitorados", nunca cobertura total da mídia.
- Classificação política fica em tabela própria e sempre atribuída a um avaliador; a tabela existe, mas não é usada no MVP.
- Fact-checks são versionados (`supersedes_id`); nada é sobrescrito.
- Embeddings ficam em `articles.embedding` (pgvector, sem dimensão fixa para permitir trocar de modelo).
- A coleta guarda só título, link, datas e um resumo de até 500 caracteres. O texto completo das matérias não é armazenado (licença).
- O coletor respeita o `robots.txt` de cada site e se identifica com um User-Agent próprio. Se o robots.txt não permitir, a coleta falha e o motivo aparece na tela Coletas.
- Na coleta, a mesma URL canônica (sem parâmetros de rastreamento como `utm_*`) nunca é gravada duas vezes.
- Notícias sem data de publicação no feed são guardadas, mas não entram nas janelas de tempo.
- Duplicatas: mesmo título + resumo (`exact`) ou, no mesmo veículo, título quase idêntico em até 48 h (`near_headline`). Duplicata do mesmo veículo não conta na cobertura; republicação de outro veículo entra na história com o método `syndicated`.
- Agrupamento incremental: cada notícia nova é comparada com as histórias ativas nas últimas 48 h. Acima do limiar de junção, entra na história; abaixo do limiar de nova história, abre uma história nova; no meio, vai para a tela **Revisão** e não conta na cobertura até alguém decidir.
- Toda decisão (automática ou manual) fica em `clustering_decisions`. Correções manuais criam uma nova decisão e apontam a antiga para ela; nada é apagado.
- Os limiares em `app/clustering/core.py` são palpites iniciais. Ajuste com o conjunto de teste.

- Painel de cobertura (`/cobertura`): períodos de 24 h, 3 dias, 7 dias ou datas escolhidas (horário de SP), filtro por seção, linha do tempo por veículo, volume, alcance das histórias, histórias exclusivas, seções por veículo e uma seção de limitações (lacunas de coleta, feeds que podem ter "passado" notícias, notícias sem data, duplicatas, pendências de revisão).
- "Tempo com coleta" considera lacuna qualquer intervalo maior que 2× o intervalo da coleta sem coleta bem-sucedida. Com o Mac desligado, a lacuna aparece.
- Diferença de cobertura entre veículos nunca é apresentada como prova de omissão ou motivação.
- Com muitos veículos, os gráficos usam uma cor só e a identidade vem do rótulo; a linha do tempo é um gráfico pequeno por veículo, todos na mesma escala. Cores categóricas só aparecem para até 3 séries (comparação de histórias), com paleta validada para daltonismo.
- O painel filtra por grupo (nacionais / internacionais): veículos estrangeiros publicam pouco sobre o Brasil e pareceriam "ignorar" histórias numa comparação direta.
- Notícias em inglês só se juntam às histórias em português com embeddings multilíngues (Ollama + `bge-m3`).

- Enquadramento (fase 5): a página de cada história mostra as manchetes lado a lado, quem cada veículo pôs em destaque, quem não aparece em algumas manchetes, falas atribuídas, perguntas e termos de impacto. Tudo isso vem de regras sobre o título e o resumo (o sistema não guarda a matéria inteira).
- A leitura da IA nunca é aceita sem conferência: todo tom diferente de neutro precisa de um trecho copiado literalmente do texto; senão vira "incerto". Atores e vozes que não aparecem no texto são removidos. O texto das notícias é tratado como dado, nunca como instrução ao modelo.
- Análises são append-only: mudar regra, prompt ou modelo cria linhas novas em `article_analyses`, com versão e modelo.
- Orientação do veículo (avaliação atribuída) e enquadramento da notícia ficam separados: um não é deduzido do outro.
- Layout de portal: cabeçalho com a marca e o menu; à esquerda, a barra lateral com o título da página, a última coleta, o período, as seções, o grupo e os veículos (com favoritos); à direita, o conteúdo. A página Histórias é uma capa: a história de maior alcance em destaque, duas em seguida e as demais em grade.
- **Relevância** (`app/relevance.py`, 0 a 100): 60% alcance (veículos que cobriram), 25% volume (no máximo 3 notícias por veículo, escala log) e 15% recência (meia-vida de 8 h). A seção não entra na nota. Histórias são ordenadas por ela (`/api/stories?order=relevance|recent|reach`).
- **Resumo por seção** (página Resumo): a IA local lê as 8 histórias mais relevantes de cada seção nas últimas 24 h e escreve um panorama e até 5 pontos. Cada ponto cita as histórias de onde saiu; pontos com história inexistente, número ou nome próprio que não aparece no texto das histórias citadas são descartados. Só regera uma seção quando as histórias mudam; cada geração fica guardada (`briefings`). Rodar na mão: `docker compose exec api python -m app.briefing.pipeline --force`.
- **Perfil de cada veículo** (`/veiculos/<id>`): seções, atores nas manchetes, forma das manchetes, tom lido pela IA (só leituras validadas, com n) e exclusividade, sempre ao lado da média simples dos outros veículos do mesmo grupo. Não é rótulo de orientação política.
- **Checagem (fase 6)**: com dado oficial, o veredito é por regra, sem IA: o número afirmado bate com a série do Banco Central dentro do arredondamento que ele usa ("4,3%" cobre 4,25 a 4,35; "4%" cobre 3,5 a 4,5) → verdadeiro; perto (até 10% de diferença) → impreciso; longe → falso; sem dado no período → sem evidência suficiente. A explicação é um texto fixo com os números da série, então a IA não tem como inventar um valor.
- A série da meta Selic (SGS 432) já traz datas futuras, até a próxima reunião do Copom: "valor atual" ignora datas depois de hoje.
- Sem dado oficial, a IA só pode decidir a partir de checagens já publicadas, citando-as; explicação com número ou nome que não está nas evidências é descartada. Sem dado oficial nem checagem publicada, a imprensa monitorada pode indicar um lado, mas só como **"provavelmente verdadeiro/falso"** (decisão do dono do projeto, que substituiu a regra anterior de "imprensa nunca decide"): a IA só classifica cada notícia (apoia / contradiz / irrelevante) copiando um trecho literal do título ou resumo; uma regra exige pelo menos 2 veículos diferentes de um lado e nenhum do outro; a explicação é um texto fixo, sem IA. Se há divergência ou só um veículo, o resultado é "sem evidência suficiente". "Verdadeiro" e "falso" continuam exclusivos de dado oficial e checagens publicadas.
- Fora da checagem automática (aparecem como limitação): afirmações de direção ("o desemprego caiu"), comparação ("o maior desde…"), inflação acumulada no ano, mais de um indicador ou mais de um ano na mesma frase, ano ainda não terminado.
- Rechecar cria uma nova versão (`fact_checks.supersedes_id`) com as próprias evidências e datas de busca; a revisão humana (aprovar/rejeitar, com nota) vale só para a versão atual.
- Favoritos ficam no banco (`outlets.favorite`), valem em todas as telas e o seed nunca os altera. "Só favoritos" filtra histórias, notícias e o painel de cobertura.

## Próximos passos

1. Montar o conjunto de teste (cerca de 100 notícias) e ajustar o limiar de junção.
2. Conferir as seções e a lista de termos de impacto com dados reais.
3. Checagem: conjunto de teste com afirmações já checadas por agências, para medir acertos e abstenções.
4. Checagem: mais fontes oficiais (IBGE/SIDRA, Portal da Transparência, Câmara) e afirmações de direção ("caiu", "subiu").
5. Fase 7: avaliação automática, backups e alertas.
