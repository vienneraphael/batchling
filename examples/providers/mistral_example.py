import asyncio
import os

from dotenv import load_dotenv
from mistralai import Mistral

from batchling import batchify

load_dotenv()


async def build_tasks() -> list:
    """Build Mistral requests."""
    client = Mistral(api_key=os.getenv(key="MISTRAL_API_KEY"))
    messages = [
        {
            "content": "Who is the best French painter? Answer in one short sentence.",
            "role": "user",
        },
    ]
    return [
        client.chat.complete_async(
            model="mistral-medium-2505",
            messages=messages,
            stream=False,
            response_format={"type": "text"},
        ),
        client.chat.complete_async(
            model="mistral-small-2506",
            messages=messages,
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
