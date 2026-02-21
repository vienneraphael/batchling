import asyncio

from dotenv import load_dotenv
from pydantic_ai import Agent

from batchling import batchify

load_dotenv()


async def build_tasks() -> list:
    """Build pydantic-ai requests."""
    agent = Agent(
        model="openai:gpt-5-nano",
        tools=[],
    )
    questions = [
        "Who is the best French painter? Answer in one short sentence.",
        "What is the capital of France?",
    ]
    return [agent.run(user_prompt=question) for question in questions]


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
