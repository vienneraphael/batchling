from __future__ import annotations

import typing as t
from abc import ABC, abstractmethod
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
        """
        Check whether a URL belongs to this provider.

        Parameters
        ----------
        url : str
            Candidate request URL.

        Returns
        -------
        bool
            ``True`` if the URL matches this provider.
        """
        parsed = urlparse(url=url)
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
    def from_batch_result(self, result_item: dict[str, t.Any]) -> httpx.Response:
        """
        Convert a batch result JSON item into an ``httpx.Response``.

        Parameters
        ----------
        result_item : dict[str, typing.Any]
            Provider-specific JSONL result line.

        Returns
        -------
        httpx.Response
            Parsed HTTP response.
        """

    def normalize_url(self, url: str) -> str:
        """
        Normalize a request URL into the format expected by the provider's
        batch API. The default is the full URL string. Providers can override.

        Parameters
        ----------
        url : str
            Original request URL.

        Returns
        -------
        str
            Normalized URL string.
        """
        return url
