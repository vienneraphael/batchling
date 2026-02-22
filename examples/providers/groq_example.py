import asyncio
import os

from dotenv import load_dotenv
from groq import AsyncGroq

from batchling import batchify

load_dotenv()


async def build_tasks() -> list:
    """Build Groq requests."""
    client = AsyncGroq(api_key=os.getenv(key="GROQ_API_KEY"))
    questions = [
        "Who is the best French painter? Answer in one short sentence.",
        "What is the capital of France?",
    ]
    return [
        client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=question,
        )
        for question in questions
    ]


async def main() -> None:
    """Run the Groq example."""
    tasks = await build_tasks()
    responses = await asyncio.gather(*tasks)
    print(responses)


async def run_with_batchify() -> None:
    """Run `main` inside `batchify` for direct script execution."""
    async with batchify():
        await main()


if __name__ == "__main__":
    asyncio.run(run_with_batchify())
