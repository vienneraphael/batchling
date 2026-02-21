import asyncio
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI

from batchling import batchify

load_dotenv()


async def build_tasks() -> list:
    """Build OpenAI requests."""
    client = AsyncOpenAI(api_key=os.getenv(key="OPENAI_API_KEY"))
    message = "Who is the best French painter? Answer in one short sentence."
    return [
        client.responses.create(
            input=message,
            model="gpt-4o-mini",
        ),
        client.responses.create(
            input=message,
            model="gpt-5-nano",
        ),
    ]


async def main() -> None:
    """Run the OpenAI example."""
    tasks = await build_tasks()
    responses = await asyncio.gather(*tasks)
    for response in responses:
        content = response.output[-1].content  # skip reasoning output, get straight to the answer
        print(f"{response.model} answer: {content[0].text}")


async def run_with_batchify() -> None:
    """Run `main` inside `batchify` for direct script execution."""
    async with batchify():
        await main()


if __name__ == "__main__":
    asyncio.run(run_with_batchify())
