"""Fase 5: análise de enquadramento das manchetes.

observable.py: características que dá para conferir lendo a manchete (regras, sem IA).
llm.py:        interpretação por um modelo local, sempre com evidência literal validada.
compare.py:    o que muda entre as manchetes da mesma história.
pipeline.py:   grava as análises no banco (nunca sobrescreve: cada versão é uma linha).

Limite importante: o sistema guarda só título e resumo do feed, então a análise
é da manchete e do resumo, não da matéria inteira.
"""
