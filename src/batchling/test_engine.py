import asyncio
import base64
import os
import typing as t

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from google import genai
from groq import AsyncGroq
from mistralai import Mistral
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from together import AsyncTogether

load_dotenv()


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


class ImageAnalysis(BaseModel):
    name: str = Field(description="the name of the image")
    fun_fact: str = Field(description="a fun fact about the image")


async def mistral_tasks():
    client = Mistral(api_key=os.getenv(key="MISTRAL_API_KEY"))
    messages: list[dict[str, str]] = [
        {
            "content": "Who is the best French painter? Answer in one short sentence.",
            "role": "user",
        },
    ]
    tasks = [
        client.chat.complete_async(
            model="mistral-medium-2505",
            messages=t.cast(t.Any, messages),
            stream=False,
            response_format={"type": "text"},
        ),
        client.chat.complete_async(
            model="mistral-small-2506",
            messages=t.cast(t.Any, messages),
            stream=False,
            response_format={"type": "text"},
        ),
    ]
    return tasks


async def openai_tasks():
    client = AsyncOpenAI(api_key=os.getenv(key="OPENAI_API_KEY"))
    messages = [
        {
            "content": "Who is the best French painter? Answer in one short sentence.",
            "role": "user",
        },
    ]
    tasks = [
        client.responses.create(
            input=t.cast(t.Any, messages),
            model="gpt-4o-mini",
            stream=False,
        ),
        client.responses.create(
            input=t.cast(t.Any, messages),
            model="gpt-5-nano",
            stream=False,
        ),
    ]
    return tasks


async def together_tasks():
    client = AsyncTogether(api_key=os.getenv(key="TOGETHER_API_KEY"))
    messages = [
        {
            "content": "Who is the best French painter? Answer in one short sentence.",
            "role": "user",
        },
    ]
    tasks = [
        client.chat.completions.create(
            model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
            messages=t.cast(t.Any, messages),
        ),
        client.chat.completions.create(
            model="google/gemma-3n-E4B-it",
            messages=t.cast(t.Any, messages),
        ),
    ]
    return tasks


async def anthropic_tasks():
    client = AsyncAnthropic(api_key=os.getenv(key="ANTHROPIC_API_KEY"))
    messages = [
        {
            "content": "Who is the best French painter? Answer in one short sentence.",
            "role": "user",
        },
    ]
    tasks = [
        client.messages.create(
            max_tokens=1024,
            messages=t.cast(t.Any, messages),
            model="claude-haiku-4-5",
        ),
        client.messages.create(
            max_tokens=1024,
            messages=t.cast(t.Any, messages),
            model="claude-3-5-haiku-latest",
        ),
    ]
    return tasks


async def groq_tasks():
    client = AsyncGroq(api_key=os.getenv(key="GROQ_API_KEY"))
    messages = [
        {
            "content": "Who is the best French painter? Answer in one short sentence.",
            "role": "user",
        },
    ]
    tasks = [
        client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=t.cast(t.Any, messages),
        ),
        client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=t.cast(t.Any, messages),
        ),
    ]
    return tasks


async def gemini_tasks():
    client = genai.Client(api_key=os.getenv(key="GEMINI_API_KEY")).aio
    contents = "Who is the best French painter? Answer in one short sentence."
    tasks = [
        client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
        ),
        client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
        ),
    ]
    return tasks


async def main(provider: str):
    match provider:
        case "mistral":
            tasks = await mistral_tasks()
        case "openai":
            tasks = await openai_tasks()
        case "together":
            tasks = await together_tasks()
        case "anthropic":
            tasks = await anthropic_tasks()
        case "groq":
            tasks = await groq_tasks()
        case "gemini":
            tasks = await gemini_tasks()
        case _:
            raise ValueError(f"Invalid provider: {provider}")
    responses = await asyncio.gather(*tasks)
    print(responses)
