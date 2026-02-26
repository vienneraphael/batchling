"""
Mocks asynchronous HTTP requests.
For recognized URLs from supported providers, delegate requests to the active batcher.
For unknown URLs, call the original method.
Hooks are installed globally but batch mode is activated through a context var.
The context var is set by the `batchify` function upon calling.
"""

import contextvars
import json
import logging
import typing as t
from urllib.parse import urlparse

import aiohttp
import httpx
from aiohttp.client_reqrep import RequestInfo
from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL

from batchling.core import Batcher
from batchling.logging import log_debug
from batchling.providers import get_provider_for_batch_request
from batchling.providers.base import BaseProvider

log = logging.getLogger(name=__name__)


# ContextVar to hold the active Batcher for the current Task
active_batcher: contextvars.ContextVar = contextvars.ContextVar("active_batcher", default=None)

# Original method storage to avoid infinite recursion
_BASE_HTTPX_ASYNC_SEND = httpx.AsyncClient.send
_original_httpx_async_send: t.Callable[..., t.Awaitable[httpx.Response]] | None = None
_BASE_AIOHTTP_REQUEST = aiohttp.ClientSession._request
_original_aiohttp_request: t.Callable[..., t.Awaitable[t.Any]] | None = None
_hooks_installed = False


class _BatchedAiohttpResponse(aiohttp.ClientResponse):
    """
    Lightweight aiohttp-compatible response wrapper for batched results.
    """

    def __init__(
        self,
        *,
        method: str,
        url: str,
        request_headers: dict[str, str] | None,
        status: int,
        reason: str,
        headers: dict[str, str],
        body: bytes,
    ) -> None:
        request_url = URL(url)
        request_headers_map = CIMultiDictProxy(CIMultiDict(request_headers or {}))
        request_info = RequestInfo(
            url=request_url,
            method=method,
            headers=request_headers_map,
            real_url=request_url,
        )

        self._cache: dict[str, t.Any] = {}
        self._url = request_url
        self._real_url = request_url
        self._method = method
        self._request_info = request_info
        self._history = tuple()
        self.status = status
        self.reason = reason
        headers_map = CIMultiDict(headers)
        self._headers = CIMultiDictProxy(headers_map)
        self._raw_headers = tuple(
            (key.encode(encoding="utf-8"), value.encode(encoding="utf-8"))
            for key, value in headers_map.items()
        )
        self._body = body

    async def text(self, encoding: str | None = None, errors: str = "strict") -> str:
        """
        Decode response bytes into text.
        """
        del errors
        decode_encoding = encoding or "utf-8"
        body = self._body or b""
        return body.decode(encoding=decode_encoding)

    async def json(
        self,
        encoding: str | None = None,
        loads: t.Callable[[str], t.Any] = json.loads,
        content_type: str | None = "application/json",
    ) -> t.Any:
        """
        Decode response body into JSON.
        """
        del content_type
        text_body = await self.text(encoding=encoding)
        return loads(text_body)

    async def read(self) -> bytes:
        """
        Return response body bytes.
        """
        return self._body or b""

    @classmethod
    def from_httpx_response(
        cls,
        *,
        response: httpx.Response,
        method: str,
        url: str,
        request_headers: dict[str, str] | None,
    ) -> "_BatchedAiohttpResponse":
        """
        Build wrapper from an httpx response.
        """
        return cls(
            method=method,
            url=url,
            request_headers=request_headers,
            status=response.status_code,
            reason=response.reason_phrase,
            headers=dict(response.headers),
            body=response.content,
        )


def _extract_body_and_headers_from_request(
    request: httpx.Request,
) -> tuple[dict[str, str], t.Any]:
    """
    Extract headers and body from an httpx request.

    Parameters
    ----------
    request : httpx.Request
        Request instance to extract data from.

    Returns
    -------
    tuple[dict[str, str], typing.Any]
        Request headers and body.
    """
    headers = _normalize_httpx_headers(headers=request.headers)
    body: t.Any = None
    try:
        content = request.content
    except httpx.RequestNotRead:
        request.read()
        content = request.content
    if content:
        body = content
    return headers, body


def _normalize_httpx_headers(*, headers: httpx.Headers) -> dict[str, str]:
    """
    Normalize httpx headers into a plain dictionary.

    Parameters
    ----------
    headers : httpx.Headers
        Incoming headers.

    Returns
    -------
    dict[str, str]
        Normalized header mapping.
    """
    return {
        _decode_header_value(value=key).lower(): _decode_header_value(value=value)
        for key, value in headers.raw
    }


def _normalize_aiohttp_headers(*, headers: t.Any) -> dict[str, str]:
    """
    Normalize aiohttp request headers into a lowercase dictionary.
    """
    if headers is None:
        return {}
    if not hasattr(headers, "items"):
        return {}
    return {
        str(object=key).lower(): _decode_header_value(value=value) for key, value in headers.items()
    }


def _decode_header_value(*, value: bytes | str) -> str:
    """
    Decode header values into strings.

    Parameters
    ----------
    value : bytes | str
        Header value.

    Returns
    -------
    str
        Decoded header value.
    """
    if isinstance(value, bytes):
        return value.decode(encoding="latin1")
    return str(object=value)


def _ensure_response_request(
    response: httpx.Response,
    *,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """
    Ensure the response has an associated request attached.

    Parameters
    ----------
    response : httpx.Response
        Response object to update.
    method : str
        HTTP method for the synthetic request.
    url : str
        URL for the synthetic request.
    headers : dict[str, str] | None, optional
        Headers for the synthetic request.

    Returns
    -------
    httpx.Response
        Response with a request attached.
    """
    # httpx.Response.request property raises if unset; assign via private attr.
    if getattr(response, "_request", None) is None:
        response._request = httpx.Request(method=method, url=url, headers=headers)
    return response


def _extract_aiohttp_body(*, kwargs: dict[str, t.Any]) -> bytes | None:
    """
    Convert aiohttp request kwargs into raw body bytes for queueing.
    """
    if kwargs.get("json") is not None:
        return json.dumps(obj=kwargs["json"]).encode(encoding="utf-8")

    raw_data = kwargs.get("data")
    if raw_data is None:
        return None
    if isinstance(raw_data, bytes):
        return raw_data
    if isinstance(raw_data, str):
        return raw_data.encode(encoding="utf-8")
    if isinstance(raw_data, bytearray):
        return bytes(raw_data)
    return None


def _maybe_route_to_batcher(
    *,
    method: str,
    url: str,
    headers: dict[str, str] | None,
    body: t.Any,
    client_type: str,
) -> tuple[Batcher, BaseProvider, dict[str, t.Any]] | None:
    """
    Resolve the active batcher and provider for a request.

    Parameters
    ----------
    method : str
        HTTP method.
    url : str
        Request URL.
    headers : dict[str, str] | None
        Request headers.
    body : typing.Any
        Request body.

    Returns
    -------
    tuple[Batcher, BaseProvider, dict[str, typing.Any]] | None
        Routing data if batching is active, otherwise ``None``.
    """
    batcher = active_batcher.get()
    parsed = urlparse(url=url)
    hostname = (parsed.hostname or "").lower()
    path = parsed.path or "/"
    provider = get_provider_for_batch_request(method=method, hostname=hostname, path=path)
    if batcher is None or provider is None:
        if batcher is None and provider is None:
            reason = "no active batcher and no provider match"
        elif batcher is None:
            reason = "no active batcher"
        else:
            reason = "provider not matched"
        log_debug(
            logger=log,
            event="Request not routed to batcher",
            reason=reason,
            hostname=hostname,
            path=path,
        )
        return None

    return (
        batcher,
        provider,
        {
            "client_type": client_type,
            "method": method,
            "url": hostname,
            "endpoint": path,
            "headers": headers,
            "body": body,
        },
    )


async def _httpx_async_send_hook(self, request: httpx.Request, **kwargs: t.Any) -> httpx.Response:
    """
    Intercept ``httpx.AsyncClient.send`` to route requests into the batcher.

    Parameters
    ----------
    self : httpx.AsyncClient
        HTTPX client instance.
    request : httpx.Request
        Request to send.
    **kwargs : typing.Any
        Extra parameters forwarded to the original send method.

    Returns
    -------
    httpx.Response
        Response from the batcher or underlying HTTPX transport.
    """
    url_str = str(object=request.url)
    headers, body = _extract_body_and_headers_from_request(request=request)
    request_headers = _normalize_httpx_headers(headers=request.headers)
    headers = {**request_headers, **headers}
    if headers.get("x-batchling-internal") == "1":
        return await _BASE_HTTPX_ASYNC_SEND(self, request, **kwargs)

    routed = _maybe_route_to_batcher(
        method=request.method,
        url=url_str,
        headers=headers,
        body=body,
        client_type="httpx",
    )
    if routed is not None:
        batcher, provider, submit_kwargs = routed
        response = await batcher.submit(provider=provider, **submit_kwargs)
        if isinstance(response, httpx.Response):
            return _ensure_response_request(
                response=response,
                method=request.method,
                url=url_str,
                headers=headers,
            )
        return response

    if _original_httpx_async_send is None:
        raise RuntimeError("HTTPX async send hooks have not been installed")

    if _original_httpx_async_send is _httpx_async_send_hook:
        return await _BASE_HTTPX_ASYNC_SEND(self, request, **kwargs)

    return await _original_httpx_async_send(self, request, **kwargs)


async def _aiohttp_async_request_hook(
    self: t.Any,
    method: str,
    str_or_url: t.Any,
    **kwargs: t.Any,
) -> t.Any:
    """
    Intercept ``aiohttp.ClientSession._request`` to route requests into the batcher.
    """
    url_str = str(object=str_or_url)
    headers = _normalize_aiohttp_headers(headers=kwargs.get("headers"))
    body = _extract_aiohttp_body(kwargs=kwargs)

    # Keep interception narrow: only route JSON/bytes request bodies.
    if headers.get("x-batchling-internal") == "1":
        return await _BASE_AIOHTTP_REQUEST(self, method, str_or_url, **kwargs)

    routed = _maybe_route_to_batcher(
        method=method,
        url=url_str,
        headers=headers,
        body=body,
        client_type="aiohttp",
    )
    if routed is not None:
        batcher, provider, submit_kwargs = routed
        response = await batcher.submit(provider=provider, **submit_kwargs)
        if isinstance(response, httpx.Response):
            return _BatchedAiohttpResponse.from_httpx_response(
                response=response,
                method=method,
                url=url_str,
                request_headers=headers,
            )
        return response

    if _original_aiohttp_request is None:
        raise RuntimeError("aiohttp request hooks have not been installed")

    if _original_aiohttp_request is _aiohttp_async_request_hook:
        return await _BASE_AIOHTTP_REQUEST(self, method, str_or_url, **kwargs)

    return await _original_aiohttp_request(self, method, str_or_url, **kwargs)


def install_hooks():
    """
    Install global hooks for supported libraries.

    Notes
    -----
    This function is idempotent and supports ``httpx`` and ``aiohttp``.
    """
    global _original_httpx_async_send
    global _original_aiohttp_request
    global _hooks_installed

    if _hooks_installed:
        return
    if httpx.AsyncClient.send is _httpx_async_send_hook:
        if _original_httpx_async_send is None:
            _original_httpx_async_send = _BASE_HTTPX_ASYNC_SEND
        _hooks_installed = True
        return

    # Store the original request methods
    if httpx.AsyncClient.send is _httpx_async_send_hook:
        _original_httpx_async_send = _BASE_HTTPX_ASYNC_SEND
    else:
        _original_httpx_async_send = t.cast(
            typ=t.Callable[..., t.Awaitable[httpx.Response]],
            val=httpx.AsyncClient.send,
        )
    # Patch httpx clients with our hooks
    httpx.AsyncClient.send = t.cast(typ=t.Any, val=_httpx_async_send_hook)

    if aiohttp.ClientSession._request is _aiohttp_async_request_hook:
        if _original_aiohttp_request is None:
            _original_aiohttp_request = _BASE_AIOHTTP_REQUEST
    else:
        _original_aiohttp_request = t.cast(
            typ=t.Callable[..., t.Awaitable[t.Any]],
            val=aiohttp.ClientSession._request,
        )
        aiohttp.ClientSession._request = t.cast(
            typ=t.Any,
            val=_aiohttp_async_request_hook,
        )

    _hooks_installed = True
