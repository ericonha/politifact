"""Embeddings locais via Ollama (opcional).

Sem Ollama, o agrupamento continua funcionando só com léxico + entidades,
com qualidade menor. Para ativar no Mac:

    brew install ollama
    ollama serve            # ou abra o app Ollama
    ollama pull bge-m3      # modelo multilíngue, bom em português (~1,2 GB)

Os containers falam com o Ollama do Mac por host.docker.internal:11434.
"""

import json
import logging
import urllib.error
import urllib.request
from typing import Protocol

from app.config import get_settings

log = logging.getLogger(__name__)


class EmbeddingError(RuntimeError):
    pass


class Embedder(Protocol):
    model: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OllamaEmbedder:
    def __init__(self, url: str, model: str, timeout: float = 120.0) -> None:
        self.url = url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        body = json.dumps({"model": self.model, "input": texts}).encode()
        req = urllib.request.Request(
            f"{self.url}/api/embed",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:300]
            raise EmbeddingError(f"Ollama respondeu {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise EmbeddingError(f"Ollama inacessível em {self.url}: {exc}") from exc

        vectors = data.get("embeddings")
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise EmbeddingError("resposta do Ollama sem 'embeddings' no formato esperado")
        return vectors


def get_embedder() -> Embedder | None:
    s = get_settings()
    if not s.embeddings_enabled:
        return None
    return OllamaEmbedder(s.embeddings_url, s.embeddings_model)


def article_text(headline: str, summary: str | None) -> str:
    return f"{headline}\n{summary or ''}".strip()


if __name__ == "__main__":
    # Diagnóstico: docker compose exec api python -m app.clustering.embeddings
    emb = get_embedder()
    if emb is None:
        print("Embeddings desativados (EMBEDDINGS_ENABLED=false).")
    else:
        try:
            (v,) = emb.embed(["Teste de conexão com o Ollama"])
            print(f"OK: modelo {emb.model}, {len(v)} dimensões.")
        except EmbeddingError as e:
            print(f"Falhou: {e}")
