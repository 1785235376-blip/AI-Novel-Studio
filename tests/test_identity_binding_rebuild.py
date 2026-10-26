import json
import pytest
from app.repositories.file.identity import FileIdentityRepository
from app.trusted_sessions import TrustedSessionResolver
from app.actor_context import SessionContext


def seeded(tmp_path):
    repo=FileIdentityRepository(tmp_path)
    repo.save_user({'id':'u','status':'ACTIVE'})
    repo.save_membership({'id':'m','user_id':'u','workspace_id':'w','status':'ACTIVE'})
    return repo


def test_membership_aba_and_unrelated_row(tmp_path):
    r=seeded(tmp_path); first=r.binding_observation('u','w')
    r.save_user({'id':'other','status':'ACTIVE'})
    assert r.revalidate_binding('u','w',first)
    for status in ['INACTIVE','ACTIVE']:
        d=r._read();d['memberships'][0]['status']=status;r._write(d)
    assert not r.revalidate_binding('u','w',first)


def test_delete_recreate_and_instance_reopen(tmp_path):
    r=seeded(tmp_path); first=r.binding_observation('u','w')
    assert FileIdentityRepository(tmp_path).revalidate_binding('u','w',first)
    d=r._read(); member=d['memberships'].pop();r._write(d)
    r.save_membership(member)
    assert not r.revalidate_binding('u','w',first)


@pytest.mark.parametrize('legacy',[False,True])
def test_reserved_null_injection_and_no_legacy_migration(tmp_path,legacy):
    r=FileIdentityRepository(tmp_path)
    d={'users':[],'memberships':[]}
    if legacy:r.path.write_text(json.dumps(d))
    before=r.path.read_bytes() if r.path.exists() else None
    with pytest.raises(ValueError,match='owner-managed'):r._write({**d,r._LIFECYCLE:None})
    assert (r.path.read_bytes() if r.path.exists() else None)==before
    if legacy:
        r.save_user({'id':'u','status':'ACTIVE'})
        assert r._LIFECYCLE not in r._read()
        before=r.path.read_bytes()
        with pytest.raises(ValueError,match='UNSUPPORTED'):r.binding_observation('u','w')
        assert r.path.read_bytes()==before


def test_failed_write_keeps_original_evidence(tmp_path,monkeypatch):
    r=seeded(tmp_path);before=r.path.read_bytes();first=r.binding_observation('u','w')
    def fail(*a):raise OSError('fault')
    with monkeypatch.context() as m:
        m.setattr('app.repositories.file.identity.atomic_write',fail)
        with pytest.raises(OSError):r.update_membership_status('u','w','INACTIVE','later',False)
    assert r.path.read_bytes()==before
    assert r.revalidate_binding('u','w',first)


def test_session_aba_and_resolver_replacement():
    r=TrustedSessionResolver();s=SessionContext('sid','client','u','w');r.register('secret',s)
    first=r.binding_observation('secret');r.register('other',s)
    assert r.revalidate_binding('secret',first)
    r.revoke('secret');r.register('secret',s)
    assert not r.revalidate_binding('secret',first)
    other=TrustedSessionResolver();other.register('secret',s)
    assert other.binding_observation('secret')!=r.binding_observation('secret')
    assert 'secret' not in first


def test_existing_reserved_metadata_cannot_be_replaced_or_removed(tmp_path):
    r=seeded(tmp_path); before=r.path.read_bytes()
    for value in [None, {}, 'forged']:
        d=r._read();d[r._LIFECYCLE]=value
        with pytest.raises(ValueError,match='owner-managed'):r._write(d)
        assert r.path.read_bytes()==before
    d=r._read();d.pop(r._LIFECYCLE)
    with pytest.raises(ValueError,match='owner-managed'):r._write(d)
    assert r.path.read_bytes()==before
