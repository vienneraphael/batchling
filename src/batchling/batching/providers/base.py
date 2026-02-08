from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urlparse

import httpx


class BaseProvider(ABC):
    """
    Standard interface for mapping HTTP requests to/from provider Batch APIs.

    Providers implement:
    - matches_url: identify URLs that belong to the provider
    - from_batch_result: parse a JSONL result line back into an httpx.Response
    """

    name: str = "base"
    hostnames: tuple[str, ...] = ()
    path_prefixes: tuple[str, ...] = ()

    def matches_url(self, url: str) -> bool:
        """Return True if the URL belongs to this provider."""
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        path = parsed.path or ""

        host_ok = True
        if self.hostnames:
            host_ok = hostname.endswith(self.hostnames)

        path_ok = True
        if self.path_prefixes:
            path_ok = path.startswith(self.path_prefixes)

        return host_ok and path_ok

    @abstractmethod
    def from_batch_result(self, result_item: dict[str, Any]) -> httpx.Response:
        """Convert provider's Batch result JSON back to httpx.Response."""

    def normalize_url(self, url: str) -> str:
        """
        Normalize a request URL into the format expected by the provider's
        batch API. The default is the full URL string. Providers can override.
        """
        return url
