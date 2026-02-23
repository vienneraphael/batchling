import asyncio

from dotenv import load_dotenv
from litellm import acompletion

from batchling import batchify

load_dotenv()


async def build_tasks() -> list:
    """Build LiteLLM requests."""
    questions = [
        "Who is the best French painter? Answer in one short sentence.",
        "What is the capital of France?",
    ]
    return [
        acompletion(model="openai/gpt-5-nano", messages=[{"role": "user", "content": question}])
        for question in questions
    ]


async def main() -> None:
    """Run the pydantic-ai example."""
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
