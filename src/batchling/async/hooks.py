"""
Mocks asynchronous HTTP requests.
For recognized URLs from supported providers, delegate requests to the active batcher.
For unknown URLs, call the original method.
Hooks are installed globally but batch mode is activated through a context var.
The context var is set by the `batchify` function upon calling.
"""

import contextvars

# ContextVar to hold the active Batcher for the current Task
active_batcher: contextvars.ContextVar = contextvars.ContextVar("active_batcher", default=None)

# Original method storage to avoid infinite recursion
_original_httpx_request = None
_hooks_installed = False


async def _httpx_hook(self, method, url, **kwargs):
    """
    The replacement for httpx.AsyncClient.request.
    Checks if a Batcher is active and if the URL is supported.
    """
    # 1. Get current batcher from ContextVar
    # 2. If batcher matches URL -> delegate to batcher.submit()
    # 3. Else -> call _original_httpx_request()


def install_hooks():
    """
    Idempotent function to install global hooks on supported libraries.
    Currently supports: httpx
    """
