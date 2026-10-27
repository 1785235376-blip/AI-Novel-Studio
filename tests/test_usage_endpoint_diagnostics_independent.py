"""Independent diagnostic transparency and redaction checks, no business mocks."""
import asyncio
import pytest
from usage_endpoint_diagnostics import observe_endpoint, install_endpoint_observers


@pytest.mark.parametrize('secret', ['SECRET_TOKEN_ABC123', 'STUDIO_SECRET_TOKEN_ABC123'])
def test_uppercase_secret_is_not_a_code(secret):
    events = []
    error = RuntimeError(secret)
    def original(): raise error
    with pytest.raises(RuntimeError) as caught:
        observe_endpoint(original, events.append, lambda: None)()
    assert caught.value is error
    assert secret not in repr(events)


@pytest.mark.parametrize('stage', ['emit', 'budget'])
def test_observer_cancel_does_not_replace_success(stage):
    expected = object()
    def cancelled(*args): raise asyncio.CancelledError('observer only')
    emit = cancelled if stage == 'emit' else lambda event: None
    getter = cancelled if stage == 'budget' else lambda: None
    assert observe_endpoint(lambda: expected, emit, getter)() is expected


@pytest.mark.parametrize('stage', ['emit', 'budget'])
def test_observer_cancel_does_not_replace_original_error(stage):
    original_error = ValueError('original')
    def original(): raise original_error
    def cancelled(*args): raise asyncio.CancelledError('observer only')
    emit = cancelled if stage == 'emit' else lambda event: None
    getter = cancelled if stage == 'budget' else lambda: None
    with pytest.raises(ValueError) as caught:
        observe_endpoint(original, emit, getter)()
    assert caught.value is original_error


def test_hostile_diagnostic_property_preserves_error():
    class Hostile(ValueError):
        @property
        def detail(self): raise RuntimeError('diagnostic property failed')
    error = Hostile('not a code')
    def original(): raise error
    with pytest.raises(Hostile) as caught:
        observe_endpoint(original, lambda event: None, lambda: None)()
    assert caught.value is error


def test_original_cancel_identity_is_preserved_with_observer_failure():
    error = asyncio.CancelledError('original cancellation')
    def original(): raise error
    def emit(_): raise OSError('logger unavailable')
    with pytest.raises(asyncio.CancelledError) as caught:
        observe_endpoint(original, emit, lambda: None)()
    assert caught.value is error


def test_hostile_status_property_preserves_error():
    class Hostile(ValueError):
        @property
        def status_code(self): raise RuntimeError('diagnostic status failed')
    error = Hostile('not a code')
    def original(): raise error
    with pytest.raises(Hostile) as caught:
        observe_endpoint(original, lambda event: None, lambda: None)()
    assert caught.value is error


def test_diagnostic_clock_failure_does_not_skip_original():
    calls = []
    expected = object()
    def original():
        calls.append(1)
        return expected
    def clock(): raise OSError('diagnostic clock failed')
    assert observe_endpoint(original, lambda event: None, lambda: None, clock=clock)() is expected
    assert calls == [1]
