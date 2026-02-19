"""
Persistent cache store for request-to-batch mappings.
"""

from __future__ import annotations

import os
import sqlite3
import typing as t
from dataclasses import dataclass
from pathlib import Path

CACHE_PATH_ENV_VAR = "BATCHLING_CACHE_PATH"


@dataclass(frozen=True)
class CacheEntry:
    """
    Cache row used to resume batch polling from an intercepted request.

    Parameters
    ----------
    request_hash : str
        Stable fingerprint for a request.
    provider : str
        Provider adapter name.
    endpoint : str
        Provider endpoint path.
    model : str
        Model key derived from queue partitioning.
    host : str
        Provider host used for polling.
    batch_id : str
        Provider batch identifier.
    custom_id : str
        Request identifier within the provider batch.
    created_at : float
        Unix timestamp when the cache row was created.
    """

    request_hash: str
    provider: str
    endpoint: str
    model: str
    host: str
    batch_id: str
    custom_id: str
    created_at: float


def resolve_cache_path(*, path: Path | None = None) -> Path:
    """
    Resolve cache database path.

    Parameters
    ----------
    path : Path | None, optional
        Explicit cache file path.

    Returns
    -------
    Path
        Resolved SQLite file path.
    """
    if path is not None:
        return path

    env_path = os.getenv(CACHE_PATH_ENV_VAR)
    if env_path:
        return Path(env_path).expanduser().resolve()

    return (Path.home() / ".cache" / "batchling" / "cache.sqlite3").expanduser().resolve()


class RequestCacheStore:
    """
    SQLite-backed persistent request cache.
    """

    def __init__(self, *, path: Path | None = None) -> None:
        """
        Initialize a cache store and create schema if needed.

        Parameters
        ----------
        path : Path | None, optional
            Optional explicit cache file path.
        """
        self._path = resolve_cache_path(path=path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    @property
    def path(self) -> Path:
        """
        Return the underlying SQLite database path.

        Returns
        -------
        Path
            Database file path.
        """
        return self._path

    def _connect(self) -> sqlite3.Connection:
        """
        Open a SQLite connection to the cache file.

        Returns
        -------
        sqlite3.Connection
            Open connection.
        """
        connection = sqlite3.connect(self._path.as_posix())
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_schema(self) -> None:
        """
        Create cache schema and indexes when missing.
        """
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS request_cache (
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
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_request_cache_created_at
                ON request_cache (created_at)
                """
            )
            connection.commit()

    @staticmethod
    def _row_to_entry(*, row: sqlite3.Row) -> CacheEntry:
        """
        Map one SQLite row to a cache entry.

        Parameters
        ----------
        row : sqlite3.Row
            Database row from ``request_cache``.

        Returns
        -------
        CacheEntry
            Parsed cache entry.
        """
        return CacheEntry(
            request_hash=str(row["request_hash"]),
            provider=str(row["provider"]),
            endpoint=str(row["endpoint"]),
            model=str(row["model"]),
            host=str(row["host"]),
            batch_id=str(row["batch_id"]),
            custom_id=str(row["custom_id"]),
            created_at=float(row["created_at"]),
        )

    @staticmethod
    def _entry_values(*, entry: CacheEntry) -> tuple[str, str, str, str, str, str, str, float]:
        """
        Convert cache entry to SQLite parameter tuple.

        Parameters
        ----------
        entry : CacheEntry
            Cache row model.

        Returns
        -------
        tuple[str, str, str, str, str, str, str, float]
            Tuple ordered for ``INSERT`` statements.
        """
        return (
            entry.request_hash,
            entry.provider,
            entry.endpoint,
            entry.model,
            entry.host,
            entry.batch_id,
            entry.custom_id,
            entry.created_at,
        )

    def get_by_hash(self, *, request_hash: str) -> CacheEntry | None:
        """
        Load one cache row by request hash.

        Parameters
        ----------
        request_hash : str
            Request fingerprint.

        Returns
        -------
        CacheEntry | None
            Matching row when found.
        """
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT request_hash, provider, endpoint, model, host, batch_id, custom_id, created_at
                FROM request_cache
                WHERE request_hash = ?
                """,
                (request_hash,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_entry(row=row)

    def upsert_many(self, *, entries: t.Sequence[CacheEntry]) -> int:
        """
        Insert or update multiple cache rows.

        Parameters
        ----------
        entries : typing.Sequence[CacheEntry]
            Rows to insert or replace.

        Returns
        -------
        int
            Number of rows affected.
        """
        if not entries:
            return 0

        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO request_cache (
                    request_hash, provider, endpoint, model, host, batch_id, custom_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(request_hash) DO UPDATE SET
                    provider=excluded.provider,
                    endpoint=excluded.endpoint,
                    model=excluded.model,
                    host=excluded.host,
                    batch_id=excluded.batch_id,
                    custom_id=excluded.custom_id,
                    created_at=excluded.created_at
                """,
                [self._entry_values(entry=entry) for entry in entries],
            )
            affected = connection.total_changes
            connection.commit()
        return affected

    def delete_older_than(self, *, min_created_at: float) -> int:
        """
        Delete rows older than the provided timestamp.

        Parameters
        ----------
        min_created_at : float
            Lower bound for retained rows (Unix timestamp).

        Returns
        -------
        int
            Number of deleted rows.
        """
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM request_cache WHERE created_at < ?",
                (min_created_at,),
            )
            deleted_count = cursor.rowcount if cursor.rowcount is not None else 0
            connection.commit()
        return deleted_count

    def delete_by_hashes(self, *, request_hashes: t.Iterable[str]) -> int:
        """
        Delete a set of cache rows by request hashes.

        Parameters
        ----------
        request_hashes : typing.Iterable[str]
            Hashes to delete.

        Returns
        -------
        int
            Number of deleted rows.
        """
        unique_hashes = tuple(dict.fromkeys(request_hashes))
        if not unique_hashes:
            return 0

        with self._connect() as connection:
            previous_changes = connection.total_changes
            connection.executemany(
                "DELETE FROM request_cache WHERE request_hash = ?",
                [(request_hash,) for request_hash in unique_hashes],
            )
            deleted_count = connection.total_changes - previous_changes
            connection.commit()
        return deleted_count
