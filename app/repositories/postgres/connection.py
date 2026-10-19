"""Bounded PostgreSQL connection establishment for repository/experimental access.

On Windows a PostgreSQL child can transiently fail to map the postmaster's shared
memory region (server log: "could not reserve shared memory region (...) for child
...: error code 487"). A client connect without a deadline then waits inside
libpq's select loop; because repository connections are opened from synchronous
code paths (including async request handlers), that can freeze the whole event
loop indefinitely - the D-07 hang class.

Every direct psycopg connection therefore carries:

* a bounded connect deadline (POSTGRES_CONNECT_TIMEOUT_SECONDS, default 10s);
* a bounded retry for transient OperationalError during *establishment*
  (POSTGRES_CONNECT_ATTEMPTS, default 3, 0.25s linear backoff).

Only connection establishment is retried. Query, transaction, integrity and
authorization errors are surfaced unchanged and never retried. When every attempt
fails the original OperationalError is re-raised.
"""
from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager

import psycopg

DEFAULT_CONNECT_TIMEOUT_SECONDS = 10.0
MIN_CONNECT_TIMEOUT_SECONDS = 2.0
MAX_CONNECT_TIMEOUT_SECONDS = 120.0
DEFAULT_CONNECT_ATTEMPTS = 3
MAX_CONNECT_ATTEMPTS = 5
RETRY_BACKOFF_SECONDS = 0.25

_logger = logging.getLogger(__name__)


def connect_timeout_seconds() -> float:
    """Return the configured bounded connect deadline in seconds."""
    raw = os.getenv("POSTGRES_CONNECT_TIMEOUT_SECONDS", "").strip()
    try:
        value = float(raw) if raw else DEFAULT_CONNECT_TIMEOUT_SECONDS
    except ValueError:
        return DEFAULT_CONNECT_TIMEOUT_SECONDS
    if not MIN_CONNECT_TIMEOUT_SECONDS <= value <= MAX_CONNECT_TIMEOUT_SECONDS:
        return DEFAULT_CONNECT_TIMEOUT_SECONDS
    return value


def connect_timeout() -> int:
    """Return the libpq-compatible integer connect deadline in seconds."""
    return max(2, int(round(connect_timeout_seconds())))


def connect_attempts() -> int:
    """Return the bounded number of connection-establishment attempts."""
    raw = os.getenv("POSTGRES_CONNECT_ATTEMPTS", "").strip()
    try:
        value = int(raw) if raw else DEFAULT_CONNECT_ATTEMPTS
    except ValueError:
        return DEFAULT_CONNECT_ATTEMPTS
    return value if 1 <= value <= MAX_CONNECT_ATTEMPTS else DEFAULT_CONNECT_ATTEMPTS


def normalize_dsn(url: str) -> str:
    """Convert a SQLAlchemy driver URL to a plain psycopg DSN."""
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def connect(url: str, *, options: str = "-c timezone=UTC") -> psycopg.Connection:
    """Open one owned PostgreSQL connection with a deadline and bounded retries."""
    attempts = connect_attempts()
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return psycopg.connect(normalize_dsn(url), options=options,
                                   connect_timeout=connect_timeout())
        except psycopg.OperationalError as exc:
            last_error = exc
            if attempt < attempts:
                _logger.warning(
                    "PostgreSQL connection attempt %s/%s failed (%s); retrying within the bounded budget",
                    attempt, attempts, type(exc).__name__)
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    assert last_error is not None
    raise last_error


@contextmanager
def pooled_connection(engine):
    """Borrow a pooled DBAPI connection for one repository operation.

    Repository connection factories used to open a brand-new PostgreSQL
    connection for every call. A single local-interop test opened more than 1200
    connections; each Windows connection costs about 0.1 s, so synchronous
    authorization inside an async streaming guard blocked the event loop and the
    peer transport timed out (D-07). Reuse the existing SQLAlchemy pool instead.

    Transaction semantics match the psycopg connection context manager the
    repository layer used before pooling: a clean block commits, a raised block
    rolls back. Preserving that is required because original write paths relied on
    the implicit commit-on-exit; returning the connection without committing would
    silently discard those writes. The connection is always returned to the pool.
    """
    fairy = engine.raw_connection()
    connection = fairy.driver_connection
    try:
        yield connection
    except BaseException:
        try:
            connection.rollback()
        except Exception:
            connection.close()
        raise
    else:
        try:
            connection.commit()
        except Exception:
            try:
                connection.rollback()
            except Exception:
                pass
            raise
    finally:
        fairy.close()
