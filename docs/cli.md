# CLI

batchling comes with a CLI included that further facilitates batching an existing process.

The CLI pushes the abstraction even more, to a point where you don't even need to modify your code to start batching.

## Example

Suppose you work in e-commerce and you have a cutting-edge business which uses GenAI to generate product visuals whenever you receive new products from your vendors.
You have a function `generate_image` that takes a prompt (string) as input and generates the corresponding image using an API, returning image bytes.
You would typically run concurrent tasks using `asyncio` for tasks not blocking each other in the execution loop.

```python
# generate_product_images.py
import asyncio

async def get_new_product_descriptions() -> list[str]:
    """
    Fetches pending product descriptions having no image yet
    """
    ...

async def generate_image(text: str) -> bytes:
    ...

async def update_product_db(generated_images: list[bytes]):
    """
    Update product db with generated images for review
    """

async def main():
    new_product_descriptions = await get_new_product_descriptions()
    tasks = [
        generate_image(text=product_description)
        for product_description in new_product_descriptions
    ]
    generated_images = asyncio.gather(*tasks)
    await update_product_db(generated_images=generated_images)


if __name__ == "__main__":
    asyncio.run(main())
```

This approach might have several drawbacks for you:

1. You pay the full price for calls that likely can wait at most 24h.
2. You might hit your providers' rate limits if you send all products at once, so you likely need to add more complex structures like semaphores.
3. Even with semaphores, you might run into daily rate limits, so you likely want to implement retries with exponential waiting

The batch inference approach solves all those issues:

1. Cut costs by 50% if you can wait up to 24 hours.
2. Batch APIs rate limits are made for high-volume and thus always higher (near-infinite for certain providers)
3. No retries mechanism needed, you keep the code simple and light.

Here's how you can leverage the `batchling` CLI to transform that workflow from async to batched.

In your terminal, run the following command:

```bash
batchling generate_product_images.py:main
```

That's it! Just run that command and you save 50% off your workflow.

## Next Steps

If you haven't yet, look at how you can:

- leverage the [Python SDK](./python-sdk.md) to scope batching to specific portions of your code.

- use `batchling` with any [provider](./providers.md) / [framework](./frameworks.md) with examples

- learn about end-to-end [use-cases](./use-cases.md) using `batchling`

- learn about [advanced features](./advanced-features.md)
