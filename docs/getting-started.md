# Getting Started

## Install

```bash
pip install batchling
```

## Minimal async usage (recommended)

```python
import asyncio
from batchling import batchify
from openai import AsyncOpenAI


async def generate() -> None:
    client = AsyncOpenAI()
    messages = [
        {
            "role": "user",
            "content": "Classify this text in one label: 'Batch APIs reduce cost for deferred jobs.'",
        }
    ]

    async with batchify():
        responses = await asyncio.gather(
            client.responses.create(
                model="gpt-4o-mini",
                input=messages,
            ),
            client.responses.create(
                model="gpt-4o-mini",
                input=messages,
            ),
        )

    print(responses)


asyncio.run(generate())
```

## What to expect at runtime

- Batchling installs request hooks and watches supported HTTP requests.
- Supported requests are grouped by `(provider, endpoint, model)`.
- A batch is submitted when either queue size or window threshold is hit.
- Batch results are polled and mapped back to each original request.

## CLI wrapper option

If your workload already lives in an async function inside a script, use the CLI wrapper:

```bash
batchling path/to/script.py:generate --batch-size 100 --batch-window-seconds 3.0
```

The target must be an `async def` callable.
