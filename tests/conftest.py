import aiohttp
import httpx
import pytest

import batchling.hooks as hooks_module
from batchling.cache import CACHE_PATH_ENV_VAR
from batchling.hooks import active_batcher


@pytest.fixture
def reset_hooks():
    """Reset hook state and restore original httpx client methods."""
    original_async_send = httpx.AsyncClient.send
    original_aiohttp_request = aiohttp.ClientSession._request
    hooks_module._hooks_installed = False
    hooks_module._original_httpx_async_send = None
    hooks_module._original_aiohttp_request = None
    yield
    httpx.AsyncClient.send = original_async_send
    aiohttp.ClientSession._request = original_aiohttp_request
    hooks_module._hooks_installed = False
    hooks_module._original_httpx_async_send = None
    hooks_module._original_aiohttp_request = None


@pytest.fixture
def reset_context():
    """Reset the active_batcher context."""
    try:
        active_batcher.set(None)
    except LookupError:
        pass


@pytest.fixture(autouse=True)
def isolate_cache_path(monkeypatch, tmp_path):
    """Use a dedicated cache file per test."""
    cache_path = tmp_path / "batchling-cache.sqlite3"
    monkeypatch.setenv(CACHE_PATH_ENV_VAR, cache_path.as_posix())
    yield
    try:
        active_batcher.set(None)
    except LookupError:
        pass
