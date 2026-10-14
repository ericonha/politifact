# Avaliação

Mede o que o sistema faz de verdade, em vez de supor. Três conjuntos em `data/` (JSONL, um caso por linha):

| Conjunto | O que mede | Usa modelo? |
|---|---|---|
| `extract.jsonl` (25 textos) | separar afirmações e dar o tipo certo (fato, número, citação, opinião, previsão, pergunta); resistência a ordens plantadas no texto | sim |
| `stance.jsonl` (16 casos, 35 notícias) | classificar cada notícia como apoia/contradiz/irrelevante e o veredito “provável” que sai daí; alcance, período, hipótese, negação, injeção, pares de troca de nomes | sim |
| `official.jsonl` (20 afirmações) | leitura da afirmação + comparação com séries congeladas (**sintéticas**) | não |

## Rodar

```bash
# sem Ollama: linhas de base + dados oficiais
docker compose run --rm api python -m app.evals.run

# comparar modelos (baixe-os antes: ollama pull <modelo>)
docker compose run --rm api python -m app.evals.run --models qwen2.5:7b,llama3.1:8b,gemma2:9b
```

Escreve `results/<data>.json` (tudo, por caso) e `results/latest.md` (tabela). A linha `baseline` é o sistema sem
modelo (regras para extração; “tudo irrelevante” para posição da imprensa).

## Como ler

- Intervalos de Wilson 95%. Com 16–35 casos eles são largos: diferença menor que o intervalo não é evidência.
- **Veredito errado e confiante** é a métrica principal: o sistema disse “provavelmente verdadeiro/falso” quando o
  gabarito não diz esse lado. Um modelo melhor em acerto, mas pior aqui, não serve.
- “Trechos rejeitados” conta citações que o modelo inventou e a validação barrou; “Fallback” conta extrações em que o
  modelo falhou e o sistema caiu para regras.
- Cada resultado guarda a versão dos prompts e um hash dos conjuntos, então comparações entre execuções são rastreáveis.

## Honestidade dos rótulos

Todos os casos têm `"label_status": "proposed"`: os rótulos foram **propostos** junto com o código, não revisados
por quem decide a política do projeto. Antes de citar um número, revise os JSONL (ex.: `s08` e `s12` são casos
debatíveis, marcados na `note`), troque para `"reviewed"` e acrescente casos de notícias reais. Os casos de
posição usam cidades e pessoas fictícias de propósito, para o modelo não responder com o que já sabe.
As séries de `official.jsonl` são sintéticas: testam a lógica de leitura/comparação, não os valores do Banco Central.

## Achado da primeira rodada

`o18` (“O PIB caiu 3,5% em 2020”) falhou: “caiu” não virava valor negativo, e a afirmação contava como divergente
do dado real (−3,3%). Corrigido em `factcheck/parse.py` e coberto em `tests/test_factcheck_parse.py`.
