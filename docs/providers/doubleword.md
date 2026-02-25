# Doubleword

`batchling` is compatible with Doubleword through any [supported framework](../frameworks.md){ data-preview }

The following endpoints are made batch-compatible by Doubleword:

- `/v1/chat/completions`
- `/v1/responses`
- `/v1/embeddings`
- `/v1/moderations`
- `/v1/completions`

!!! warning "Check model support and batch pricing"
    Before sending batches, review the provider's official pricing page for supported models and batch pricing details.

## Example Usage

Here's an example showing how to use `batchling` with Doubleword:

```python
--8<-- "examples/providers/doubleword_example.py"
```

Output:

--8<-- "docs/providers/_outputs/doubleword.md"
