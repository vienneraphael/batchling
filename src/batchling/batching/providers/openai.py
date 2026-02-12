from __future__ import annotations

import structlog

from batchling.batching.providers.base import (
    BaseProvider,
)

log = structlog.get_logger(__name__)


class OpenAIProvider(BaseProvider):
    """Provider adapter for OpenAI's HTTP and Batch APIs."""

    name = "openai"
    hostnames = ("api.openai.com",)
    batchable_endpoints = (
        "/v1/responses",
        "/v1/chat/completions",
        "/v1/embeddings",
        "/v1/completions",
        "/v1/moderations",
        "/v1/images/generations",
        "/v1/images/edits",
    )
    terminal_states = {"completed", "failed", "cancelled", "expired"}
