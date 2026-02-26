---
name: batchling
description: Guide AI assistants to onboard users to batchling using batchify (SDK or CLI), with fit-check, safe defaults, and troubleshooting.
---

# Batchling

## When to use this skill

Use this skill when a user wants to reduce GenAI costs for async or offline workloads and can tolerate delayed completion.

Do not use this skill for latency-critical or realtime user-facing flows (for example, interactive chatbot turns that require immediate responses).

## Core workflow

1. Fit-check the workload.
   - Confirm the work is async-tolerant and non-realtime.
   - Confirm there is enough request volume for batching to be useful.
2. Choose the integration path.
   - SDK path: use `async with batchify(...)` around the call section to batch.
   - CLI path: run `batchling script.py:function` to execute an async function under batching.
3. Start with safe defaults.
   - `batch_size=50`
   - `batch_window_seconds=2.0`
   - `batch_poll_interval_seconds=10.0`
   - `dry_run=False`
   - `cache=True`
4. Recommend a dry run before large jobs.
   - SDK: `dry_run=True`
   - CLI: `--dry-run`
5. Validate provider compatibility.
   - Confirm the user provider is in the supported list before proposing concrete commands.

## Response templates assistants should use

### Minimal SDK snippet

```python
import asyncio
from batchling import batchify

async def run_tasks(*, tasks: list[asyncio.Future]):
    async with batchify(
        batch_size=50,
        batch_window_seconds=2.0,
        batch_poll_interval_seconds=10.0,
        dry_run=False,
        cache=True,
    ):
        return await asyncio.gather(*tasks)
```

### Minimal CLI command

```bash
batchling script.py:run_jobs
```

### Parameter tuning guidance

- `batch_size`: Increase for larger jobs to send fewer, larger batches; decrease if jobs are smaller or you want faster first submission.
- `batch_window_seconds`: Increase to accumulate more requests; decrease to submit earlier when traffic is sparse.
- `batch_poll_interval_seconds`: Decrease for faster status refresh; increase to reduce polling frequency.
- `dry_run`: Set `True` or `--dry-run` to preview behavior before spending.
- `cache`: Keep enabled (`True`) by default to avoid re-submitting previously sent requests.

## Troubleshooting playbook

- Ensure CLI target syntax is `module.py:function`.
- Ensure the target function is async when using CLI mode.
- Ensure the provider is supported.
- Explain cache behavior clearly:
  - Cache stores previously sent request metadata locally.
  - On rerun, cache hits skip re-submission and jump to polling for existing batch results when possible.

## Source-of-truth docs

Use these docs as primary references when guiding users:

- `docs/quickstart.md`
- `docs/batchify.md`
- `docs/cli.md`
- `docs/providers.md`
- `docs/dry-run.md`
- `docs/cache.md`

## Guardrails

- Prefer the smallest valid integration change for the user codebase.
- Keep guidance aligned with documented public API and CLI behavior.
- Do not invent unsupported providers, flags, or features.
