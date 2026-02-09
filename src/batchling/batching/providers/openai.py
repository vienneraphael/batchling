from __future__ import annotations

import json
import typing as t
from urllib.parse import urlparse

import httpx

from batchling.batching.providers.base import BaseProvider


class OpenAIProvider(BaseProvider):
    """Provider adapter for OpenAI's HTTP and Batch APIs."""

    name = "openai"
    hostnames = ("api.openai.com",)
    path_prefixes = ("/v1/",)

    def matches_url(self, url: str) -> bool:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        if hostname:
            return hostname.lower().endswith(self.hostnames) and parsed.path.startswith(
                self.path_prefixes
            )
        return parsed.path.startswith(self.path_prefixes)

    def from_batch_result(self, result_item: dict[str, t.Any]) -> httpx.Response:
        response = result_item.get("response")
        error = result_item.get("error")

        if response:
            status_code = int(response.get("status_code", 200))
            headers = dict(response.get("headers") or {})
            body = response.get("body")
        else:
            status_code = int(error.get("status_code", 500)) if error else 500
            headers = {}
            body = error or {"error": "Missing response"}

        content, content_headers = self._encode_body(body)
        headers.update(content_headers)

        return httpx.Response(
            status_code=status_code,
            headers=headers,
            content=content,
        )

    def normalize_url(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            if parsed.query:
                return f"{parsed.path}?{parsed.query}"
            return parsed.path
        return url

    def _encode_body(self, body: t.Any) -> tuple[bytes, dict[str, str]]:
        if body is None:
            return b"", {}
        if isinstance(body, (dict, list)):
            return json.dumps(body).encode("utf-8"), {"content-type": "application/json"}
        if isinstance(body, str):
            return body.encode("utf-8"), {"content-type": "text/plain"}
        if isinstance(body, (bytes, bytearray)):
            return bytes(body), {}
        return json.dumps(body).encode("utf-8"), {"content-type": "application/json"}
