from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_client():
    with patch("openai.OpenAI") as OpenAI_cls:
        client = MagicMock(name="openai_client")
        file_obj = MagicMock(name="fake_file", id="test-file-id")
        client.files.create.return_value = file_obj
        batch_obj = MagicMock(name="fake_batch", id="test-batch-id")
        client.batches.create.return_value = batch_obj
        OpenAI_cls.return_value = client

        yield client


@pytest.fixture(autouse=True)
def test_set_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
