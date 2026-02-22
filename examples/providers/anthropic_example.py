import asyncio
import os

from anthropic import AsyncAnthropic
from dotenv import load_dotenv

from batchling import batchify

load_dotenv()


async def build_tasks() -> list:
    """Build Anthropic requests."""
    client = AsyncAnthropic(api_key=os.getenv(key="ANTHROPIC_API_KEY"))
    questions = [
        "Who is the best French painter? Answer in one short sentence.",
        "What is the capital of France?",
    ]
    return [
        client.messages.create(
            max_tokens=1024,
            messages=question,
            model="claude-haiku-4-5",
        )
        for question in questions
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
