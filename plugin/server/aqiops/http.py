"""Tiny stdlib HTTP helper with a clear error when a sandbox or firewall blocks the host."""

from __future__ import annotations

import urllib.error
import urllib.request

from . import __version__

UA = f"aqi-ops/{__version__} (+https://github.com/bosons14/ncr-aqi-tracker)"


class FetchError(RuntimeError):
    def __init__(self, url: str, reason: str):
        super().__init__(f"{reason} while fetching {url}")
        self.url = url
        self.reason = reason


def get(url: str, timeout: float = 45) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        raise FetchError(url, f"HTTP {e.code}: {body}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise FetchError(url, f"network error ({getattr(e, 'reason', e)})") from None
