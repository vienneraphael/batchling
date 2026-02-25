import asyncio
import os

from dotenv import load_dotenv
from groq import AsyncGroq

from batchling import batchify

load_dotenv()


async def build_tasks() -> list:
    """Build an identical groq request for two models to create two batches."""
    client = AsyncGroq(api_key=os.getenv(key="GROQ_API_KEY"))
    models = ["llama-3.1-8b-instant", "openai/gpt-oss-20b"]
    question = "Tell me a short joke, one sentence max."
    return [
        client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": question,
                }
            ],
        )
        for model in models
    ]


async def main() -> None:
    """Run the streaming batches example."""
    tasks = await build_tasks()
    processed_batches = 0
    for task in asyncio.as_completed(tasks):
        response = await task
        processed_batches += 1
        print(f"Processed batches: {processed_batches} / {len(tasks)}")
        print(f"{response.model} answer:\n{response.choices[0].message.content}\n")


async def run_with_batchify() -> None:
    """Run `main` inside `batchify` for direct script execution."""
    async with batchify(cache=False):
        await main()


if __name__ == "__main__":
    asyncio.run(run_with_batchify())
