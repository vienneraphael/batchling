import asyncio
import os

from cerebras.cloud.sdk import AsyncCerebras
from dotenv import load_dotenv

from batchling import batchify

load_dotenv()


async def build_tasks() -> list:
    """Build OpenAI requests."""
    client = AsyncCerebras(api_key=os.getenv(key="CEREBAS_API_KEY"))
    questions = [
        "Who is the best French painter? Answer in one short sentence.",
        "What is the capital of France?",
    ]
    return [
        client.chat.completions.create(
            messages={
                "role": "user",
                "content": question,
            },
            model="zai-glm-4.7",
        )
        for question in questions
    ]


async def main() -> None:
    """Run the OpenAI example."""
    tasks = await build_tasks()
    responses = await asyncio.gather(*tasks)
    for response in responses:
        print(f"{response.model} answer:\n{response.choices[0].message.content}\n")


async def run_with_batchify() -> None:
    """Run `main` inside `batchify` for direct script execution."""
    async with batchify():
        await main()


if __name__ == "__main__":
    asyncio.run(run_with_batchify())
