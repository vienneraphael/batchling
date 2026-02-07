"""
Mocks asynchronous HTTP requests.
For recognized URLs from supported providers, delegate requests to the active batcher.
For unknown URLs, call the original method.
Hooks are installed globally but batch mode is activated through a context var.
The context var is set by the `batchify` function upon calling.
"""

import contextvars
import json
from typing import Any

import httpx
import structlog

log = structlog.get_logger(__name__)

# ContextVar to hold the active Batcher for the current Task
active_batcher: contextvars.ContextVar = contextvars.ContextVar("active_batcher", default=None)

# Global flag to control request flow
allow_requests: bool = True

# Original method storage to avoid infinite recursion
_original_httpx_request = None
_hooks_installed = False


async def _httpx_hook(self, method: str, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
    """
    The replacement for httpx.AsyncClient.request.
    Intercepts requests, prints details, and conditionally allows or blocks them.
    """
    # Log request details
    url_str = str(url)
    headers = kwargs.get("headers", {})
    content = kwargs.get("content")
    json_data = kwargs.get("json")
    data = kwargs.get("data")
    
    # Prepare log context
    log_context = {
        "method": method,
        "url": url_str,
    }
    
    if headers:
        log_context["headers"] = dict(headers)
    
    # Try to extract body content for logging
    body_str = None
    if json_data is not None:
        try:
            body_str = json.dumps(json_data, indent=2)
        except Exception:
            body_str = str(json_data)
    elif content is not None:
        try:
            if isinstance(content, (str, bytes)):
                body_str = content[:200] if len(str(content)) > 200 else str(content)
            else:
                body_str = str(content)
        except Exception:
            body_str = "<binary or non-serializable content>"
    elif data is not None:
        body_str = str(data)[:200] if len(str(data)) > 200 else str(data)
    
    if body_str:
        log_context["body"] = body_str
    
    log.info("httpx request intercepted", **log_context)
    
    # Check if requests are allowed
    if not allow_requests:
        log.warning("Request blocked by allow_requests flag", method=method, url=url_str)
        # Return a mock response
        return httpx.Response(
            status_code=200,
            text="",
        )
    
    # Call the original method
    return await _original_httpx_request(self, method, url, **kwargs)


def install_hooks():
    """
    Idempotent function to install global hooks on supported libraries.
    Currently supports: httpx
    """
    global _original_httpx_request, _hooks_installed
    
    if _hooks_installed:
        return
    
    # Store the original request method
    _original_httpx_request = httpx.AsyncClient.request
    
    # Patch httpx.AsyncClient.request with our hook
    httpx.AsyncClient.request = _httpx_hook
    
    _hooks_installed = True
