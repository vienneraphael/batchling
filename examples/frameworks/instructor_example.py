import asyncio

import instructor
from dotenv import load_dotenv
from pydantic import BaseModel

from batchling import batchify

load_dotenv()


class Person(BaseModel):
    name: str
    age: int
    occupation: str


async def build_tasks() -> list:
    """Build Instructor requests."""
    client = instructor.from_provider("openai/gpt-5-nano", async_client=True)
    questions = [
        "Extract: Daniel is a 25-year-old software engineer",
        "Extract: Marie is a 26-year-old freelance in communication",
    ]
    return [
        client.create(response_model=Person, messages=[{"role": "user", "content": question}])
        for question in questions
    ]


async def main() -> None:
    """Run the Instructor example."""
    tasks = await build_tasks()
    responses = await asyncio.gather(*tasks)
    for response in responses:
        print(response.model_dump_json(indent=2))


async def run_with_batchify() -> None:
    """Run `main` inside `batchify` for direct script execution."""
    async with batchify():
        await main()


if __name__ == "__main__":
    asyncio.run(run_with_batchify())
