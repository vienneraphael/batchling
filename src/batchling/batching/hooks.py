"""
Mocks asynchronous HTTP requests.
For recognized URLs from supported providers, delegate requests to the active batcher.
For unknown URLs, call the original method.
Hooks are installed globally but batch mode is activated through a context var.
The context var is set by the `batchify` function upon calling.
"""

import contextvars
import json
import typing as t
import asyncio
import httpx
import structlog

from batchling.batching.providers import get_provider_for_url

log = structlog.get_logger(__name__)

# ContextVar to hold the active Batcher for the current Task
active_batcher: contextvars.ContextVar = contextvars.ContextVar("active_batcher", default=None)

# Original method storage to avoid infinite recursion
_original_httpx_async_request: t.Callable[..., t.Awaitable[httpx.Response]] | None = None
_original_httpx_async_send: t.Callable[..., t.Awaitable[httpx.Response]] | None = None
_hooks_installed = False


def _extract_body_and_headers_from_request(
    request: httpx.Request,
) -> tuple[dict[str, str], t.Any]:
    headers = dict(request.headers)
    body: t.Any = None
    if request.content:
        body = request.content
    return headers, body


def _ensure_response_request(
    response: httpx.Response,
    *,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    # httpx.Response.request property raises if unset; assign via private attr.
    if getattr(response, "_request", None) is None:
        response._request = httpx.Request(method=method, url=url, headers=headers)
    return response


def _log_httpx_request(
    *,
    method: str,
    url: str,
    headers: dict[str, str] | None,
    json_data: t.Any = None,
    content: t.Any = None,
    data: t.Any = None,
    body: t.Any = None,
) -> None:
    log_context: dict[str, t.Any] = {
        "method": method,
        "url": url,
    }

    if headers:
        log_context["headers"] = dict(headers)

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
    elif body is not None:
        try:
            if isinstance(body, (str, bytes)):
                body_str = body[:200] if len(str(body)) > 200 else str(body)
            else:
                body_str = str(body)
        except Exception:
            body_str = "<binary or non-serializable content>"

    if body_str:
        log_context["body"] = body_str

    log.info("httpx request intercepted", **log_context)


def _maybe_route_to_batcher(
    *,
    method: str,
    url: str,
    headers: dict[str, str] | None,
    body: t.Any,
):
    batcher = active_batcher.get()
    provider = get_provider_for_url(url)
    if batcher is None or provider is None:
        if batcher is None and provider is None:
            log.debug(
                "httpx request not routed",
                reason="no active batcher and no provider match",
                url=url,
            )
        elif batcher is None:
            log.debug(
                "httpx request not routed",
                reason="no active batcher",
                url=url,
            )
        else:
            log.debug(
                "httpx request not routed",
                reason="provider not matched",
                url=url,
            )
        return None

    return batcher, provider, {
        "client_type": "httpx",
        "method": method,
        "url": url,
        "headers": headers,
        "body": body,
    }


async def _httpx_async_request_hook(
    self, method: str, url: str | httpx.URL, **kwargs: t.Any
) -> httpx.Response:
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

    _log_httpx_request(
        method=method,
        url=url_str,
        headers=dict(headers) if headers else None,
        json_data=json_data,
        content=content,
        data=data,
    )

    # If there's an active batcher and the URL is supported, route to batcher
    body = None
    if json_data is not None:
        body = json_data
    elif content is not None:
        body = content
    elif data is not None:
        body = data

    routed = _maybe_route_to_batcher(
        method=method,
        url=url_str,
        headers=dict(headers) if headers else None,
        body=body,
    )
    if routed is not None:
        batcher, _provider, submit_kwargs = routed
        response = await batcher.submit(**submit_kwargs)
        if isinstance(response, httpx.Response):
            return _ensure_response_request(
                response,
                method=method,
                url=url_str,
                headers=dict(headers) if headers else None,
            )
        return response

    # Call the original method
    if _original_httpx_async_request is None:
        raise RuntimeError("HTTPX async request hooks have not been installed")

    return await _original_httpx_async_request(self, method, url, **kwargs)


async def _httpx_async_send_hook(
    self, request: httpx.Request, **kwargs: t.Any
) -> httpx.Response:
    url_str = str(request.url)
    headers, body = _extract_body_and_headers_from_request(request)

    _log_httpx_request(
        method=request.method,
        url=url_str,
        headers=headers,
        body=body,
    )

    routed = _maybe_route_to_batcher(
        method=request.method,
        url=url_str,
        headers=headers,
        body=body,
    )
    if routed is not None:
        batcher, _provider, submit_kwargs = routed
        response = await batcher.submit(**submit_kwargs)
        if isinstance(response, httpx.Response):
            return _ensure_response_request(
                response,
                method=request.method,
                url=url_str,
                headers=headers,
            )
        return response

    if _original_httpx_async_send is None:
        raise RuntimeError("HTTPX async send hooks have not been installed")

    return await _original_httpx_async_send(self, request, **kwargs)


def install_hooks():
    """
    Idempotent function to install global hooks on supported libraries.
    Currently supports: httpx
    """
    global _original_httpx_async_request, _original_httpx_async_send
    global _hooks_installed

    if _hooks_installed:
        return

    # Store the original request methods
    _original_httpx_async_request = t.cast(
        t.Callable[..., t.Awaitable[httpx.Response]],
        httpx.AsyncClient.request,
    )
    _original_httpx_async_send = t.cast(
        t.Callable[..., t.Awaitable[httpx.Response]],
        httpx.AsyncClient.send,
    )
    # Patch httpx clients with our hooks
    httpx.AsyncClient.request = t.cast(t.Any, _httpx_async_request_hook)
    httpx.AsyncClient.send = t.cast(t.Any, _httpx_async_send_hook)

    _hooks_installed = True
