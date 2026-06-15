import asyncio
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI

from batchling import batchify

load_dotenv()


async def build_tasks() -> list:
    """Build sference chat completion requests."""
    client = AsyncOpenAI(
        api_key=os.getenv(key="SFERENCE_API_KEY"),
        base_url="https://api.sference.com/v1",
    )
    questions = [
        "Who is the best French painter? Answer in one short sentence.",
        "What is the capital of France?",
    ]
    return [
        client.chat.completions.create(
            model="moonshotai/Kimi-K2.6",
            messages=[
                {
                    "role": "user",
                    "content": question,
                }
            ],
        )
        for question in questions
    ]


async def main() -> None:
    """Run the sference example."""
    tasks = await build_tasks()
    responses = await asyncio.gather(*tasks)
    for response in responses:
        print(f"{response.model} answer:\n{response.choices[0].message.content}\n")


async def run_with_batchify() -> None:
    """Run `main` inside `batchify` for direct script execution."""
    async with batchify(completion_window="24h"):
        await main()


if __name__ == "__main__":
    asyncio.run(run_with_batchify())
