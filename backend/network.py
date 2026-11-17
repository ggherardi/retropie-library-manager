"""Bounded public HTTPS requests with robots rules and per-host pacing."""

import threading
import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from backend.providers import validate_url

USER_AGENT = "RetroPieLibraryManager/0.2 (+https://github.com/ggherardi/retropie-library-manager)"


class PublicHTTP:
    def __init__(self, transport=None):
        self.client = httpx.Client(
            timeout=30,
            follow_redirects=False,
            trust_env=False,
            headers={"User-Agent": USER_AGENT},
            transport=transport,
        )
        self.lock = threading.RLock()
        self.robots: dict[str, tuple[float, RobotFileParser]] = {}
        self.last_request: dict[str, float] = {}

    def close(self):
        self.client.close()

    def check(self, url: str):
        validate_url(url)
        parsed = urlsplit(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        with self.lock:
            cached = self.robots.get(origin)
            if not cached or time.monotonic() - cached[0] > 3600:
                response = self.client.get(f"{origin}/robots.txt")
                if response.status_code == 404:
                    content = "User-agent: *\nAllow: /"
                elif response.status_code == 200:
                    content = response.text
                else:
                    raise ValueError(f"Regole robots non verificabili per {origin} ({response.status_code})")
                robot = RobotFileParser()
                robot.parse(content.splitlines())
                self.robots[origin] = (time.monotonic(), robot)
            robot = self.robots[origin][1]
            if not robot.can_fetch(USER_AGENT, url):
                raise ValueError("Accesso automatico escluso da robots.txt")
            delay = max(0.25, float(robot.crawl_delay(USER_AGENT) or 0))
            remaining = delay - (time.monotonic() - self.last_request.get(origin, 0))
            if remaining > 0:
                time.sleep(remaining)
            self.last_request[origin] = time.monotonic()

    def stream(self, url: str, headers=None):
        self.check(url)
        return self.client.stream("GET", url, headers=headers)

    def read(self, url: str, limit=10_000_000) -> bytes:
        with self.stream(url) as response:
            response.raise_for_status()
            chunks = []
            size = 0
            for chunk in response.iter_bytes(65536):
                size += len(chunk)
                if size > limit:
                    raise ValueError("Risposta del provider troppo grande")
                chunks.append(chunk)
            return b"".join(chunks)
