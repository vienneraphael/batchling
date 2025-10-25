import pytest

from tests.mocks.providers import (
    setup_anthropic_mocks,
    setup_gemini_mocks,
    setup_groq_mocks,
    setup_mistral_mocks,
    setup_openai_mocks,
    setup_together_mocks,
)


@pytest.fixture(autouse=True)
def test_set_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("TOGETHER_API_KEY", "test-key")


@pytest.fixture(autouse=True)
def mock_providers(respx_mock, request):
    """Autouse dispatcher: install only the current provider's mocks if available.

    Falls back to installing all mocks when provider is not parameterized.
    """
    provider_setups = {
        "openai": setup_openai_mocks,
        "groq": setup_groq_mocks,
        "mistral": setup_mistral_mocks,
        "together": setup_together_mocks,
        "anthropic": setup_anthropic_mocks,
        "gemini": setup_gemini_mocks,
    }

    if hasattr(request, "fixturenames") and "provider" in request.fixturenames:
        current_provider = request.getfixturevalue("provider")
        setup_fn = provider_setups.get(current_provider)
        if setup_fn is not None:
            setup_fn(respx_mock)
        else:
            for fn in provider_setups.values():
                fn(respx_mock)
    else:
        for fn in provider_setups.values():
            fn(respx_mock)

    yield
