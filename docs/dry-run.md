# Dry Run

`batchling` allow users to declare that they want to launch a dry run for their batching.

This feature exists for users to be able to debug and better understand what WILL happen when they ultimately disable the flag, giving them the transparency required to be confident in the library.

In practice, dry-run deactivates all provider submissions while keeping the
internal batching path active (queueing, windowing, and per-queue grouping).

To put it simply, it provides users with an exact breakdown of what their
batched inference run would have been for real.

Sample output:

```text
╭────────────────────────────────────────────── batchling dry run summary ───────────────────────────────────────────────╮
│ Batchable Requests: 8  -  Cache Hit Requests: 0                                                                        │
│ ┏━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┓ │
│ ┃ provider    ┃ endpoint                          ┃ model                       ┃ expected reques… ┃ expected batch… ┃ │
│ ┡━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━┩ │
│ │ anthropic   │ /v1/messages                      │ claude-haiku-4-5            │                1 │               1 │ │
│ │ doubleword  │ /v1/responses                     │ openai/gpt-oss-20b          │                1 │               1 │ │
│ │ gemini      │ /v1beta/models/gemini-2.5-flash-… │ gemini-2.5-flash-lite       │                1 │               1 │ │
│ │ groq        │ /openai/v1/chat/completions       │ llama-3.1-8b-instant        │                1 │               1 │ │
│ │ mistral     │ /v1/chat/completions              │ mistral-medium-2505         │                1 │               1 │ │
│ │ openai      │ /v1/responses                     │ gpt-4o-mini                 │                1 │               1 │ │
│ │ together    │ /v1/chat/completions              │ google/gemma-3n-E4B-it      │                1 │               1 │ │
│ │ xai         │ /v1/chat/completions              │ grok-4-1-fast-non-reasoning │                1 │               1 │ │
│ └─────────────┴───────────────────────────────────┴─────────────────────────────┴──────────────────┴─────────────────┘ │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## Avoid partial counts

Dry-run exits as soon as the first intercepted request returns, which can lead
to partial totals if requests are awaited one by one. To let batchling see the
full request set before exit, schedule requests together and await them with
`asyncio.gather`.

For SDK usage, this abort is handled at the `batchify` scope boundary so the
dry-run summary is shown without a traceback. There is no separate dry-run mode
parameter beyond `dry_run=True` / `--dry-run`.

## Activating dry run

Dry run is activated by setting up a flag in the CLI or SDK:

- `dry_run=True` if using the SDK

- `--dry-run` if using the CLI

## Next Steps

- See how [cache](./cache.md) is saved and for how long it is kept.
