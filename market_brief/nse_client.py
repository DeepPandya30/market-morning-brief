from __future__ import annotations

import time
from typing import Any

import requests

from .config import NSE_BASE_URL, NSE_REFERERS


class NSEClient:
    def __init__(self, timeout: int = 20, retries: int = 2) -> None:
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
                "Connection": "keep-alive",
                "DNT": "1",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            }
        )
        self._warmed = False

    def warmup(self) -> None:
        if self._warmed:
            return
        warmup_urls = [*NSE_REFERERS, NSE_BASE_URL]
        for url in warmup_urls:
            try:
                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    headers={
                        "Referer": NSE_BASE_URL,
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    },
                )
                if response.status_code < 400:
                    self._warmed = True
                    return
            except requests.RequestException:
                continue
        self._warmed = True

    def get_json(self, url: str, referer: str | None = None) -> Any:
        self.warmup()
        headers = {}
        if referer:
            headers["Referer"] = referer
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = self.session.get(url, timeout=self.timeout, headers=headers)
                if response.status_code in {401, 403, 404} and attempt < self.retries:
                    self._warmed = False
                    self.warmup()
                    time.sleep(0.8)
                    continue
                response.raise_for_status()
                return response.json()
            except Exception as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(0.8)
                    continue
        raise RuntimeError(f"NSE JSON fetch failed for {url}: {last_error}")
