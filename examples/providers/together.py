#!/usr/bin/env python3
import asyncio
import os
import typing as t

from dotenv import load_dotenv
from together import AsyncTogether

from batchling import batchify

load_dotenv()


async def build_tasks() -> list[t.Awaitable[t.Any]]:
    """Build Together AI requests.

    Returns
    -------
    list[Awaitable[Any]]
        Concurrent requests for batchling execution.
    """
    client = AsyncTogether(api_key=os.getenv(key="TOGETHER_API_KEY"))
    messages = [
        {
            "content": "Who is the best French painter? Answer in one short sentence.",
            "role": "user",
        },
    ]
    return [
        client.chat.completions.create(
            model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
            messages=t.cast(t.Any, messages),
        ),
        client.chat.completions.create(
            model="google/gemma-3n-E4B-it",
            messages=t.cast(t.Any, messages),
        ),
    ]


async def main() -> None:
    """Run the Together AI example."""
    tasks = await build_tasks()
    responses = await asyncio.gather(*tasks)
    print(responses)


async def run_with_batchify() -> None:
    """Run `main` inside `batchify` for direct script execution."""
    async with batchify():
        await main()


if __name__ == "__main__":
    asyncio.run(run_with_batchify())
