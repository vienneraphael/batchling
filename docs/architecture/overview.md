# Architecture Overview

```mermaid
flowchart TB
    subgraph Caller[Caller Code]
        app[Application or Client Code]
        batchify[batchify adapter]
    end

    subgraph Runtime[Runtime Context]
        proxy[BatchingContext]
        ctx[ContextVar: active Batcher]
    end

    subgraph Hooks[HTTP Hooks]
        intercept[Request Interception]
        enqueue[Enqueue Requests]
    end

    subgraph Engine[Batching Engine]
        batcher[Batcher lifecycle]
        pending[Pending Requests]
        submit[Submit Batch]
        resolve[Resolve Futures]
    end

    subgraph Providers[Provider Adapters]
        match[URL Matching]
        decode[Response Decoding]
    end

    app -->|calls wrapped function or client| batchify
    batchify -->|returns wrapper or context| app

    batchify -->|returns context for| proxy
    batchify -->|installs hooks and seeds| ctx
    proxy -->|activates| ctx

    ctx -->|scopes hooks to active batcher| intercept
    intercept -->|captures supported requests| enqueue
    enqueue -->|adds request to| pending
    pending -->|drains into| submit

    submit -->|select adapter by URL| match
    match -->|decode batch response| decode
    decode -->|resolve per-request futures| resolve
    resolve -->|returns results to caller| app
```

## Notes

1. `batchify` wraps a function or client instance and installs hooks.
2. `BatchingContext` activates the context variable that holds the active `Batcher`.
3. HTTP hooks capture supported requests and enqueue them into the `Batcher`.
4. The `Batcher` batches pending requests, submits them, and resolves per-request futures.
5. Provider adapters normalize URLs and decode batch results into responses.
