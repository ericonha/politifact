from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://politifact:politifact@localhost:5432/politifact"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:3000"
    collect_interval_minutes: int = 30  # pedido do usuário: coletar a cada 30 min
    embeddings_enabled: bool = True
    embeddings_url: str = "http://host.docker.internal:11434"
    embeddings_model: str = "bge-m3"
    # LLM local para a análise de enquadramento (fase 5). Usa o mesmo Ollama dos embeddings.
    llm_enabled: bool = True
    llm_model: str = "qwen2.5:7b"
    llm_articles_per_run: int = 30

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
