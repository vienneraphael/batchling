import asyncio
import os

from dotenv import load_dotenv
from google import genai

from batchling import batchify

load_dotenv()


async def build_tasks() -> list:
    """Build Gemini requests."""
    client = genai.Client(
        vertexai=True, project=os.getenv(key="VERTEX_PROJECT_ID"), location="us-central1"
    ).aio
    questions = [
        "Who is the best French painter? Answer in one short sentence.",
        "What is the capital of France?",
    ]
    return [
        client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=question,
        )
        for question in questions
    ]


async def main() -> None:
    """Run the Gemini example."""
    tasks = await build_tasks()
    responses = await asyncio.gather(*tasks)
    for response in responses:
        print(f"{response.model_version} answer:\n{response.text}\n")


async def run_with_batchify() -> None:
    """Run `main` inside `batchify` for direct script execution."""
    async with batchify(vertex_gcs_prefix=os.getenv("VERTEX_GCS_PREFIX")):
        await main()


if __name__ == "__main__":
    asyncio.run(run_with_batchify())
