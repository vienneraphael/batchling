import pytest
from dotenv import load_dotenv
from openai import NOT_GIVEN, DefaultHttpxClient
from pydantic import BaseModel

from batchling.batch_utils import (
    CapturingTransport,
    batch_create_chat_completion,
    replace_placeholders,
)

load_dotenv(override=True)


class MockBaseModel(BaseModel):
    name: str


@pytest.fixture
def messages():
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]


@pytest.fixture
def placeholder_messages():
    return [
        {"role": "system", "content": "You are a helpful {name}."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "{greeting}, how are you?"},
                {"type": "text", "text": "My name is {name}."},
            ],
        },
        {"role": "assistant", "content": "Really? Mine is {name} too!"},
        {"role": "user", "content": "That is awesome, {name}!"},
    ]


@pytest.fixture
def placeholder_dict():
    return {"name": "John", "greeting": "Hello"}


def test_request_capture():
    capturing_transport = CapturingTransport()
    custom_http_client = DefaultHttpxClient(transport=capturing_transport)
    with pytest.raises(
        Exception, match="Aborted request in CapturingTransport to capture payload."
    ):
        custom_http_client.request("GET", "https://www.google.com")
        assert capturing_transport.captured_request is not None


@pytest.mark.parametrize("response_format", [NOT_GIVEN, MockBaseModel])
def test_single_completion(messages, response_format):
    batch_request = batch_create_chat_completion(
        custom_id="test", messages=messages, model="gpt-4o-mini", response_format=response_format
    )
    assert batch_request is not None


def test_placeholders_filling(placeholder_messages, placeholder_dict):
    filled_messages = replace_placeholders(placeholder_messages, placeholder_dict)
    assert filled_messages == [
        {"role": "system", "content": "You are a helpful {name}."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Hello, how are you?"},
                {"type": "text", "text": "My name is John."},
            ],
        },
        {"role": "assistant", "content": "Really? Mine is {name} too!"},
        {"role": "user", "content": "That is awesome, John!"},
    ]
