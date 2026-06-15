# Sference

`batchling` is compatible with Sference through any [supported framework](../frameworks.md){ data-preview }

The following endpoints are made batch-compatible by Sference:

- `/v1/chat/completions`

!!! warning "Check model support and batch pricing"
    Before sending batches, review the provider's official pricing page for supported models and batch pricing details.

The Batch API docs for Sference can be found on the following URL:
--8<-- "docs/providers/_urls/sference.md"

## Example Usage

--8<-- "docs/providers/_credentials/sference.md"

Here's an example showing how to use `batchling` with Sference:

```py title="sference_example.py"
--8<-- "examples/providers/sference_example.py"
```
