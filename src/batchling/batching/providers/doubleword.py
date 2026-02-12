from __future__ import annotations

from batchling.batching.providers.openai import OpenAIProvider


class DoublewordProvider(OpenAIProvider):
    """Provider adapter for Doubleword's OpenAI-compatible Batch API."""

    name = "doubleword"
    hostnames = ("api.doubleword.ai",)
    batchable_endpoints = ("/v1/chat/completions",)
