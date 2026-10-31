"""Preserve the original writer's accepted JSON-serializable value domain."""
from test_export_owner_independent_process import owner,seed_terminal


def test_existing_row_accepts_nested_mixed_json_object_keys(owner):
    row=seed_terminal(owner)
    row['private_snapshot']={1:'integer-key','name':'text-key'}
    owner._write({'terminal':row})
    before=owner.binding_observation(['terminal'])
    # The original json.dumps writer accepts this again; canonical comparison
    # must not narrow that contract merely because an existing row is compared.
    owner._write({'terminal':row})
    assert owner.get('terminal')['private_snapshot']=={'1':'integer-key','name':'text-key'}
    assert owner.binding_observation(['terminal'])==before
