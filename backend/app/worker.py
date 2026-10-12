"""Worker de jobs em background (RQ + Redis).

Na fase 1 só existe um job de teste. A coleta de RSS entra na fase 2.
"""

from redis import Redis
from rq import Queue, Worker

from app.config import get_settings


def ping() -> str:
    return "pong"


def main() -> None:
    conn = Redis.from_url(get_settings().redis_url)
    Worker([Queue("default", connection=conn)], connection=conn).work()


if __name__ == "__main__":
    main()
