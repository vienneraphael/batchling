#!/usr/bin/env python3
import asyncio
import os
import typing as t

from dotenv import load_dotenv
from openai import AsyncOpenAI

from batchling import batchify

load_dotenv()


async def build_tasks() -> list[t.Awaitable[t.Any]]:
    """Build OpenAI requests.

    Returns
    -------
    list[Awaitable[Any]]
        Concurrent requests for batchling execution.
    """
    client = AsyncOpenAI(api_key=os.getenv(key="OPENAI_API_KEY"))
    messages = [
        {
            "content": "Who is the best French painter? Answer in one short sentence.",
            "role": "user",
        },
    ]
    return [
        client.responses.create(
            input=t.cast(t.Any, messages),
            model="gpt-4o-mini",
            stream=False,
        ),
        client.responses.create(
            input=t.cast(t.Any, messages),
            model="gpt-5-nano",
            stream=False,
        ),
    ]


async def main() -> None:
    """Run the OpenAI example."""
    tasks = await build_tasks()
    responses = await asyncio.gather(*tasks)
    print(responses)


async def run_with_batchify() -> None:
    """Run `main` inside `batchify` for direct script execution."""
    async with batchify():
        await main()


if __name__ == "__main__":
    asyncio.run(run_with_batchify())
