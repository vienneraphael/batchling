import asyncio
import os
import typing as t
from dataclasses import dataclass

from dotenv import load_dotenv

from batchling import batchify

load_dotenv()


ProviderRequestRunner = t.Callable[..., t.Coroutine[t.Any, t.Any, tuple[str, str]]]


@dataclass
class ProviderRequestSpec:
    """
    One provider request definition.

    Parameters
    ----------
    provider : str
        Provider display name.
    env_var : str
        Environment variable holding the API key.
    request_runner : ProviderRequestRunner
        Coroutine function sending one request and returning ``(model, answer)``.
    """

    provider: str
    env_var: str
    request_runner: ProviderRequestRunner


async def run_openai_request(*, prompt: str) -> tuple[str, str]:
    """
    Send one OpenAI responses request.

    Parameters
    ----------
    prompt : str
        User question.

    Returns
    -------
    tuple[str, str]
        ``(model_name, answer_text)``.
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=os.getenv(key="OPENAI_API_KEY"))
    response = await client.responses.create(
        input=prompt,
        model="gpt-4o-mini",
    )
    content = response.output[-1].content
    return response.model, content[0].text


async def run_anthropic_request(*, prompt: str) -> tuple[str, str]:
    """
    Send one Anthropic messages request.

    Parameters
    ----------
    prompt : str
        User question.

    Returns
    -------
    tuple[str, str]
        ``(model_name, answer_text)``.
    """
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=os.getenv(key="ANTHROPIC_API_KEY"))
    response = await client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )
    return response.model, response.content[0].text


async def run_groq_request(*, prompt: str) -> tuple[str, str]:
    """
    Send one Groq chat completion request.

    Parameters
    ----------
    prompt : str
        User question.

    Returns
    -------
    tuple[str, str]
        ``(model_name, answer_text)``.
    """
    from groq import AsyncGroq

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
    return response.model, str(object=response.choices[0].message.content)


async def run_mistral_request(*, prompt: str) -> tuple[str, str]:
    """
    Send one Mistral chat completion request.

    Parameters
    ----------
    prompt : str
        User question.

    Returns
    -------
    tuple[str, str]
        ``(model_name, answer_text)``.
    """
    from mistralai import Mistral

    client = Mistral(api_key=os.getenv(key="MISTRAL_API_KEY"))
    response = await client.chat.complete_async(
        model="mistral-medium-2505",
        stream=False,
        response_format={"type": "text"},
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )
    return response.model, str(object=response.choices[0].message.content)


async def run_together_request(*, prompt: str) -> tuple[str, str]:
    """
    Send one Together chat completion request.

    Parameters
    ----------
    prompt : str
        User question.

    Returns
    -------
    tuple[str, str]
        ``(model_name, answer_text)``.
    """
    from together import AsyncTogether

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
    return response.model, str(object=response.choices[0].message.content)


async def run_doubleword_request(*, prompt: str) -> tuple[str, str]:
    """
    Send one Doubleword responses request.

    Parameters
    ----------
    prompt : str
        User question.

    Returns
    -------
    tuple[str, str]
        ``(model_name, answer_text)``.
    """
    from openai import AsyncOpenAI

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


async def run_xai_request(*, prompt: str) -> tuple[str, str]:
    """
    Send one XAI chat completion request.

    Parameters
    ----------
    prompt : str
        User question.

    Returns
    -------
    tuple[str, str]
        ``(model_name, answer_text)``.
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=os.getenv(key="XAI_API_KEY"),
        base_url="https://api.x.ai/v1",
    )
    response = await client.chat.completions.create(
        model="grok-4-1-fast-non-reasoning",
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )
    model_name = str(object=response.chat_get_completion["model"])
    answer_text = str(object=response.chat_get_completion["choices"][0]["message"]["content"])
    return model_name, answer_text


async def run_gemini_request(*, prompt: str) -> tuple[str, str]:
    """
    Send one Gemini generate_content request.

    Parameters
    ----------
    prompt : str
        User question.

    Returns
    -------
    tuple[str, str]
        ``(model_name, answer_text)``.
    """
    from google import genai

    client = genai.Client(api_key=os.getenv(key="GEMINI_API_KEY")).aio
    response = await client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt,
    )
    return response.model_version, str(object=response.text)


def build_provider_specs() -> list[ProviderRequestSpec]:
    """
    Return all provider request specs supported by this example.

    Returns
    -------
    list[ProviderRequestSpec]
        Provider definitions for one-request execution.
    """
    return [
        ProviderRequestSpec(
            provider="openai",
            env_var="OPENAI_API_KEY",
            request_runner=run_openai_request,
        ),
        ProviderRequestSpec(
            provider="anthropic",
            env_var="ANTHROPIC_API_KEY",
            request_runner=run_anthropic_request,
        ),
        ProviderRequestSpec(
            provider="groq",
            env_var="GROQ_API_KEY",
            request_runner=run_groq_request,
        ),
        ProviderRequestSpec(
            provider="mistral",
            env_var="MISTRAL_API_KEY",
            request_runner=run_mistral_request,
        ),
        ProviderRequestSpec(
            provider="together",
            env_var="TOGETHER_API_KEY",
            request_runner=run_together_request,
        ),
        ProviderRequestSpec(
            provider="doubleword",
            env_var="DOUBLEWORD_API_KEY",
            request_runner=run_doubleword_request,
        ),
        ProviderRequestSpec(
            provider="xai",
            env_var="XAI_API_KEY",
            request_runner=run_xai_request,
        ),
        ProviderRequestSpec(
            provider="gemini",
            env_var="GEMINI_API_KEY",
            request_runner=run_gemini_request,
        ),
    ]


def build_enabled_provider_specs() -> list[ProviderRequestSpec]:
    """
    Return provider specs that have API keys configured.

    Returns
    -------
    list[ProviderRequestSpec]
        Enabled provider definitions.
    """
    enabled_specs: list[ProviderRequestSpec] = []
    for spec in build_provider_specs():
        if os.getenv(key=spec.env_var):
            enabled_specs.append(spec)
    return enabled_specs


async def main() -> None:
    """
    Ask one question to many providers and collect all answers with gather.

    Notes
    -----
    This example intentionally uses ``asyncio.gather(..., return_exceptions=True)``
    so all provider outcomes are collected in one pass.
    """
    question = "Give one short sentence explaining what asynchronous batching is."
    enabled_specs = build_enabled_provider_specs()
    if not enabled_specs:
        print("No providers configured. Set at least one provider API key in your environment.")
        return

    tasks = [spec.request_runner(prompt=question) for spec in enabled_specs]
    results = await asyncio.gather(*tasks)

    for spec, result in zip(enabled_specs, results, strict=True):
        model_name, answer_text = result
        print(f"{spec.provider} ({model_name}) answer:\n{answer_text}\n")


async def run_with_batchify() -> None:
    """Run `main` inside `batchify` for direct script execution."""
    async with batchify():
        await main()


if __name__ == "__main__":
    asyncio.run(run_with_batchify())
