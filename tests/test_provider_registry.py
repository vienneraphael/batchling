"""Tests for provider auto-discovery and registry lookup."""

from pathlib import Path

import batchling.batching.providers as providers_module
from batchling.batching.providers import (
    BaseProvider,
    get_provider_for_batch_request,
)
from batchling.batching.providers.gemini import GeminiProvider


def test_provider_registry_auto_discovers_modules() -> None:
    """
    Ensure provider instances are discovered from provider module files.

    Returns
    -------
    None
        This test asserts registry state.
    """
    provider_dir = Path(providers_module.__file__).resolve().parent
    file_stems = {
        file_path.stem
        for file_path in provider_dir.glob("*.py")
        if file_path.name not in {"__init__.py", "base.py"}
    }
    discovered_modules = {
        provider.__class__.__module__.split(sep=".")[-1] for provider in providers_module.PROVIDERS
    }

    assert discovered_modules
    assert discovered_modules.issubset(file_stems)
    assert "openai" in discovered_modules


def test_provider_registry_contains_only_concrete_provider_instances() -> None:
    """
    Ensure the provider registry contains concrete provider adapter instances.

    Returns
    -------
    None
        This test asserts registry instance types.
    """
    assert providers_module.PROVIDERS
    assert all(isinstance(provider, BaseProvider) for provider in providers_module.PROVIDERS)
    assert all(provider.__class__ is not BaseProvider for provider in providers_module.PROVIDERS)


def test_provider_lookup_still_resolves_openai() -> None:
    """
    Ensure hostname lookup still resolves the OpenAI provider adapter.

    Returns
    -------
    None
        This test asserts hostname-to-provider mapping.
    """
    provider = get_provider_for_batch_request(
        hostname="api.openai.com",
        path="/v1/chat/completions",
        method="POST",
    )
    assert provider is not None
    assert provider.name == "openai"


def test_provider_lookup_resolves_doubleword() -> None:
    """
    Ensure hostname lookup resolves the Doubleword provider adapter.

    Returns
    -------
    None
        This test asserts hostname-to-provider mapping.
    """
    provider = get_provider_for_batch_request(
        hostname="api.doubleword.ai",
        path="/v1/chat/completions",
        method="POST",
    )
    assert provider is not None
    assert provider.name == "doubleword"


def test_batchable_lookup_requires_post_method() -> None:
    """
    Ensure batchable lookup only routes POST requests.

    Returns
    -------
    None
        This test asserts method gating for batchable requests.
    """
    post_provider = get_provider_for_batch_request(
        method="POST",
        hostname="api.openai.com",
        path="/v1/chat/completions",
    )
    assert post_provider is not None
    assert post_provider.name == "openai"

    get_provider = get_provider_for_batch_request(
        method="GET",
        hostname="api.openai.com",
        path="/v1/chat/completions",
    )
    assert get_provider is None


def test_batchable_lookup_requires_configured_endpoint() -> None:
    """
    Ensure batchable lookup only routes configured endpoints.

    Returns
    -------
    None
        This test asserts endpoint gating for batchable requests.
    """
    provider = get_provider_for_batch_request(
        method="POST",
        hostname="api.openai.com",
        path="/v1/doesnotexist",
    )
    assert provider is None


def test_provider_lookup_resolves_gemini_dynamic_model_endpoint() -> None:
    """
    Ensure Gemini dynamic model endpoints are recognized as batchable.

    Returns
    -------
    None
        This test asserts dynamic endpoint matching.
    """
    provider = get_provider_for_batch_request(
        method="POST",
        hostname="generativelanguage.googleapis.com",
        path="/v1beta/models/gemini-3-flash-preview:generateContent",
    )
    assert provider is not None
    assert provider.name == "gemini"


def test_provider_lookup_rejects_non_batchable_gemini_path() -> None:
    """
    Ensure Gemini paths not matching generateContent are not routed.

    Returns
    -------
    None
        This test asserts endpoint gating for Gemini requests.
    """
    provider = get_provider_for_batch_request(
        method="POST",
        hostname="generativelanguage.googleapis.com",
        path="/v1beta/models/gemini-3-flash-preview:batchGenerateContent",
    )
    assert provider is None


def test_base_provider_supports_template_batchable_endpoint_matching() -> None:
    """
    Ensure template placeholders in ``batchable_endpoints`` are matched.

    Returns
    -------
    None
        This test asserts template endpoint matching behavior.
    """
    gemini_provider = GeminiProvider()

    assert gemini_provider.matches_batchable_endpoint(
        path="/v1beta/models/gemini-2.5-flash:generateContent"
    )
    assert not gemini_provider.matches_batchable_endpoint(
        path="/v1beta/models/gemini-2.5-flash:batchGenerateContent"
    )
