"""Worker de jobs em background (RQ + Redis).

Filas:
- "default": coleta, processamento, enquadramento e resumos (jobs longos, em lote).
- "checks": checagens pedidas pelo usuário. Têm worker próprio para não esperar atrás
  de um job de 7 minutos na IA local.

Uso: python -m app.worker [fila ...]   (padrão: default)
"""

import sys

from redis import Redis
from rq import Queue, Worker

from app.config import get_settings


def ping() -> str:
    return "pong"


def main() -> None:
    conn = Redis.from_url(get_settings().redis_url)
    names = sys.argv[1:] or ["default"]
    Worker([Queue(n, connection=conn) for n in names], connection=conn).work()


if __name__ == "__main__":
    main()
