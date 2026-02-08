## Usage

### Instance Patching

```
import batchling
from openai import OpenAI
client = batchling.batchify(
    OpenAI(),
    batch_size=40,
    time_limits_seconds=2.0
    poll_interval_seconds=5.0
    completion_window="24h",
    max_retries=1
)
```

### Context Manager
```
with batchling.batchify(
    OpenAI(),
    batch_size=40,
    time_limits_seconds=2.0
    poll_interval_seconds=5.0
    completion_window="24h",
    max_retries=1
):
    client.xxx # batched

client.yyy # not batched
```

## Use-cases

### Bulk (Jobs, Evals..)

```
import asyncio
import batchling
import OpenAI

async def process_many(prompts: list[str]) -> list[str]:
    client = batchling.batchify(
        OpenAI(),
        batch_size=50,
        batch_window_seconds=2.0
    )

    async def get_response(prompt: str) -> str:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    # All requests are batched together automatically
    results = await asyncio.gather(*[get_response(p) for p in prompts])

    await client.close()
    return results

prompts = [
    "What is 2+2?",
    "What is the capital of Paris?"
]
asyncio.run(process_many())
```

### APIs and Queues

TBD


