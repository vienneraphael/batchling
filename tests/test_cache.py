"""Tests for request cache schema migration and request-count persistence."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from batchling.cache import CacheEntry, RequestCacheStore


def _create_legacy_cache_schema(*, path: Path) -> None:
    """
    Create pre-migration cache schema without the ``request_count`` column.

    Parameters
    ----------
    path : Path
        SQLite database path to initialize.
    """
    with sqlite3.connect(path.as_posix()) as connection:
        connection.execute(
            """
            CREATE TABLE request_cache (
                request_hash TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                model TEXT NOT NULL,
                host TEXT NOT NULL,
                batch_id TEXT NOT NULL,
                custom_id TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        connection.commit()


def test_initialize_schema_adds_request_count_column(tmp_path: Path) -> None:
    """
    Ensure fresh cache schema includes non-null ``request_count``.

    Parameters
    ----------
    tmp_path : Path
        Temporary test directory.
    """
    cache_path = tmp_path / "cache.sqlite3"
    _ = RequestCacheStore(path=cache_path)

    with sqlite3.connect(cache_path.as_posix()) as connection:
        columns = connection.execute("PRAGMA table_info(request_cache)").fetchall()

    by_name = {str(column[1]): column for column in columns}
    assert "request_count" in by_name
    request_count_column = by_name["request_count"]
    assert str(request_count_column[2]).upper() == "INTEGER"
    assert int(request_count_column[3]) == 1
    assert int(request_count_column[4]) == 0


def test_initialize_schema_migrates_and_backfills_request_count(tmp_path: Path) -> None:
    """
    Ensure migration adds request-count and backfills grouped batch totals.

    Parameters
    ----------
    tmp_path : Path
        Temporary test directory.
    """
    cache_path = tmp_path / "legacy-cache.sqlite3"
    _create_legacy_cache_schema(path=cache_path)

    with sqlite3.connect(cache_path.as_posix()) as connection:
        connection.executemany(
            """
            INSERT INTO request_cache (
                request_hash, provider, endpoint, model, host, batch_id, custom_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "hash-1",
                    "openai",
                    "/v1/chat/completions",
                    "model-a",
                    "api.openai.com",
                    "batch-1",
                    "custom-1",
                    1.0,
                ),
                (
                    "hash-2",
                    "openai",
                    "/v1/chat/completions",
                    "model-a",
                    "api.openai.com",
                    "batch-1",
                    "custom-2",
                    2.0,
                ),
                (
                    "hash-3",
                    "openai",
                    "/v1/chat/completions",
                    "model-a",
                    "api.openai.com",
                    "batch-2",
                    "custom-3",
                    3.0,
                ),
            ],
        )
        connection.commit()

    _ = RequestCacheStore(path=cache_path)
    with sqlite3.connect(cache_path.as_posix()) as connection:
        rows = connection.execute(
            "SELECT request_hash, request_count FROM request_cache ORDER BY request_hash"
        ).fetchall()

    assert rows == [("hash-1", 2), ("hash-2", 2), ("hash-3", 1)]


def test_upsert_and_get_by_hash_roundtrip_request_count(tmp_path: Path) -> None:
    """
    Ensure cache writes and reads preserve request-count values.

    Parameters
    ----------
    tmp_path : Path
        Temporary test directory.
    """
    cache_path = tmp_path / "roundtrip-cache.sqlite3"
    store = RequestCacheStore(path=cache_path)
    now = time.time()
    _ = store.upsert_many(
        entries=[
            CacheEntry(
                request_hash="hash-1",
                provider="openai",
                endpoint="/v1/chat/completions",
                model="model-a",
                host="api.openai.com",
                batch_id="batch-1",
                custom_id="custom-1",
                request_count=4,
                created_at=now,
            )
        ]
    )

    entry = store.get_by_hash(request_hash="hash-1")
    assert entry is not None
    assert entry.request_count == 4
