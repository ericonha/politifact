"""Fase 6: checagem de fatos.

Fluxo de uma investigação:
  1. extract.py  separa o texto em afirmações (LLM com citação literal validada,
                 ou regras quando o LLM não está disponível);
  2. parse.py    lê cada afirmação por regras: indicador, valor, período;
  3. sources/    busca evidências: dados oficiais (Banco Central, SGS), checagens
                 já publicadas (opcional, Google Fact Check Tools) e o arquivo de
                 notícias coletadas (só como contexto);
  4. verdict.py  decide: com dado oficial, por regra determinística; com checagem
                 publicada, LLM restrito e validado; sem prova, "sem evidência";
  5. pipeline.py grava tudo (versões nunca são sobrescritas) e deixa a checagem
                 aguardando revisão humana.

A imprensa nunca é usada como prova: mostra contexto, não decide veredito.
"""
