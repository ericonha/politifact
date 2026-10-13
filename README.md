# PolitiFact BR

Plataforma pessoal para acompanhar como os veículos brasileiros cobrem as histórias do dia e, nas fases finais, checar afirmações de políticos com evidências rastreáveis.

O plano completo está no documento de arquitetura (fases 1 a 7). Este repositório está na **fase 4: painel de cobertura** (com seções temáticas).

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
    tasks.py       jobs do worker (coleta e agrupamento, com lock no Redis)
    scheduler.py   agenda a coleta periódica
    worker.py      worker de jobs (RQ)
  alembic/         migrações
  tests/
frontend/
  app/             páginas (histórias, cobertura, comparar, notícias, revisão, coletas, veículos)
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

## Próximos passos

1. Montar o conjunto de teste (cerca de 100 notícias) e ajustar o limiar de junção.
2. Conferir as seções com dados reais e ajustar as regras de `app/topics.py`.
3. Fase 5: análise de veículos e de enquadramento das notícias.
