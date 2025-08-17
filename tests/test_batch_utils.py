import pytest

from batchling.batch_utils import replace_placeholders


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
