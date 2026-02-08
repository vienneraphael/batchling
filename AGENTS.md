# AGENTS.md

## Repository Expectations

- Document public utilities in `docs/` when you change behavior.
- Whenever you import typing, use: `import typing as t`
- Use python native type hinting whenever possible, e.g. `list[dict]`
- Always use named-arguments when calling functions or methods.
- Document function and methods using numpy-style docs.
- Run tests (using pytest) and pre-commits (using `prek run -a`) for every code change but not when changing code comments or documentation.
- To install libraries to the project, use `uv add`
