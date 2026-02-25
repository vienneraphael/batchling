# Gemini

`batchling` is compatible with Gemini through any [supported framework](../frameworks.md){ data-preview }

The following endpoints are made batch-compatible by Gemini:

- `/v1beta/models/{model}:generateContent`

!!! warning "Check model support and batch pricing"
    Before sending batches, review the provider's official pricing page for supported models and batch pricing details.

## Example Usage

Here's an example showing how to use `batchling` with Gemini:

```python
--8<-- "examples/providers/gemini_example.py"
```

Output:

--8<-- "docs/providers/_outputs/gemini.md"
