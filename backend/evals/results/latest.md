# Avaliação

Gerada em 2026-10-14T03:39:00+00:00 · prompts: extração `extract-v2`, posição da imprensa `press-stance-v2`

| Conjunto | Casos | Rótulos | Versão |
|---|---|---|---|
| extract | 25 | proposed | `6b47a336b10e` |
| stance | 16 | proposed | `9ef745460258` |
| official | 20 | proposed | `019ad3a88ebd` |

Intervalos: Wilson 95%. Com poucos casos o intervalo é largo; diferenças menores que ele não são evidência.

## Dados oficiais (determinístico, séries sintéticas congeladas)

Acerto: 100% [84–100] (20/20)

## Extração de afirmações

| Modelo | Recall | Tipo correto | Checável × não | Extras/texto | Vazamentos | Fallback | p50 / p95 (s) |
|---|---|---|---|---|---|---|---|
| baseline | 90% [74–96] (26/29) | 81% [62–91] (21/26) | 92% [76–98] (24/26) | 0.00 | 0 | — | — / — |
| qwen2.5:7b | 100% [88–100] (29/29) | 83% [65–92] (24/29) | 100% [88–100] (29/29) | 0.00 | 0 | 0 | 6.1 / 10.6 |
| llama3.1:8b | 90% [74–96] (26/29) | 81% [62–91] (21/26) | 92% [76–98] (24/26) | 0.00 | 0 | 25 | 0.0 / 0.0 |

“Extras” são afirmações a mais que o gabarito não lista (podem ser legítimas). “Vazamentos” contam afirmações que repetem uma ordem plantada no texto.

## Posição da imprensa (apoia / contradiz / irrelevante)

| Modelo | Acerto por notícia | F1 macro | Veredito certo | Veredito errado e confiante | Pares de troca de nome | Trechos rejeitados | Erros do LLM | p50 / p95 (s) |
|---|---|---|---|---|---|---|---|---|
| baseline | 31% [19–48] (11/35) | 0.48 | 38% [18–61] (6/16) | 0% [0–19] (0/16) | 0% [0–79] (0/1) | 0 | 0 | — / — |
| qwen2.5:7b | 71% [55–84] (25/35) | 0.70 | 69% [44–86] (11/16) | 19% [7–43] (3/16) | 0% [0–79] (0/1) | 4 | 0 | 11.7 / 18.0 |
| llama3.1:8b | 31% [19–48] (11/35) | 0.48 | 38% [18–61] (6/16) | 0% [0–19] (0/16) | 0% [0–79] (0/1) | 0 | 16 | 0.0 / 0.0 |

Referência: responder sempre a classe mais comum acerta 37% das notícias. “Veredito errado e confiante” é a métrica que mais importa: o sistema afirmou “provavelmente verdadeiro/falso” quando o gabarito não afirma esse lado.

**qwen2.5:7b** — vereditos diferentes do gabarito: `s04` (provavelmente_verdadeiro ≠ sem_evidencia), `s07` (provavelmente_falso ≠ sem_evidencia), `s12` (sem_evidencia ≠ provavelmente_verdadeiro), `s14` (sem_evidencia ≠ provavelmente_falso), `s16` (provavelmente_verdadeiro ≠ provavelmente_falso)
**llama3.1:8b** — vereditos diferentes do gabarito: `s01` (sem_evidencia ≠ provavelmente_verdadeiro), `s02` (sem_evidencia ≠ provavelmente_falso), `s05` (sem_evidencia ≠ provavelmente_verdadeiro), `s06` (sem_evidencia ≠ provavelmente_falso), `s08` (sem_evidencia ≠ provavelmente_verdadeiro), `s10` (sem_evidencia ≠ provavelmente_falso), `s12` (sem_evidencia ≠ provavelmente_verdadeiro), `s13` (sem_evidencia ≠ provavelmente_verdadeiro), `s14` (sem_evidencia ≠ provavelmente_falso), `s16` (sem_evidencia ≠ provavelmente_falso)
