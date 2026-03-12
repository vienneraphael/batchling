# Vertex

`batchling` is compatible with Vertex through any [supported framework](../frameworks.md){ data-preview }

The following endpoints are made batch-compatible by Vertex:

- _No declared `batchable_endpoints` found in the provider file._

!!! warning "Check model support and batch pricing"
    Before sending batches, review the provider's official pricing page for supported models and batch pricing details.

The Batch API docs for Vertex can be found on the following URL:
--8<-- "docs/providers/_urls/vertex.md"

## Example Usage

!!! note "API key required"
    Set `VERTEX_API_KEY` in `.env` or ensure it is already loaded in your environment variables before running batches.

Here's an example showing how to use `batchling` with Vertex:

```py title="vertex_example.py"
--8<-- "examples/providers/vertex_example.py"
```
