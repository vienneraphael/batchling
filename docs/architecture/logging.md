# Logging utilities: normalized and redacted log messages

`src/batchling/logging.py` centralizes package logging defaults and message
formatting helpers used across core/context/hooks.

## Responsibilities

- Configure default package logger level.
- Normalize event + context messages into a compact key/value format.
- Drop sensitive payload-like fields before formatting.
- Expose convenience wrappers per log level.

## Default logger setup

`setup_logging()` sets the `batchling` logger level to `WARNING`.
This establishes conservative defaults when users call `batchify()`.

## Message formatting contract

`_format_log_message(event=..., **context)` produces:

- base event text
- optional `"key=value"` context suffix joined by spaces
- final shape: `"event | key=value key2=value2"`

Context entries are included only when their values are not `None`.

## Redaction / field dropping

`_DROP_LOG_FIELDS` removes payload-like keys from formatted output, including:

- `body`, `content`, `data`, `files`, `headers`, `json`, `payload`
- `result_item`

This keeps logs focused on lifecycle/debug metadata and avoids leaking request
payloads or headers.

## Level helpers

- `log_debug(logger=..., event=..., **context)`
- `log_info(logger=..., event=..., **context)`
- `log_warning(logger=..., event=..., **context)`
- `log_error(logger=..., event=..., **context)`

Each helper routes through `_format_log_message(...)` before emitting.

## Code reference

- `src/batchling/logging.py`
- `src/batchling/api.py`
- `src/batchling/core.py`
- `src/batchling/context.py`
