"""Read-only aggregation applies scope before bounded pagination."""
from types import SimpleNamespace


def test_workflow_projection_filters_current_branch_before_definition_limit(monkeypatch):
    import app.experimental.api as experimental
    import app.workflow_api as workflows
    authorized = [{'id': f'other-{i}', 'branch_id': 'other'} for i in range(20)] + [{'id': 'current', 'branch_id': 'current'}]
    seen = []
    monkeypatch.setattr(workflows, 'workflows', lambda **_: {'items': authorized})
    def runs(workflow_id, x_session_token):
        seen.append((workflow_id, x_session_token))
        return {'items': [{'id': 'running-task', 'novel_id': 'n', 'branch_id': 'current', 'status': 'RUNNING'}]}
    monkeypatch.setattr(workflows, 'runs', runs)
    result = experimental.read_legacy_workflow_tasks(SimpleNamespace(novel_id='n', branch='current', token='synthetic'))
    assert [row['id'] for row in result['items']] == ['running-task']
    assert seen == [('current', 'synthetic')]
    assert result['has_more'] is False


def test_workflow_projection_bounds_only_current_scope_and_reports_more(monkeypatch):
    import app.experimental.api as experimental
    import app.workflow_api as workflows
    monkeypatch.setattr(workflows, 'workflows', lambda **_: {'items': [{'id': str(i), 'branch_id': 'current'} for i in range(21)]})
    seen = []
    def runs(workflow_id, x_session_token):
        seen.append(workflow_id)
        return {'items': [{'id': 'job-' + workflow_id}]}
    monkeypatch.setattr(workflows, 'runs', runs)
    result = experimental.read_legacy_workflow_tasks(SimpleNamespace(novel_id='n', branch='current', token='synthetic'))
    assert len(seen) == 20 and result['has_more'] is True
