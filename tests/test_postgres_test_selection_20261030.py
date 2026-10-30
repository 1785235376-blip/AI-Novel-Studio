"""No-database safety checks for explicit PostgreSQL test input selection."""
from types import SimpleNamespace
import socket

import pytest

from postgres_test_selection import (
    PostgresTestInput, capture_postgres_test_input, selected_postgres_test_url,
    validate_postgres_test_url,
)

SAFE = 'postgresql://synthetic:never-use-this-password@127.0.0.1:55432/ai_novel_studio_e2e_fixture'


@pytest.fixture(autouse=True)
def no_connections(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('This test must never connect to any database or network')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    import psycopg
    monkeypatch.setattr(psycopg, 'connect', forbidden)


def selected(environ, *, marked=True):
    config = SimpleNamespace(stash=pytest.Stash())
    capture_postgres_test_input(config, environ)
    node = SimpleNamespace(get_closest_marker=lambda name: marked)
    return config, node


@pytest.mark.parametrize('scheme', ['postgresql', 'postgresql+psycopg'])
def test_explicit_test_url_survives_environment_clear_without_repopulating_it(scheme):
    url = SAFE.replace('postgresql:', scheme + ':')
    env = {'STORAGE_BACKEND': 'postgres', 'TEST_POSTGRES_DATABASE_URL': url,
           'DATABASE_URL': 'production-not-selected', 'E2E_DATABASE_URL': 'also-not-selected'}
    config, node = selected(env)
    env.clear()  # restore_global_settings intentionally removes these values.
    assert selected_postgres_test_url(config, node) == url
    assert env == {}


@pytest.mark.parametrize('url', [
    '', 'postgresql://secret@127.0.0.1:55432/production',
    SAFE.replace('127.0.0.1', 'localhost'), SAFE.replace('127.0.0.1', '192.0.2.1'),
    SAFE.replace('127.0.0.1', '[::1]'), SAFE.replace(':55432', ''),
    SAFE.replace(':55432', ':bad'), SAFE.replace(':55432', ':65536'),
    SAFE.replace(':55432', ':0'), SAFE.replace('postgresql:', 'mysql:'),
    SAFE + '?host=remote', SAFE + '#secret-fragment', ' ' + SAFE, SAFE + '\n',
    SAFE.replace('_fixture', '_'), SAFE.replace('_fixture', '_a' * 43),
    SAFE.replace('_fixture', '_fixture/other'),
])
def test_invalid_input_fails_without_echoing_credentials(url):
    config, node = selected({'STORAGE_BACKEND': 'postgres', 'TEST_POSTGRES_DATABASE_URL': url})
    with pytest.raises(pytest.fail.Exception) as failure:
        selected_postgres_test_url(config, node)
    assert 'never-use-this-password' not in str(failure.value)
    assert 'secret' not in str(failure.value)
    assert 'TEST_POSTGRES_DATABASE_URL' in str(failure.value)


def test_production_or_dotenv_values_cannot_substitute_for_explicit_test_input(tmp_path, monkeypatch):
    (tmp_path / '.env').write_text('TEST_POSTGRES_DATABASE_URL=' + SAFE + '\n')
    monkeypatch.chdir(tmp_path)
    config, node = selected({'STORAGE_BACKEND': 'postgres', 'DATABASE_URL': SAFE,
                             'E2E_DATABASE_URL': SAFE})
    with pytest.raises(pytest.fail.Exception):
        selected_postgres_test_url(config, node)


def test_file_selection_does_not_validate_or_use_database_input():
    config, node = selected({'STORAGE_BACKEND': 'file', 'TEST_POSTGRES_DATABASE_URL': 'invalid'})
    with pytest.raises(pytest.skip.Exception):
        selected_postgres_test_url(config, node)


def test_missing_backend_does_not_opt_in_even_with_test_url():
    config, node = selected({'TEST_POSTGRES_DATABASE_URL': SAFE})
    with pytest.raises(pytest.skip.Exception):
        selected_postgres_test_url(config, node)


def test_fixture_refuses_unmarked_consumer():
    config, node = selected({'STORAGE_BACKEND': 'postgres', 'TEST_POSTGRES_DATABASE_URL': SAFE}, marked=False)
    with pytest.raises(pytest.fail.Exception, match='requires postgres_backend_only'):
        selected_postgres_test_url(config, node)


def test_snapshot_representation_does_not_expose_url():
    assert SAFE not in repr(PostgresTestInput(True, SAFE))
    assert 'never-use-this-password' not in repr(PostgresTestInput(True, SAFE))


@pytest.mark.parametrize('raises', [False, True])
def test_scoped_bootstrap_restores_settings_even_on_import_failure(raises):
    from postgres_test_selection import scoped_postgres_bootstrap
    settings = SimpleNamespace(database_url='original-unselected-value')
    try:
        with scoped_postgres_bootstrap(settings, SAFE):
            assert settings.database_url == SAFE
            if raises:
                raise RuntimeError('synthetic import failure')
    except RuntimeError:
        assert raises
    assert settings.database_url == 'original-unselected-value'


def test_invalid_bootstrap_never_enters_app_import_scope():
    from postgres_test_selection import scoped_postgres_bootstrap
    settings = SimpleNamespace(database_url='original-unselected-value')
    entered = False
    with pytest.raises(ValueError):
        with scoped_postgres_bootstrap(settings, 'postgresql://secret@remote/production'):
            entered = True
    assert not entered
    assert settings.database_url == 'original-unselected-value'


def test_unselected_bootstrap_keeps_file_settings():
    from postgres_test_selection import scoped_postgres_bootstrap
    settings = SimpleNamespace(database_url='original-unselected-value')
    with scoped_postgres_bootstrap(settings, None):
        assert settings.database_url == 'original-unselected-value'
    assert settings.database_url == 'original-unselected-value'


def test_backend_selection_is_not_changed_by_later_dotenv_or_environment_values():
    from postgres_test_selection import postgres_tests_selected
    env = {}
    config, _ = selected(env)
    env.update(STORAGE_BACKEND='postgres', TEST_POSTGRES_DATABASE_URL=SAFE)
    assert postgres_tests_selected(config) is False
