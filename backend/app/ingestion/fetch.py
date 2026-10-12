"""Download de feeds com retries, timeout e respeito ao robots.txt."""

import logging
import time
import urllib.error
import urllib.request
import urllib.robotparser
from functools import lru_cache
from urllib.parse import urlsplit

log = logging.getLogger(__name__)

USER_AGENT = "PolitiFactBR/0.2 (projeto pessoal; coleta de RSS)"
TIMEOUT_SECONDS = 20
MAX_BYTES = 5 * 1024 * 1024
RETRIES = 3
BACKOFF_SECONDS = 2.0


class FetchError(RuntimeError):
    pass


class DisallowedByRobots(FetchError):
    pass


@lru_cache(maxsize=64)
def _robots_for(origin: str) -> urllib.robotparser.RobotFileParser | None:
    parser = urllib.robotparser.RobotFileParser()
    req = urllib.request.Request(f"{origin}/robots.txt", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            parser.parse(resp.read(MAX_BYTES).decode("utf-8", errors="replace").splitlines())
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            parser.disallow_all = True
        elif 400 <= exc.code < 500:
            parser.allow_all = True  # sem robots.txt: tudo permitido
        else:
            return None
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
    return parser


def allowed_by_robots(url: str) -> bool:
    parts = urlsplit(url)
    parser = _robots_for(f"{parts.scheme}://{parts.netloc}")
    if parser is None:
        # robots.txt inacessível agora: não arrisca, tenta na próxima coleta.
        raise FetchError("robots.txt inacessível")
    return parser.can_fetch(USER_AGENT, url)


def fetch(url: str) -> bytes:
    if not allowed_by_robots(url):
        raise DisallowedByRobots(f"robots.txt não permite {url}")

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
        },
    )
    last_error: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                data = resp.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise FetchError(f"feed maior que {MAX_BYTES} bytes")
            return data
        except urllib.error.HTTPError as exc:
            last_error = exc
            if 400 <= exc.code < 500 and exc.code != 429:
                break  # erro do cliente: repetir não ajuda
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
        if attempt < RETRIES:
            delay = BACKOFF_SECONDS * 2 ** (attempt - 1)
            log.warning("falha ao baixar %s (tentativa %d): %s", url, attempt, last_error)
            time.sleep(delay)
    raise FetchError(f"{url}: {last_error}")
