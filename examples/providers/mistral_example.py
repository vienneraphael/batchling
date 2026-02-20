#!/usr/bin/env python3
import asyncio
import os
import typing as t

from dotenv import load_dotenv
from mistralai import Mistral

from batchling import batchify

load_dotenv()


async def build_tasks() -> list[t.Awaitable[t.Any]]:
    """Build Mistral requests.

    Returns
    -------
    list[Awaitable[Any]]
        Concurrent requests for batchling execution.
    """
    client = Mistral(api_key=os.getenv(key="MISTRAL_API_KEY"))
    messages: list[dict[str, str]] = [
        {
            "content": "Who is the best French painter? Answer in one short sentence.",
            "role": "user",
        },
    ]
    return [
        client.chat.complete_async(
            model="mistral-medium-2505",
            messages=t.cast(t.Any, messages),
            stream=False,
            response_format={"type": "text"},
        ),
        client.chat.complete_async(
            model="mistral-small-2506",
            messages=t.cast(t.Any, messages),
            stream=False,
            response_format={"type": "text"},
        ),
    ]


async def main() -> None:
    """Run the Mistral example."""
    tasks = await build_tasks()
    responses = await asyncio.gather(*tasks)
    print(responses)


async def run_with_batchify() -> None:
    """Run `main` inside `batchify` for direct script execution."""
    async with batchify():
        await main()


if __name__ == "__main__":
    asyncio.run(run_with_batchify())
