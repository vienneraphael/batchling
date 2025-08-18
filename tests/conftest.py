import pytest


@pytest.fixture(autouse=True)
def test_set_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
