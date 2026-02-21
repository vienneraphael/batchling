# Overview

## Inference Providers

`batchling` is compatible with most providers exposing a Batch API.

Head over to the [list of supported providers](./providers.md) to see more details.

## Frameworks

By construction, `batchling` is supposed to be framework-agnostic, meaning that you can use batchling with any AI framework, as long as you call a supported provider from that framework.

As long as a framework build async requests on top of `httpx` or `aiohttp`, `batchling` will be compatible.

Still, we curated a [list of frameworks](./frameworks.md) that were carefully tested that we expose in our documentation.
