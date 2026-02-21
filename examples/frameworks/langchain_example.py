#!/usr/bin/env python3
import asyncio

from dotenv import load_dotenv
from langchain.agents import create_agent

from batchling import batchify

load_dotenv()


async def build_tasks() -> list:
    """Build LangChain requests."""
    agent = create_agent(
        model="openai:gpt-4.1-mini",
    )
    return [
        agent.ainvoke(
            input={
                "messages": [
                    {"role": "user", "content": "What is the best French painter?"},
                ]
            }
        ),
        agent.ainvoke(
            input={
                "messages": [
                    {"role": "user", "content": "Where does 'hello world' come from?"},
                ]
            }
        ),
    ]


async def main() -> None:
    """Run the LangChain example."""
    tasks = await build_tasks()
    responses = await asyncio.gather(*tasks)
    print(responses)


async def run_with_batchify() -> None:
    """Run `main` inside `batchify` for direct script execution."""
    async with batchify():
        await main()


if __name__ == "__main__":
    asyncio.run(run_with_batchify())
