# Python SDK

To use `batchling`, you only need to learn to use one function exposed through the library: [`batchify`](./batchify.md){ data-preview }

The `batchify` function is meant to be used as a context manager wrapping portions of your code containing GenAI calls that you want to batch.

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
    generated_images = await asyncio.gather(*tasks)
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

Here's how you can leverage `batchling` Python SDK to transform that workflow from async to batched:

Add one import at the top of your file:

```diff
+ from batchling import batchify
```

Add the context manager scoping to your script:

```diff
async def main():
    new_product_descriptions = await get_new_product_descriptions()
    tasks = [
        generate_image(text=product_description)
        for product_description in new_product_descriptions
    ]
-   generated_images = asyncio.gather(*tasks)
+   async with batchify():
+       generated_images = await asyncio.gather(*tasks)
    await update_product_db(generated_images=generated_images)
```

That's it! Update three lines of code and you save 50% off your workflow.

You can now run this script normally using python and start saving money:

```bash
python generate_product_images.py
```

## Next Steps

If you haven't yet, look at how you can:

- leverage the [CLI](./cli.md) to batchify full scripts in one command

- use `batchling` with any [provider](./providers.md) / [framework](./frameworks.md) with examples

- learn about [advanced features](./advanced-features.md)
