# PolitiFact BR

Plataforma pessoal para acompanhar como os veículos brasileiros cobrem as histórias do dia e, nas fases finais, checar afirmações de políticos com evidências rastreáveis.

O plano completo está no documento de arquitetura (fases 1 a 7). Este repositório está na **fase 3: deduplicação e agrupamento**.

## Escopo atual

- Veículos monitorados: Jovem Pan, CNN Brasil e BBC News Brasil.
- Band: desativada por enquanto, porque não tem feed RSS público.
- Fora do MVP: veículos em inglês, O Globo, Estadão e classificação política dos veículos.
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

Ao subir, a API aplica as migrações e cadastra os veículos. O serviço `scheduler` dispara uma coleta logo no início e depois a cada 30 minutos; ao fim de cada coleta, as notícias novas são deduplicadas e agrupadas em histórias.

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

### Mudar feeds ou ativar um veículo

Edite `backend/app/seed.py` e reinicie a API (`docker compose restart api`); o seed atualiza os veículos existentes.

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
    tasks.py       jobs do worker (coleta e agrupamento, com lock no Redis)
    scheduler.py   agenda a coleta periódica
    worker.py      worker de jobs (RQ)
  alembic/         migrações
  tests/
frontend/
  app/             páginas (histórias, notícias, revisão, coletas e veículos)
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

## Próximos passos

1. Montar o conjunto de teste (cerca de 100 notícias) e ajustar o limiar de junção.
2. Fase 4: dashboard de cobertura (linha do tempo, comparação entre veículos, limitações da coleta).
