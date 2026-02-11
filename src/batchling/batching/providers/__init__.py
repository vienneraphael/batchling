from __future__ import annotations

import importlib
import inspect
import typing as t
from pathlib import Path

from batchling.batching.providers.base import BaseProvider

__all__ = [
    "BaseProvider",
    "PROVIDERS",
    "get_provider_for_batch_request",
]


def _discover_provider_module_names() -> list[str]:
    """
    Discover provider module names from files in this package.

    Returns
    -------
    list[str]
        Sorted module names excluding package and base modules.
    """
    package_dir = Path(__file__).resolve().parent
    module_names = [
        file_path.stem
        for file_path in package_dir.glob("*.py")
        if file_path.name not in {"__init__.py", "base.py"}
    ]
    return sorted(module_names)


def _discover_provider_classes() -> list[type[BaseProvider]]:
    """
    Discover provider adapter classes from provider modules.

    Returns
    -------
    list[type[BaseProvider]]
        Concrete ``BaseProvider`` subclasses found in provider modules.
    """
    provider_classes: list[type[BaseProvider]] = []
    for module_name in _discover_provider_module_names():
        module = importlib.import_module(name=f"{__name__}.{module_name}")
        for attr in vars(module).values():
            if not inspect.isclass(attr):
                continue
            if not issubclass(attr, BaseProvider) or attr is BaseProvider:
                continue
            if inspect.isabstract(attr):
                continue
            if attr.__module__ != module.__name__:
                continue
            provider_classes.append(attr)
    return provider_classes


def _load_providers() -> list[BaseProvider]:
    """
    Instantiate providers discovered in this package.

    Returns
    -------
    list[BaseProvider]
        Provider instances in deterministic module order.
    """
    return [provider_cls() for provider_cls in _discover_provider_classes()]


def _build_provider_indexes(
    *, providers: t.Sequence[BaseProvider]
) -> dict[str, list[BaseProvider]]:
    """
    Build a hostname index for fast provider lookup.

    Parameters
    ----------
    providers : typing.Sequence[BaseProvider]
        Provider instances to index.

    Returns
    -------
    dict[str, list[BaseProvider]]
        Hostname index.
    """
    hostname_index: dict[str, list[BaseProvider]] = {}
    for provider in providers:
        for hostname in provider.hostnames:
            hostname_index.setdefault(hostname.lower(), []).append(provider)
    return hostname_index


PROVIDERS: list[BaseProvider] = _load_providers()
_HOSTNAME_INDEX = _build_provider_indexes(providers=PROVIDERS)


def get_provider_for_batch_request(*, method: str, hostname: str, path: str) -> BaseProvider | None:
    """
    Resolve a provider only when the request is explicitly batchable.

    Parameters
    ----------
    method : str
        HTTP method.
    hostname : str
        Request hostname to match.
    path : str
        Request URL to match.

    Returns
    -------
    BaseProvider | None
        Provider instance if this request is batchable, otherwise ``None``.
    """
    candidates = _HOSTNAME_INDEX.get(hostname, []) if hostname else []

    if candidates:
        for provider in candidates:
            if provider.is_batchable_request(method=method, hostname=hostname, path=path):
                return provider
        return None
