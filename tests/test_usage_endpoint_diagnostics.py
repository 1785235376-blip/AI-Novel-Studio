import asyncio
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from usage_endpoint_diagnostics import observe_endpoint, install_endpoint_observers
from app.creative.asset_usage_budget import UsageReadBudget, UsageBudgetError


def test_result_identity_and_arguments_unchanged():
    expected = object(); events = []
    def original(a, *, b):
        assert a == 1 and b == 2
        return expected
    wrapped = observe_endpoint(original, events.append, lambda: None)
    assert wrapped(1, b=2) is expected
    assert events[0]['errors'] == []


@pytest.mark.parametrize('exception', [ValueError('secret/path/token'), RuntimeError('STUDIO_SAFE_CODE'), asyncio.CancelledError()])
def test_original_exception_identity_and_safe_messages(exception):
    events = []
    def original():
        raise exception
    with pytest.raises(type(exception)) as caught:
        observe_endpoint(original, events.append, lambda: None)()
    assert caught.value is exception
    assert 'secret/path/token' not in str(events)


def test_suppressed_chain_and_deterministic_deadline_diagnostic():
    budget = UsageReadBudget(); budget.deadline = 0
    events = []
    def original():
        try:
            budget.check()
        except UsageBudgetError:
            raise HTTPException(409, {'code': 'STUDIO_ASSET_USAGE_UNAVAILABLE'}) from None
    with pytest.raises(HTTPException):
        observe_endpoint(original, events.append, lambda: budget)()
    errors = events[0]['errors']
    assert [row['type'] for row in errors] == ['HTTPException', 'UsageBudgetError']
    assert errors[0]['code'] == 'STUDIO_ASSET_USAGE_UNAVAILABLE'
    assert any(frame['function'] == 'check' for frame in errors[1]['frames'])
    assert events[0]['budget_elapsed'] > budget.MAX_SECONDS
    assert budget.reads == 0 and budget.read_bytes == 0


def test_emitter_failure_does_not_change_result_or_error():
    def fail(_): raise OSError('unavailable log')
    expected = object()
    assert observe_endpoint(lambda: expected, fail, lambda: None)() is expected
    exception = ValueError('STUDIO_SAME_ERROR')
    def original(): raise exception
    with pytest.raises(ValueError) as caught:
        observe_endpoint(original, fail, lambda: None)()
    assert caught.value is exception


def test_nested_router_install_once_and_unrelated_untouched():
    def saved_asset_usages(): return 1
    def other(): return 2
    target = SimpleNamespace(dependant=SimpleNamespace(call=saved_asset_usages), endpoint=saved_asset_usages)
    unrelated = SimpleNamespace(dependant=SimpleNamespace(call=other), endpoint=other)
    child = SimpleNamespace(routes=[target, unrelated])
    root = SimpleNamespace(routes=[SimpleNamespace(original_router=child), SimpleNamespace(original_router=child)])
    events=[]
    count=install_endpoint_observers(root, lambda f: observe_endpoint(f, events.append, lambda: None))
    assert count == 1
    assert target.endpoint is target.dependant.call
    assert target.endpoint() == 1 and len(events) == 1
    assert unrelated.endpoint is other


def test_broken_exception_string_does_not_mask_original():
    class Broken(ValueError):
        def __str__(self): raise OSError('no string')
    original_error = Broken()
    def original(): raise original_error
    with pytest.raises(Broken) as caught:
        observe_endpoint(original, lambda event: None, lambda: None)()
    assert caught.value is original_error


def test_uppercase_arbitrary_message_is_not_a_code():
    events=[]
    def original(): raise ValueError('PRIVATE_PASSWORD')
    with pytest.raises(ValueError):
        observe_endpoint(original, events.append, lambda: None)()
    assert events[0]['errors'][0]['code'] is None


def test_clock_failure_does_not_prevent_original_call():
    expected=object()
    def fail(): raise RuntimeError('clock diagnostic unavailable')
    assert observe_endpoint(lambda: expected, lambda event: None, lambda: None, clock=fail)() is expected
