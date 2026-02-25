<!-- markdownlint-disable-file MD041 MD001 -->
We'd love you to contribute to batchling!

## Installation and Setup

Clone your fork and cd into the repo directory

```bash
git clone git@github.com:<your username>/batchling.git
cd batchling
```

Install `uv` (version 0.4.30 or later) and `pre-commit` or `prek`:

- [`uv` install docs](https://docs.astral.sh/uv/getting-started/installation/)
- [`pre-commit` install docs](https://pre-commit.com/#install)
- [`prek` install docs](https://prek.j178.dev/installation/)

To install `pre-commit` you can run the following command:

```bash
uv tool install pre-commit
```

To install `prek` you can run the following command:

```bash
uv tool install prek
```

Install `batchling`, all dependencies and pre-commit hooks

```bash
uv uv sync --frozen --all-extras --all-packages --group dev
```

Install pre-commits using either: `pre-commit install --install-hooks` or `prek install --install-hooks`

## Running Tests etc

To run tests, run:

```bash
uv run pytest
```

To run pre-commits (linting, formatting..), use either `prek run -a` or `pre-commit run -a`

## Documentation Changes

To run the documentation page locally, run:

```bash
uv run mkdocs serve
```
