#!/usr/bin/env python3
import asyncio
import base64
import os
import typing as t

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field

from batchling import batchify

load_dotenv()


class ImageAnalysis(BaseModel):
    """Structured image-analysis response example.

    Attributes
    ----------
    name : str
        Name of the image content.
    fun_fact : str
        Short fun fact about the image.
    """

    name: str = Field(description="the name of the image")
    fun_fact: str = Field(description="a fun fact about the image")


def encode_image(image_path: str) -> str:
    """Encode an image file as base64.

    Parameters
    ----------
    image_path : str
        Absolute or relative path to an image.

    Returns
    -------
    str
        Base64-encoded content.
    """
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


async def build_tasks() -> list[t.Awaitable[t.Any]]:
    """Build Gemini requests.

    Returns
    -------
    list[asyncio.Future]
        Concurrent requests for batchling execution.
    """
    client = genai.Client(api_key=os.getenv(key="GEMINI_API_KEY")).aio
    contents = "Who is the best French painter? Answer in one short sentence."
    return [
        client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
        ),
        client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
        ),
    ]


async def main() -> None:
    """Run the Gemini example."""
    tasks = await build_tasks()
    responses = await asyncio.gather(*tasks)
    print(responses)


async def run_with_batchify() -> None:
    """Run `main` inside `batchify` for direct script execution."""
    async with batchify():
        await main()


if __name__ == "__main__":
    asyncio.run(run_with_batchify())
