from unittest.mock import Mock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_client():
    with patch("openai.OpenAI") as mock_client:
        mock_client.return_value = Mock()
        yield mock_client
