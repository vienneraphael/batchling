# Streaming batches

Throughout the docs, we mostly rely on `asyncio.gather` for simplicity and developer experience, but it's also possible to stream batch rather than waiting for all to be processed before continuing the process!

## `asyncio.gather` vs `asyncio.as_completed`

Before looking at how you can stream batches results, let's go through a quick reminder about the two main `asyncio` result collection methods.

- `asyncio.gather`: Executes tasks concurrently and waits for the entire group to finish before returning. It preserves the original order of results, making it the most efficient choice when your next step requires the complete dataset.
- `asyncio.as_completed`: Yields results in an iterable as they finish (fastest first). This reduces "time to first byte" by allowing you to process early successes immediately, though it introduces slight overhead by requiring a loop to handle results one by one.

## How to stream batches

If you need to stream batches results as they are made available (for logging, tracking progress, saving intermediate results to db..), you can stream batches like so:

```python
--8<-- "examples/streaming_batches.py"
```

Output:

```text
Processed batches: 1 / 2
llama-3.1-8b-instant answer:
A man walked into a library and asked the librarian, "Do you have any books on Pavlov's dogs and Schrödinger's cat?" The librarian replied, "It rings a bell, but I'm not sure if it's here or not."

Processed batches: 2 / 2
openai/gpt-oss-20b answer:
Why don't skeletons fight each other? They don't have the guts.
```
