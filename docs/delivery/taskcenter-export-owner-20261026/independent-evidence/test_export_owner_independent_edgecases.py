"""Independent serialized-value/lifecycle namespace regression probes."""
import pytest
from test_export_owner_independent_process import owner,seed_terminal


@pytest.mark.parametrize('before_value,after_value',[(True,1),(1,1.0)])
def test_json_distinct_selected_row_changes_nonce(owner,before_value,after_value):
    row=seed_terminal(owner);row['private_snapshot']={'value':before_value};owner._write({'terminal':row})
    observed=owner.binding_observation(['terminal'])
    row['private_snapshot']['value']=after_value;owner._write({'terminal':row})
    assert owner.binding_observation(['terminal'])!=observed


def test_internal_metadata_namespace_cannot_be_selected_as_a_job(owner):
    seed_terminal(owner)
    with pytest.raises(ValueError):owner.binding_observation(['_export_lifecycle_v1'])


@pytest.mark.parametrize('kind',['managed','legacy','missing'])
def test_readers_do_not_create_lockfiles_or_provision_evidence(owner,kind):
    import json,shutil
    if kind!='missing':
        row=seed_terminal(owner)
        if kind=='legacy':owner.path.write_text(json.dumps({'terminal':row}))
    locks=owner.path.parent/'.workspace-mutation-locks'
    if locks.exists():shutil.rmtree(locks)
    before={str(p.relative_to(owner.path.parent)):p.read_bytes() for p in owner.path.parent.rglob('*') if p.is_file()}
    if kind=='managed':owner.binding_observation(['terminal'])
    else:
        with pytest.raises(ValueError):owner.binding_observation(['terminal'])
    if kind=='missing':
        with pytest.raises(FileNotFoundError):owner.get('terminal')
    else:owner.get('terminal')
    owner.list('book',permission_context={'mode':'local','novel_id':'book','actor_id':'a'})
    assert not locks.exists()
    assert {str(p.relative_to(owner.path.parent)):p.read_bytes() for p in owner.path.parent.rglob('*') if p.is_file()}==before
