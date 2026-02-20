#!/usr/bin/env python3
import asyncio
import typing as t

from dotenv import load_dotenv
from pydantic_ai import Agent

from batchling import batchify

load_dotenv()


async def build_tasks() -> list[t.Awaitable[t.Any]]:
    """Build pydantic-ai requests.

    Returns
    -------
    list[Awaitable[Any]]
        Concurrent requests for batchling execution.
    """
    agent = Agent(
        model="openai:gpt-5-nano",
        tools=[],
    )
    return [
        agent.run(user_prompt="What is the best French painter?"),
        agent.run(user_prompt="Where does 'hello world' come from?"),
    ]


async def main() -> None:
    """Run the pydantic-ai example."""
    tasks = await build_tasks()
    responses = await asyncio.gather(*tasks)
    print(responses)


async def run_with_batchify() -> None:
    """Run `main` inside `batchify` for direct script execution."""
    async with batchify():
        await main()


if __name__ == "__main__":
    asyncio.run(run_with_batchify())
