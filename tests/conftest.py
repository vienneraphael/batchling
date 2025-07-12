from unittest.mock import Mock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_client():
    with patch("openai.OpenAI") as mock_client:
        mock_client.return_value = Mock()
        yield mock_client


@pytest.fixture(autouse=True)
def test_set_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
