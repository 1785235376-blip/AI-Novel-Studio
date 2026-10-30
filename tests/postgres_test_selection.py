"""Explicit test-only PostgreSQL selection; no discovery, secrets logging or I/O.

The caller must create a fresh synthetic database. A loopback address and test
name are shape validation, not proof that a database is fresh or safe to erase.
"""
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Mapping
from urllib.parse import urlsplit
import re

import pytest


@dataclass(frozen=True)
class PostgresTestInput:
    selected: bool
    url: str = field(repr=False)


_INPUT = pytest.StashKey[PostgresTestInput]()
_ERROR = ('Explicit TEST_POSTGRES_DATABASE_URL must identify a fresh synthetic '
          'ai_novel_studio_e2e_ database on literal 127.0.0.1; '
          'production DATABASE_URL and .env fallback are not accepted')


def capture_postgres_test_input(config: pytest.Config, environ: Mapping[str, str]) -> None:
    config.stash[_INPUT] = PostgresTestInput(
        environ.get('STORAGE_BACKEND', 'file').strip().lower() == 'postgres',
        environ.get('TEST_POSTGRES_DATABASE_URL', ''),
    )


def postgres_tests_selected(config: pytest.Config) -> bool:
    return config.stash[_INPUT].selected


def validate_postgres_test_url(value: str) -> str:
    """Validate without connecting or including supplied secrets in errors."""
    try:
        parsed = urlsplit(value)
        valid = (
            bool(value) and not any(char.isspace() or ord(char) < 32 for char in value)
            and parsed.scheme in {'postgresql', 'postgresql+psycopg'}
            and parsed.hostname == '127.0.0.1'
            and parsed.port is not None and 1 <= parsed.port <= 65535
            and re.fullmatch(r'/ai_novel_studio_e2e_[a-z0-9_-]{1,42}', parsed.path)
            and not parsed.query and not parsed.fragment
        )
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise ValueError(_ERROR) from None
    return value


def selected_postgres_test_url(config: pytest.Config, node: pytest.Item) -> str:
    captured = config.stash[_INPUT]
    if not node.get_closest_marker('postgres_backend_only'):
        pytest.fail('isolated_postgres_url requires postgres_backend_only marker', pytrace=False)
    if not captured.selected:
        pytest.skip('PostgreSQL test not selected; set STORAGE_BACKEND=postgres explicitly')
    try:
        return validate_postgres_test_url(captured.url)
    except ValueError:
        pytest.fail(_ERROR, pytrace=False)


@contextmanager
def scoped_postgres_bootstrap(settings, url: str | None):
    """Bind only a selected test's app bootstrap to its validated synthetic URL.

    No environment variables are restored or populated. Preserve the original
    settings value even if app import/setup fails before fixture yield.
    """
    if url is None:
        yield
        return
    validated = validate_postgres_test_url(url)
    original = settings.database_url
    try:
        object.__setattr__(settings, 'database_url', validated)
        yield
    finally:
        object.__setattr__(settings, 'database_url', original)
