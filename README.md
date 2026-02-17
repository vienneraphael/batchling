# batchling

<div align="center">
<img src="./docs/assets/images/batchling.png" alt="batchling logo" width="500" role="img">
</div>
<p align="center">
    <em>Save 50% off GenAI costs in two lines of code!</em>
</p>
<p align="center">
<a href="https://github.com/vienneraphael/batchling/actions/workflows/ci.yml" target="_blank">
    <img src="https://github.com/vienneraphael/batchling/actions/workflows/ci.yml/badge.svg" alt="CI">
<a href="https://pypi.org/project/batchling" target="_blank">
    <img src="https://img.shields.io/pypi/v/batchling?color=%2334D058&label=pypi%20package" alt="Package version">
</a>
</p>

---

batchling intercepts supported provider HTTP requests, groups them by `(provider, endpoint, model)`, and submits them through provider batch APIs.

## What it does

- Unified batch routing across providers
- Automatic queueing with `batch_size` and `batch_window_seconds`
- Hook-based interception for `httpx` and `aiohttp`
- `dry_run` mode for non-I/O validation of batching flows

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

## Installation

```bash
pip install batchling
```

## Python usage

Use `batchify` as a scope-only context manager around code that triggers provider HTTP calls.

```python
import httpx

from batchling import batchify


async def run() -> None:
    async with batchify(batch_size=10, batch_window_seconds=1.0, dry_run=False):
        async with httpx.AsyncClient() as client:
            await client.post(
                url="https://api.openai.com/v1/chat/completions",
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "Say hi"}],
                },
            )
```

## CLI usage

Run an async function from a script inside a `batchify` context:

```bash
batchling path/to/script.py:run_job --batch-size 10 --batch-window-seconds 1.0 arg1 --name alice
```

Notes:

- Script target must follow `path/to/script.py:function_name`.
- Target function must be `async def`.
- Extra args are forwarded to the target function.

## Documentation

- Architecture overview: `docs/architecture/overview.md`
- API surface: `docs/architecture/api.md`
- Core engine: `docs/architecture/core.md`
- Hooks: `docs/architecture/hooks.md`
- Context manager: `docs/architecture/context.md`
- Providers: `docs/architecture/providers.md`
