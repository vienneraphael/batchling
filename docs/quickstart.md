# Quickstart

batchling is a powerful python library that lets you transform any async GenAI workflow to batched inference, saving you money in exchange of deferred execution (24 hours bound).
You typically want to use batched inference when running any process that does not require immediate response and can wait at most 24 hours (most jobs are completed in a few hours).

## Example use-cases

The range of use-cases you can tackle effortlessly with batchling is extremely wide, here are a few examples:

- Embedding text chunks for your RAG application overnight
- Running large-scale classification with your favourite GenAI provider and/or framework
- Run any GenAI evaluation pipeline
- Generate huge volume of synthtetic data at half the cost
- Transcribe or translate hours of audio in bulk

Things you might not want to run with batchling (yes, there are some..):

- User-facing applications e.g. chatbots, you typically want fast answers
- A whole agentic loop with tons of calls
- Full AI workflows with a lot of sequential calls (each additional step will defer results by an additional 24 hours at worst)

## Installation

batchling is available on PyPI as `batchling`, install using either `pip` or `uv`:

## Package manager

=== "uv"

    ```bash
    uv add batchling
    ```

=== "pip"

    ```bash
    pip install batchling
    ```

## Hello World Example

batchling integrates smoothly with any async function doing GenAI calls or within a whole async script that you'd run with `asyncio`.

Let's suppose we have an existing script `generate.py` that uses the OpenAI client to make two parallel calls using `asyncio.gather`:

    #!/usr/bin/env python3
    import asyncio
    import os
    import typing as t

    from dotenv import load_dotenv
    from openai import AsyncOpenAI

    load_dotenv()


    async def build_tasks() -> list[t.Awaitable[t.Any]]:
        """Build OpenAI requests.
        """
        client = AsyncOpenAI(api_key=os.getenv(key="OPENAI_API_KEY"))
        messages = [
            {
                "content": "Who is the best French painter? Answer in one short sentence.",
                "role": "user",
            },
        ]
        return [
            client.responses.create(
                input=messages,
                model="gpt-4o-mini",
            ),
            client.responses.create(
                input=messages,
                model="gpt-5-nano",
            ),
        ]


    async def main() -> None:
        """Run the OpenAI example."""
        tasks = await build_tasks()
        responses = await asyncio.gather(*tasks)
        for response in responses:
            content = response.output[-1].content # skip reasoning output, get straight to the answer
            print(f"{response.model} answer: {content[0].text}")


    if __name__ == "__main__":
        asyncio.run(main())

=== "CLI"

    For you to switch this async execution to a batched inference one, you just have to run your script using the `batchling` CLI and targetting the main function ran by `asyncio`:

    ```bash
    batchling generate.py:main
    ```

=== "Python SDK"

    To selectively batchify certain pieces of your code execution, you can rely on the `batchify` function, which exposes an async context manager.

    First, add this import at the top of your file:

    ```diff
    + from batchling import batchify
    ```

    Then, let's modify our async function `main` to wrap the `asyncio.gather` call into the `batchify` async context manager:

    ```diff
     async def main() -> None:
         """Run the OpenAI example."""
         tasks = await build_tasks()
    -    responses = await asyncio.gather(*tasks)
    +    with batchify():
    +        responses = await asyncio.gather(*tasks)
         for response in responses:
             content = response.output[-1].content # skip reasoning output, get straight to the answer
             print(f"{response.model} answer: {content[0].text}")
    ```

Output:

    gpt-4o-mini-2024-07-18 answer: The best French painter is often considered to be Claude Monet, a leading figure in the Impressionist movement.
    gpt-5-nano-2025-08-07 answer: There isn’t a universal “best” French painter, but Claude Monet is widely regarded as one of the greatest.

You can run the script and see for yourself, normally small batches like that should run under 5-10 minutes at most.
