# Exceptions: dry-run control-flow signal

`src/batchling/exceptions.py` defines public exceptions exposed by batchling.
Today the module contains one exception: `DryRunEarlyExit`.

## `DryRunEarlyExit`

`DryRunEarlyExit` is raised when dry-run mode intentionally exits before
returning a provider response for an intercepted request.

Stored fields:

- `source`
- `provider`
- `endpoint`
- `model`
- `batch_id`
- `custom_id`

The exception message includes these identifiers for diagnostics.

## Why it subclasses `BaseException`

`DryRunEarlyExit` derives from `BaseException` (not `Exception`) so it behaves
as a control-flow signal and is less likely to be swallowed by broad
`except Exception` handlers in user code or integration layers.

## Suppression behavior at context boundaries

`BatchingContext.__exit__` and `BatchingContext.__aexit__` suppress this
exception (`return True` for that exact type) so dry-run teardown can complete
cleanly without surfacing a traceback.

## Code reference

- `src/batchling/exceptions.py`
- `src/batchling/context.py`
- `src/batchling/api.py`
