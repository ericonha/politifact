"""Resumo por seção escrito por um LLM local, a partir das histórias mais relevantes.

core.py:     montagem do prompt e validação (pura, testável sem banco nem IA).
pipeline.py: escolhe as histórias, chama o modelo e grava (append-only).
"""
