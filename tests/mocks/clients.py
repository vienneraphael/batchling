"""
Mock client classes for testing batchify and BatchingContext.
"""

import asyncio
import typing as t


class MockClient:
    """Mock client for testing."""

    def __init__(self):
        self.value = 42
        self.attr = "test"

    def sync_method(self, x):
        """Synchronous method."""
        return x * 2

    async def async_method(self, x):
        """Asynchronous method."""
        await asyncio.sleep(delay=0.01)
        return x * 3

    @property
    def nested(self):
        """Nested object."""
        return MockNested()

    def __str__(self):
        return "MockClient"

    def __repr__(self):
        return "<MockClient>"

    def __getattr__(self, name: str) -> t.Any:
        raise AttributeError(name)

    def __setattr__(self, name: str, value: t.Any) -> None:
        object.__setattr__(self, name, value)


class MockNested:
    """Mock nested object."""

    def sync_nested(self, x):
        """Nested synchronous method."""
        return x + 10

    async def async_nested(self, x):
        """Nested asynchronous method."""
        await asyncio.sleep(delay=0.01)
        return x + 20


def sync_function(x):
    """Test synchronous function."""
    return x * 2


async def async_function(x):
    """Test asynchronous function."""
    await asyncio.sleep(delay=0.01)
    return x * 3
