"""The private receipt hook preserves legacy outputs and actual call semantics."""
import pytest
from fastapi import HTTPException
from test_taskcenter_query_backend import CTX,TaskReader,service,tasks


@pytest.mark.parametrize('status',[403,404])
def test_observer_records_only_actual_selected_calls_and_legacy_output_unchanged(status):
    calls=[]
    def okay(ctx):calls.append('semantic_import');return []
    def denied(ctx):calls.append('exports');raise HTTPException(status,{'private':'synthetic'})
    def unselected(ctx):pytest.fail('unselected reader must not execute')
    a=TaskReader('semantic_import','imports','history',okay);b=TaskReader('exports','exports','history',denied);c=TaskReader('media','media','history',unselected)
    svc=service(a,b,c);selected=('semantic_import','exports')
    expected=tasks(svc,authorities=selected);assert calls==['semantic_import','exports'];calls.clear()
    receipts=[];actual=tasks(svc,authorities=selected,_read_observer=lambda reader,completed:receipts.append((reader,completed)))
    assert actual==expected and calls==['semantic_import','exports']
    assert len(receipts)==2 and receipts[0][0] is a and receipts[0][1] is True and receipts[1][0] is b and receipts[1][1] is False
    assert '_read_observer' not in actual and 'private' not in str(actual)


def test_observer_failure_is_not_disguised_as_source_unavailability():
    called=[]
    a=TaskReader('semantic_import','imports','history',lambda ctx:called.append('reader') or [])
    def broken(reader,completed):raise RuntimeError('synthetic observer failure')
    with pytest.raises(RuntimeError,match='synthetic observer failure'):tasks(service(a),authorities=('semantic_import',),_read_observer=broken)
    assert called==['reader']
