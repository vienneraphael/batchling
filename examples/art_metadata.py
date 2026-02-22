# --8<-- [start:quickstart]
import asyncio

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from batchling import batchify

load_dotenv()


class ArtMetadata(BaseModel):
    author: str = Field(
        description="The name of the artist who created the artwork.",
        examples=["Vincent van Gogh", "Leonardo da Vinci", "Michelangelo", "Pablo Picasso"],
    )
    name: str = Field(
        description="The title of the artwork.",
        examples=["The Starry Night", "The Scream", "The Last Supper", "The Mona Lisa"],
    )
    period: str = Field(
        description="The period or time of the artwork. Be as precise as possible.",
        examples=["1600's", "1758", "Renaissance"],
    )
    movement: str = Field(
        description="The movement or style of the artwork.",
        examples=["Impressionism", "Baroque", "Rococo", "Neoclassicism"],
    )
    material: str = Field(
        description="The material or medium of the artwork.",
        examples=["Oil on canvas", "Watercolor", "Gouache", "Pastel"],
    )
    tags: list[str] = Field(
        description="A list of tags or keywords that describe the artwork.",
        examples=["landscape", "portrait", "still life", "war scene", "historical event"],
    )
    context: str = Field(description="A short text describing the context of the artwork.")
    fun_fact: str = Field(description="A fun fact about the artwork.")


client = AsyncOpenAI()


async def generate_art_metadata(image_url: str):
    input_query = [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_image",
                    "image_url": image_url,
                },
            ],
        }
    ]
    return await client.responses.parse(
        input=input_query,
        model="gpt-5-nano",
        text_format=ArtMetadata,
    )


async def build_tasks():
    image_urls = [
        "https://api.nga.gov/iiif/a2e6da57-3cd1-4235-b20e-95dcaefed6c8/full/!800,800/0/default.jpg",
        "https://api.nga.gov/iiif/9d8f80cf-7d2c-455a-9fb9-73e5ce2012b2/full/!800,800/0/default.jpg",
        "https://api.nga.gov/iiif/54ee6643-e0f9-4b92-a1d2-441e5108724d/full/!800,800/0/default.jpg",
    ]
    return [generate_art_metadata(image_url) for image_url in image_urls]


async def enrich_art_images() -> list[ArtMetadata]:
    tasks = await build_tasks()
    responses = await asyncio.gather(*tasks)
    for response in responses:
        print(response.output_parsed.model_dump_json(indent=2))


# --8<-- [end:quickstart]


async def run_with_batchify():
    async with batchify():
        await enrich_art_images()


if __name__ == "__main__":
    asyncio.run(run_with_batchify())
