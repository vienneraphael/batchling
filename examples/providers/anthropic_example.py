#!/usr/bin/env python3
import asyncio
import os
import typing as t

from anthropic import AsyncAnthropic
from dotenv import load_dotenv

from batchling import batchify

load_dotenv()


async def build_tasks() -> list[t.Awaitable[t.Any]]:
    """Build Anthropic requests.

    Returns
    -------
    list[Awaitable[Any]]
        Concurrent requests for batchling execution.
    """
    client = AsyncAnthropic(api_key=os.getenv(key="ANTHROPIC_API_KEY"))
    messages = [
        {
            "content": "Who is the best French painter? Answer in one short sentence.",
            "role": "user",
        },
    ]
    return [
        client.messages.create(
            max_tokens=1024,
            messages=t.cast(t.Any, messages),
            model="claude-haiku-4-5",
        ),
        client.messages.create(
            max_tokens=1024,
            messages=t.cast(t.Any, messages),
            model="claude-3-5-haiku-latest",
        ),
    ]


async def main() -> None:
    """Run the Anthropic example."""
    tasks = await build_tasks()
    responses = await asyncio.gather(*tasks)
    print(responses)


async def run_with_batchify() -> None:
    """Run `main` inside `batchify` for direct script execution."""
    async with batchify():
        await main()


if __name__ == "__main__":
    asyncio.run(run_with_batchify())
