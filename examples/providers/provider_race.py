import asyncio
import os
import time
import typing as t
from dataclasses import dataclass

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from groq import AsyncGroq
from mistralai import Mistral
from openai import AsyncOpenAI
from together import AsyncTogether

from batchling import batchify

load_dotenv()


@dataclass
class ProviderRaceResult:
    """One provider completion entry in completion order."""

    model: str
    elapsed_seconds: float
    answer: str


ProviderRequestBuilder = t.Callable[[], t.Coroutine[t.Any, t.Any, tuple[str, str]]]


async def run_openai_request(*, prompt: str) -> tuple[str, str]:
    """
    Send one OpenAI request.

    Parameters
    ----------
    prompt : str
        User prompt sent to the provider.

    Returns
    -------
    tuple[str, str]
        ``(model_name, answer_text)``.
    """
    client = AsyncOpenAI(api_key=os.getenv(key="OPENAI_API_KEY"))
    response = await client.responses.create(
        input=prompt,
        model="gpt-4o-mini",
    )
    content = response.output[-1].content
    return response.model, content[0].text


async def run_anthropic_request(*, prompt: str) -> tuple[str, str]:
    """
    Send one Anthropic request.

    Parameters
    ----------
    prompt : str
        User prompt sent to the provider.

    Returns
    -------
    tuple[str, str]
        ``(model_name, answer_text)``.
    """
    client = AsyncAnthropic(api_key=os.getenv(key="ANTHROPIC_API_KEY"))
    response = await client.messages.create(
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        model="claude-haiku-4-5",
    )
    return response.model, response.content[0].text


async def run_groq_request(*, prompt: str) -> tuple[str, str]:
    """
    Send one Groq request.

    Parameters
    ----------
    prompt : str
        User prompt sent to the provider.

    Returns
    -------
    tuple[str, str]
        ``(model_name, answer_text)``.
    """
    client = AsyncGroq(api_key=os.getenv(key="GROQ_API_KEY"))
    response = await client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )
    return response.model, response.choices[0].message.content


async def run_mistral_request(*, prompt: str) -> tuple[str, str]:
    """
    Send one Mistral request.

    Parameters
    ----------
    prompt : str
        User prompt sent to the provider.

    Returns
    -------
    tuple[str, str]
        ``(model_name, answer_text)``.
    """
    client = Mistral(api_key=os.getenv(key="MISTRAL_API_KEY"))
    response = await client.chat.complete_async(
        model="mistral-medium-2505",
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        stream=False,
        response_format={"type": "text"},
    )
    return response.model, str(object=response.choices[0].message.content)


async def run_together_request(*, prompt: str) -> tuple[str, str]:
    """
    Send one Together request.

    Parameters
    ----------
    prompt : str
        User prompt sent to the provider.

    Returns
    -------
    tuple[str, str]
        ``(model_name, answer_text)``.
    """
    client = AsyncTogether(api_key=os.getenv(key="TOGETHER_API_KEY"))
    response = await client.chat.completions.create(
        model="google/gemma-3n-E4B-it",
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )
    return response.model, response.choices[0].message.content


async def run_doubleword_request(*, prompt: str) -> tuple[str, str]:
    """
    Send one Doubleword request.

    Parameters
    ----------
    prompt : str
        User prompt sent to the provider.

    Returns
    -------
    tuple[str, str]
        ``(model_name, answer_text)``.
    """
    client = AsyncOpenAI(
        api_key=os.getenv(key="DOUBLEWORD_API_KEY"),
        base_url="https://api.doubleword.ai/v1",
    )
    response = await client.responses.create(
        input=prompt,
        model="openai/gpt-oss-20b",
    )
    content = response.output[-1].content
    return response.model, content[0].text


async def run_provider_request(
    *,
    request_builder: ProviderRequestBuilder,
    started_at: float,
) -> ProviderRaceResult:
    """
    Execute one provider request and annotate elapsed time.

    Parameters
    ----------
    request_builder : ProviderRequestBuilder
        Provider request coroutine factory.
    started_at : float
        Shared wall-clock start time in ``perf_counter`` seconds.

    Returns
    -------
    ProviderRaceResult
        Result payload with answer and elapsed time.
    """
    model, answer = await request_builder()
    elapsed_seconds = time.perf_counter() - started_at
    return ProviderRaceResult(
        model=model,
        elapsed_seconds=elapsed_seconds,
        answer=answer,
    )


def build_enabled_request_builders(*, prompt: str) -> list[ProviderRequestBuilder]:
    """
    Build one request factory per configured provider.

    Parameters
    ----------
    prompt : str
        Shared text prompt sent to all providers.

    Returns
    -------
    list[ProviderRequestBuilder]
        Enabled provider request factories.
    """
    providers: list[tuple[str, ProviderRequestBuilder]] = [
        (
            "OPENAI_API_KEY",
            lambda: run_openai_request(prompt=prompt),
        ),
        (
            "ANTHROPIC_API_KEY",
            lambda: run_anthropic_request(prompt=prompt),
        ),
        (
            "GROQ_API_KEY",
            lambda: run_groq_request(prompt=prompt),
        ),
        (
            "MISTRAL_API_KEY",
            lambda: run_mistral_request(prompt=prompt),
        ),
        (
            "TOGETHER_API_KEY",
            lambda: run_together_request(prompt=prompt),
        ),
        (
            "DOUBLEWORD_API_KEY",
            lambda: run_doubleword_request(prompt=prompt),
        ),
    ]
    enabled_builders: list[ProviderRequestBuilder] = []
    for env_var_name, request_builder in providers:
        api_key = os.getenv(key=env_var_name)
        if not api_key:
            continue
        enabled_builders.append(request_builder)
    return enabled_builders


async def main() -> None:
    """
    Run one request per provider and collect completion-order results.

    The race excludes Gemini and XAI on purpose because their model field
    extraction differs from the other provider examples.
    """
    prompt = "Give one short sentence explaining what asynchronous batching is."
    request_builders = build_enabled_request_builders(prompt=prompt)
    if not request_builders:
        print("No providers configured. Set at least one provider API key in your environment.")
        return

    started_at = time.perf_counter()
    tasks = [
        asyncio.create_task(
            run_provider_request(
                request_builder=request_builder,
                started_at=started_at,
            )
        )
        for request_builder in request_builders
    ]

    completion_order_register: list[ProviderRaceResult] = []
    for task in asyncio.as_completed(tasks):
        result = await task
        completion_order_register.append(result)

    for index, result in enumerate(completion_order_register, start=1):
        print(f"{index}. model={result.model}")
        print(f"   elapsed={result.elapsed_seconds:.2f}s")
        print(f"   answer={result.answer}\n")


async def run_with_batchify() -> None:
    """Run the provider race inside ``batchify`` for direct script execution."""
    async with batchify():
        await main()


if __name__ == "__main__":
    asyncio.run(run_with_batchify())
