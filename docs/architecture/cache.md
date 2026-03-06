# Request Cache: persistent request-to-batch mappings

`src/batchling/cache.py` provides a small SQLite store that lets `Batcher`
resume polling for already-submitted requests instead of re-submitting them.

## Responsibilities

- Resolve and create the on-disk cache database path.
- Maintain a stable cache row model (`CacheEntry`).
- Persist and read request-hash mappings to provider batch metadata.
- Remove stale rows by age and invalidate specific hashes.

## Path resolution

Cache location resolution uses this precedence:

1. explicit `path` argument passed to `RequestCacheStore`
2. `BATCHLING_CACHE_PATH` (`CACHE_PATH_ENV_VAR`) environment variable
3. default path: `~/.cache/batchling/cache.sqlite3`

The parent directory is created automatically.

## Data model and schema

`CacheEntry` fields:

- `request_hash`
- `provider`
- `endpoint`
- `model`
- `host`
- `batch_id`
- `custom_id`
- `request_count`
- `created_at`

SQLite schema (`request_cache`):

- primary key: `request_hash`
- secondary index: `idx_request_cache_created_at` on `created_at`
- `request_count INTEGER NOT NULL DEFAULT 0`

Schema initialization keeps a permanent migration path:

- detect missing `request_count` via `PRAGMA table_info(request_cache)`
- `ALTER TABLE request_cache ADD COLUMN request_count ...`
- backfill `request_count` by grouped row count over
  `(provider, host, batch_id)`

## Store operations

- `get_by_hash(request_hash=...)` returns one `CacheEntry | None`
- `upsert_many(entries=...)` inserts or updates rows by `request_hash`
- `delete_older_than(min_created_at=...)` removes stale rows by timestamp
- `delete_by_hashes(request_hashes=...)` removes selected hashes

`upsert_many` and delete methods return affected/deleted row counts.

## Integration with core retention behavior

`Batcher` writes cache rows through `RequestCacheStore` after successful batch
submission, then performs retention cleanup using
`CACHE_RETENTION_SECONDS = 30 * 24 * 60 * 60` from `src/batchling/core.py`.
When cache resume fails or returns stale results, core can invalidate request
hashes via targeted deletes.

## Code reference

- `src/batchling/cache.py`
- `src/batchling/core.py`
