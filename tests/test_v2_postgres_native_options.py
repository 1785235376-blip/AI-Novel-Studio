"""Original owned PostgreSQL runner uses the native platform's argument syntax."""
import shlex
import subprocess

import pytest

from scripts import run_v2_postgres_checks as runner


def fixed_arguments(port):
    return ["-h", "127.0.0.1", "-p", str(port), "-c", "shared_buffers=32MB",
            "-c", "max_connections=50", "-c", "timezone=UTC", "-c", "log_timezone=UTC"]


def test_windows_startup_omits_unix_socket_argument_and_uses_native_quoting(monkeypatch):
    calls = []
    native_quote = subprocess.list2cmdline

    def quote(arguments):
        calls.append(list(arguments))
        return native_quote(arguments)

    monkeypatch.setattr(runner.subprocess, "list2cmdline", quote)
    result = runner.postgres_start_options(55573, platform="win32")
    assert calls == [fixed_arguments(55573)]
    assert result == native_quote(fixed_arguments(55573))
    assert "-k" not in result and "''" not in result


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_posix_startup_keeps_an_actual_empty_socket_directory(platform):
    expected = fixed_arguments(55573)
    expected[4:4] = ["-k", ""]
    options = runner.postgres_start_options(55573, platform=platform)
    assert shlex.split(options) == expected
    assert "-k ''" in options


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_platform_default_selects_current_native_parser(monkeypatch, platform):
    monkeypatch.setattr(runner.sys, "platform", platform)
    assert runner.postgres_start_options(55573) == runner.postgres_start_options(55573, platform=platform)
