# AGENTS.md

## Repository Expectations

- use ripgrep (through `rg` command) in place of grep.
- Document public utilities in `docs/` when you change behavior.
- Whenever you import typing, use: `import typing as t`
- Use as much typing as possible on your function definitions
- Use python native type hinting whenever possible, e.g. `list[dict]`
- Always use named-arguments when calling functions or methods.
- Document function and methods using numpy-style docs.
- To install libraries to the project, use `uv add`

## Development workflows

- When asking me questions in Plan Mode, give me extensive information to make an informed choice: define the impact of each invidual choice and give context about the question before asking it.

- Run tests (using pytest) for every code change but not when changing code comments or documentation-related stuff.
If the pytest command does not work due to missing imports, try activating the environment first with `source .venv/bin/activate`
- Run pre-commits (using `prek run -a`) for every code change including code comments or documentation.

pre-commits to check for:

- pre-commit-hooks/ruff-check/ruff-format: syntax/style related, they autofix most of the time
- markdownlint-cli: syntax/style related, does not autofix.
- ty-check: type hinting, does not autofix
- bandit/detect-secrets: security-related, does not autofix but can have false flags.
<!-- - complexipy: outputs a function complexity report. For high-complexity functions/methods, try to find a way to better organize the code for readability, if possible.
- skylos: finds dead code. Can have false positive but review each case and make a decision. -->

- When updating static docs, always rebuild in strict mode after your changes. In that case, no need to run tests with pytest.

- When pursuing a complex task, break it down as simpler tasks and make atomic commits to facilitate code review.
Do the atomic commits yourself using `git commit -m`.
When the task is done, include atomic commit names in your recap to streamline your approach.
Always follow good practices for atomic commits.

## Component index

- [API surface: `batchify` adapter](docs/architecture/api.md)
- [Batching engine: `Batcher` lifecycle](docs/architecture/core.md)
- [HTTP hooks: request interception](docs/architecture/hooks.md)
- [Async Context Manager: `BatchingContext`](docs/architecture/context.md)
- [Provider adapters: URL matching + response decoding](docs/architecture/providers.md)

## End-to-end flow (high level)

1. Callers wrap a function or client instance with `batchify`, which creates a `Batcher` and installs hooks.
2. `BatchingContext` activates a context variable holding the `Batcher` when its async context is entered.
3. HTTP hooks intercept supported requests and enqueue them into the `Batcher`.
4. The `Batcher` batches pending requests, submits them, and resolves per-request futures.
5. Provider adapters normalize URLs and decode batch API results back into HTTP responses.

See the component pages above for detailed behavior and extension points.

## Overall Coding Principles

Whenever asked to do something, strictly follow these principles in your actions.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:

- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

**Add later if needed:** Caching (when performance matters), validation (when bad data appears), merging (when requirement emerges).

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:

- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

```text
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant cl

Here is real-world code examples demonstrating the four principles. Each example shows what LLMs commonly do wrong and how to fix it.

---

### Anti-Patterns Summary

| Principle | Anti-Pattern | Fix |
| ----------- | ------------- | ----- |
| Think Before Coding | Silently assumes file format, fields, scope | List assumptions explicitly, ask for clarification |
| implicity First | Strategy pattern for single discount calculation | One function until complexity is actually needed |
| Surgical Changes | Reformats quotes, adds type hints while fixing bug | Only change lines that fix the reported issue |
| Goal-Driven | "I'll review and improve the code" | "Write test for bug X → make it pass → verify no regressions" |

### Key Insight

The "overcomplicated" examples aren't obviously wrong—they follow design patterns and best practices. The problem iming**: they add complexity before it's needed, which:

- Makes code harder to understand
- Introduces more bugs
- Takes longer to implement
- Harder to test

The "simple" versions are:

- Easier to understand
- Faster to implement
- Easier to test
- Can be refactored later when complexity is actually needed

**Good code is code that solves today's problem simply, not tomorrow's problem prematurely.**
