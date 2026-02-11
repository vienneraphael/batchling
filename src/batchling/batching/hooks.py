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

import httpx
import structlog

from batchling.batching.providers import get_provider_for_batch_request

log = structlog.get_logger(__name__)

# ContextVar to hold the active Batcher for the current Task
active_batcher: contextvars.ContextVar = contextvars.ContextVar("active_batcher", default=None)

# Original method storage to avoid infinite recursion
_BASE_HTTPX_ASYNC_SEND = httpx.AsyncClient.send
_original_httpx_async_send: t.Callable[..., t.Awaitable[httpx.Response]] | None = None
_hooks_installed = False


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
    """
    Emit structured logs for an intercepted HTTPX request.

    Parameters
    ----------
    method : str
        HTTP method.
    url : str
        Request URL.
    headers : dict[str, str] | None
        Request headers.
    json_data : typing.Any, optional
        JSON payload.
    content : typing.Any, optional
        Raw content payload.
    data : typing.Any, optional
        Form data payload.
    body : typing.Any, optional
        Generic body payload.
    """
    log_context: dict[str, t.Any] = {
        "method": method,
        "url": url,
    }

    if headers:
        log_context["headers"] = headers

    body_str = _format_httpx_body(
        json_data=json_data,
        content=content,
        data=data,
        body=body,
    )
    if body_str:
        log_context["body"] = body_str

    log.info(event="httpx request intercepted", **log_context)


def _format_httpx_body(
    *,
    json_data: t.Any = None,
    content: t.Any = None,
    data: t.Any = None,
    body: t.Any = None,
) -> str | None:
    """
    Format request payload for structured logging.

    Parameters
    ----------
    json_data : typing.Any, optional
        JSON payload.
    content : typing.Any, optional
        Raw content payload.
    data : typing.Any, optional
        Form data payload.
    body : typing.Any, optional
        Generic body payload.

    Returns
    -------
    str | None
        Truncated string representation of the payload.
    """
    if json_data is not None:
        return _safe_json_dump(value=json_data)
    if content is not None:
        return _safe_repr(value=content)
    if data is not None:
        return _truncate(text=str(object=data))
    if body is not None:
        return _safe_repr(value=body)
    return None


def _safe_json_dump(*, value: t.Any) -> str:
    """
    Safely serialize JSON payloads for logging.

    Parameters
    ----------
    value : typing.Any
        Value to serialize.

    Returns
    -------
    str
        Serialized payload string.
    """
    try:
        return json.dumps(obj=value, indent=2)
    except Exception:
        return str(object=value)


def _safe_repr(*, value: t.Any) -> str:
    """
    Build a safe string representation of payloads for logging.

    Parameters
    ----------
    value : typing.Any
        Value to represent.

    Returns
    -------
    str
        Truncated string representation.
    """
    try:
        if isinstance(value, (str, bytes)):
            return _truncate(text=str(object=value))
        return str(object=value)
    except Exception:
        return "<binary or non-serializable content>"


def _truncate(*, text: str, limit: int = 200) -> str:
    """
    Truncate a string for logging.

    Parameters
    ----------
    text : str
        Input string.
    limit : int, optional
        Maximum length.

    Returns
    -------
    str
        Truncated string.
    """
    if len(text) > limit:
        return text[:limit]
    return text


def _maybe_route_to_batcher(
    *,
    method: str,
    url: str,
    headers: dict[str, str] | None,
    body: t.Any,
):
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
    provider = get_provider_for_batch_request(method=method, url=url)
    if batcher is None or provider is None:
        if batcher is None and provider is None:
            log.debug(
                event="httpx request not routed",
                reason="no active batcher and no provider match",
                url=url,
            )
        elif batcher is None:
            log.debug(
                event="httpx request not routed",
                reason="no active batcher",
                url=url,
            )
        else:
            log.debug(
                event="httpx request not routed",
                reason="provider not matched",
                url=url,
            )
        return None

    return (
        batcher,
        provider,
        {
            "client_type": "httpx",
            "method": method,
            "url": url,
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
    if headers:
        headers = {**request_headers, **headers}
    else:
        headers = request_headers

    if headers.get("x-batchling-internal") == "1":
        return await _BASE_HTTPX_ASYNC_SEND(self, request, **kwargs)

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


def install_hooks():
    """
    Install global hooks for supported libraries.

    Notes
    -----
    This function is idempotent and currently supports ``httpx``.
    """
    global _original_httpx_async_send
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

    _hooks_installed = True
