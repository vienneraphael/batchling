import asyncio
import os

from dotenv import load_dotenv
from together import AsyncTogether

from batchling import batchify

load_dotenv()


async def build_tasks() -> list:
    """Build Together AI requests."""
    client = AsyncTogether(api_key=os.getenv(key="TOGETHER_API_KEY"))
    messages = [
        "Who is the best French painter? Answer in one short sentence.",
    ]
    return [
        client.chat.completions.create(
            model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
            messages=messages,
        ),
        client.chat.completions.create(
            model="google/gemma-3n-E4B-it",
            messages=messages,
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
