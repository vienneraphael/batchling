# Deferred Mode

Batch APIs were never meant to be run async initially (until I hacked them :p).

If you still want to run batches like an OG, deferred mode is there for you.

The deferred execution in `batchling` allow for a graceful exit of the polling once we've reached an idle state (I see you hitting Ctrl + C furiously).

The idle state is basically defined by "nothing happened except polling for X seconds" as a way to detect that we intercepted and sent every batch we had to.

The default idle time value is one minute (60 seconds).

## Usage

Deferred execution is meant to be used in several steps:

- You first run a deferred batch, wait for it to gracefully exit.

Whenever you get impatient or you have waited for 24 hours, come back and re-run the same script/command:

- if you re-run it using deferred execution, it means you just want to check once

- if you run it normally it will poll until it gets results (or you have to quit by Ctrl + C)

## Activating deferred execution

Deferred mode is activated by two parameters through the CLI/SDK:

- `deferred=True` and `deferred_idle_seconds=60` in the SDK

- `--deferred` and `--deferred-idle-seconds 60` in the CLI

## Next Steps

- See how [cache](./cache.md) is saved and for how long it is kept.

- See how [dry run](./dry-run.md) can help you plan that everything is ok before sending batches
