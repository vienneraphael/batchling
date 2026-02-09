from __future__ import annotations

import typing as t
from urllib.parse import urlparse

from batchling.batching.providers.base import BaseProvider
from batchling.batching.providers.openai import OpenAIProvider

PROVIDERS: list[BaseProvider] = [OpenAIProvider()]

__all__ = [
    "BaseProvider",
    "PROVIDERS",
    "get_provider_for_url",
]

_HOSTNAME_INDEX: dict[str, list[BaseProvider]] = {}
_PATH_PREFIX_INDEX: dict[str, list[BaseProvider]] = {}

for provider in PROVIDERS:
    for hostname in provider.hostnames:
        _HOSTNAME_INDEX.setdefault(hostname.lower(), []).append(provider)
    for prefix in provider.path_prefixes:
        _PATH_PREFIX_INDEX.setdefault(prefix, []).append(provider)


def get_provider_for_url(url: str) -> BaseProvider | None:
    """
    Resolve a provider adapter for a request URL.

    Parameters
    ----------
    url : str
        Request URL to match.

    Returns
    -------
    BaseProvider | None
        Provider instance if matched, otherwise ``None``.
    """
    parsed = urlparse(url=url)
    hostname = (parsed.hostname or "").lower()
    path = parsed.path or ""

    candidates: list[BaseProvider] = []
    if hostname:
        candidates.extend(_HOSTNAME_INDEX.get(hostname, []))
    for prefix, providers in _PATH_PREFIX_INDEX.items():
        if path.startswith(prefix):
            candidates.extend(providers)

    if candidates:
        # De-duplicate while preserving order
        seen: set[int] = set()
        unique: list[BaseProvider] = []
        for provider in candidates:
            provider_id = id(provider)
            if provider_id in seen:
                continue
            seen.add(provider_id)
            unique.append(provider)
        for provider in unique:
            if provider.matches_url(url=url):
                return provider
        return None

    return _fallback_match(url=url, providers=PROVIDERS)


def _fallback_match(
    url: str,
    providers: t.Iterable[BaseProvider],
) -> BaseProvider | None:
    """
    Check providers in order when indexes do not produce a match.

    Parameters
    ----------
    url : str
        Request URL to match.
    providers : typing.Iterable[BaseProvider]
        Provider candidates.

    Returns
    -------
    BaseProvider | None
        Provider instance if matched, otherwise ``None``.
    """
    for provider in providers:
        if provider.matches_url(url=url):
            return provider
    return None
