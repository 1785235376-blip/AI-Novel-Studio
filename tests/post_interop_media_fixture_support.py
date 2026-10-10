"""Continuation profile marks around the unchanged original media rig body.

The historical fixture retains its original opt-in skip behavior. New tests
must instead let tests/conftest.py produce the canonical opposite-profile
setup skip. The PostgreSQL lane still requires its original real-database gate.
"""
import inspect

import pytest
import test_r3_media_support as _original_media_support


@pytest.fixture(params=[
    pytest.param('file', marks=pytest.mark.file_backend_only),
    pytest.param('postgres', marks=pytest.mark.postgres_backend_only),
])
def rig(request, tmp_path):
    # pytest 8.4.2 exposes the generator through its public __wrapped__ chain.
    # Delegate setup, yielded services and teardown; do not duplicate ownership.
    yield from inspect.unwrap(_original_media_support.rig)(request, tmp_path)
