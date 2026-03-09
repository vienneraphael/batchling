import asyncio

import dspy
from dotenv import load_dotenv

from batchling import batchify

load_dotenv()


async def build_tasks() -> list:
    """Build dspy requests."""
    dspy.configure(lm=dspy.LM("together_ai/google/gemma-3n-E4B-it"))
    predict = dspy.Predict("question->answer")
    questions = [
        "Who is the best French painter? Answer in one short sentence.",
        "What is the capital of France?",
    ]
    return [predict.acall(question=question) for question in questions]


async def main() -> None:
    """Run the dspy example."""
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
