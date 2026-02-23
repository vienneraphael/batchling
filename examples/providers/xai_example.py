import asyncio
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI

from batchling import batchify

load_dotenv()


async def build_tasks() -> list:
    """Build OpenAI requests."""
    client = AsyncOpenAI(api_key=os.getenv(key="XAI_API_KEY"), base_url="https://api.x.ai/v1")
    questions = [
        "Who is the best French painter? Answer in one short sentence.",
        "What is the capital of France?",
    ]
    return [
        client.chat.completions.create(
            messages=[{"role": "user", "content": question}], model="grok-4-1-fast-non-reasoning"
        )
        for question in questions
    ]


async def main() -> None:
    """Run the OpenAI example."""
    tasks = await build_tasks()
    responses = await asyncio.gather(*tasks)
    for response in responses:
        print(response)


async def run_with_batchify() -> None:
    """Run `main` inside `batchify` for direct script execution."""
    async with batchify():
        await main()


if __name__ == "__main__":
    asyncio.run(run_with_batchify())
