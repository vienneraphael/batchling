# AGENTS.md

## Repository Expectations

- Document public utilities in `docs/` when you change behavior.
- Whenever you import typing, use: `import typing as t`
- Use python native type hinting whenever possible, e.g. `list[dict]`
- Always use named-arguments when calling functions or methods.
- Document function and methods using numpy-style docs.
- To install libraries to the project, use `uv add`

## Development workflows

- Run tests (using pytest) for every code change but not when changing code comments or documentation.
If the pytest command does not work due to missing imports, try activating the environment first with `source .venv/bin/activate`
- Run pre-commits (using `prek run -a`) for every code change including code comments or documentation.

pre-commits to check for:

- pre-commit-hooks/ruff-check/ruff-format: syntax/style related, they autofix most of the time
- markdownlint-cli: syntax/style related, does not autofix.
- ty-check: type hinting, does not autofix
- bandit/detect-secrets: security-related, does not autofix but can have false flags.
- complexipy: outputs a function complexity report. For high-complexity functions/methods, try to find a way to better organize the code for readability, if possible.
- skylos: finds dead code. Can have false positive but review each case and make a decision.

## Component index

- [API surface: `batchify` adapter](docs/architecture/api.md)
- [Batching engine: `Batcher` lifecycle](docs/architecture/core.md)
- [HTTP hooks: request interception](docs/architecture/hooks.md)
- [Proxy wrapper: `BatchingProxy`](docs/architecture/proxy.md)
- [Provider adapters: URL matching + response decoding](docs/architecture/providers.md)

## End-to-end flow (high level)

1. Callers wrap a function or client instance with `batchify`, which creates a `Batcher` and installs hooks.
2. `BatchingProxy` (or the function wrapper) activates a context variable holding the `Batcher`.
3. HTTP hooks intercept supported requests and enqueue them into the `Batcher`.
4. The `Batcher` batches pending requests, submits them, and resolves per-request futures.
5. Provider adapters normalize URLs and decode batch API results back into HTTP responses.

See the component pages above for detailed behavior and extension points.
