"""Agendador simples: enfileira a coleta a cada N minutos.

Roda como processo separado (serviço `scheduler` no docker compose).
O lock em app.tasks impede duas coletas simultâneas, então reiniciar o
agendador ou disparar uma coleta manual ao mesmo tempo é seguro.
"""

import logging
import signal
import time

from redis import Redis
from rq import Queue

from app.config import get_settings

log = logging.getLogger("scheduler")
_running = True


def _stop(*_: object) -> None:
    global _running
    _running = False


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    queue = Queue("default", connection=Redis.from_url(settings.redis_url))
    interval = settings.collect_interval_minutes * 60

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    next_run = time.monotonic()
    while _running:
        if time.monotonic() >= next_run:
            job = queue.enqueue("app.tasks.collect_all_job", job_timeout=20 * 60)
            log.info("coleta enfileirada (job %s); próxima em %d min", job.id, interval // 60)
            next_run = time.monotonic() + interval
        time.sleep(1)


if __name__ == "__main__":
    main()
