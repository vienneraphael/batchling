<!-- markdownlint-disable-file MD041 MD001 -->
<div align="center">
<img src="https://raw.githubusercontent.com/vienneraphael/batchling/main/docs/assets/images/batchling.png" alt="batchling logo" width="500" role="img">
</div>
<p align="center">
    <em>Save 50% off GenAI costs in two lines of code</em>
</p>
<p align="center">
<a href="https://github.com/vienneraphael/batchling/actions/workflows/ci.yml" target="_blank">
    <img src="https://github.com/vienneraphael/batchling/actions/workflows/ci.yml/badge.svg" alt="CI">
</a>
<a href="https://pypi.org/project/batchling" target="_blank">
    <img src="https://img.shields.io/pypi/v/batchling?color=%2334D058&label=pypi%20package" alt="Package version">
</a>
</p>

---

batchling is a frictionless, batteries-included plugin to convert any GenAI async function or script into half-cost deferred jobs.

Key features:

- **Simplicity**: a simple 2-liner gets you 50% off your GenAI bill instantly.
- **Transparent**: Your code remains the same, no added behaviors. Track sent batches easily.
- **Global**: Integrates with most providers and all frameworks.
- **Safe**: Get a complete breakdown of your cost savings before launching a single batch.
- **Lightweight**: Very few dependencies.

<details markdown="1">

<summary><strong>What's the catch?</strong></summary>

The batch is the catch!

Batch APIs enable you to process large volumes of requests asynchronously (usually at 50% lower cost compared to real-time API calls). It's perfect for workloads that don't need immediate responses such as:

- Running mass offline evaluations
- Classifying large datasets
- Generating large-scale embeddings
- Offline summarization
- Synthetic data generation
- Structured data extraction (e.g. OCR)
- Audio transcriptions/translations at scale

Compared to using standard endpoints directly, Batch API offers:

- **Better cost efficiency**: usually 50% cost discount compared to synchronous APIs
- **Higher rate limits**: Substantially more headroom with separate rate limit pools
- **Large-scale support**: Process thousands of requests per batch
- **Flexible completion**: Best-effort completion within 24 hours with progress tracking, batches usually complete within an hour.

</details>

## Installation

```bash
pip install batchling
```

## Get Started

### Using the async context manager (recommended)

```python
import asyncio
from batchling import batchify
from openai import AsyncOpenAI

async def generate():
    client = AsyncOpenAI()
    questions = [
        "Who is the best French painter? Answer in one short sentence.",
        "What is the capital of France?",
    ]
    return [
        client.responses.create(input=question, model="gpt-4o-mini") for question in questions
    ]
    with batchify(): # Runs your tasks as batches, save 50%
        responses = await asyncio.gather(*tasks)
```

### Using the CLI wrapper

Create a file `main.py` with:

```python
import asyncio
from openai import AsyncOpenAI

async def generate():
    client = AsyncOpenAI()
    messages = [
        {
            "content": "Who is the best French painter? Answer in one short sentence.",
            "role": "user",
        },
    ]
    tasks = [
        client.responses.create(
            input=messages,
            model="gpt-4o-mini",
        ),
        client.responses.create(
            input=messages,
            model="gpt-5-nano",
        ),
    ]
    responses = await asyncio.gather(*tasks)
```

Run your function in batch mode:

```bash
batchling main.py:generate
```

## Supported providers

| Name        | Batch API Docs URL                                                       |
|-------------|--------------------------------------------------------------------------|
| OpenAI      | <https://platform.openai.com/docs/guides/batch>                          |
| Anthropic   | <https://docs.anthropic.com/en/docs/build-with-claude/batch-processing>  |
| Gemini      | <https://ai.google.dev/gemini-api/docs/batch-mode>                       |
| Groq        | <https://console.groq.com/docs/batch>                                    |
| Mistral     | <https://docs.mistral.ai/capabilities/batch/>                            |
| Together AI | <https://docs.together.ai/docs/batch-inference>                          |
| Doubleword  | <https://docs.doubleword.ai/batches/getting-started-with-batched-api>    |

## Next Steps

To try `batchling` for yourself, follow  this [quickstart guide](https://vienneraphael.github.io/batchling/quickstart/).

Read the [docs](https://vienneraphael.github.io/batchling/batchify/) to learn more about how you can save on your GenAI expenses with `batchling`.
