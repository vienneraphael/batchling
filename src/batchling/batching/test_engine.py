import asyncio
import base64
import os
import typing as t

from dotenv import load_dotenv
from mistralai import Mistral
from pydantic import BaseModel, Field

load_dotenv()


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


class ImageAnalysis(BaseModel):
    name: str = Field(description="the name of the image")
    fun_fact: str = Field(description="a fun fact about the image")


async def main():
    client = Mistral(api_key=os.getenv(key="MISTRAL_API_KEY"))
    # with batchify(dry_run=False):
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
        )
    ]
    responses = await asyncio.gather(*tasks)
    print(responses)


if __name__ == "__main__":
    asyncio.run(main())
