"""Remove only exact synthetic fixture residues observed in the failed check.

This is evidence-specific test cleanup, not a product migration or repair.
"""
import hashlib, json, os
from pathlib import Path
import psycopg
proof = json.loads(Path('docs/delivery/v2-development/comic-author-integration-postgres-cleanup.json').read_text())
scopes = {'w-f7983fbfb3cb444cb75d61879a52ead5', 'w-b8d265dc6d024ffd8ec08fe59ec8b46e'}
users = {prefix + wid[2:] for wid in scopes for prefix in ('lead-', 'viewer-')}
tables = proof['before']['row_sha256']
def snapshot(c):
    return {t: sorted(hashlib.sha256(r[0].encode()).hexdigest() for r in c.execute('SELECT row_to_json(t)::text FROM '+t+' t')) for t in tables}
# Prior snapshots sort raw rows before hashing; compare sorted hash multisets.
expected = {t: sorted(v) for t,v in proof['before']['row_sha256'].items()}
observed = {t: sorted(v) for t,v in proof['after']['row_sha256'].items()}
removed = {}
with psycopg.connect(os.environ['TEST_POSTGRES_DATABASE_URL']) as c:
    identity = c.execute("SELECT current_database(), (SELECT oid FROM pg_database WHERE datname=current_database())").fetchone()
    assert identity == ('v2_recovered_ocr_export_20261018', 16384)
    assert snapshot(c) == observed, 'Database changed after exact residue observation'
    for t,count in (('authorization_audit_events',6),('workspace_memberships',4),('users',4),('workspaces',2)):
        additions = []
        old = set(proof['before']['row_sha256'][t])
        for raw, in c.execute('SELECT row_to_json(t)::text FROM '+t+' t'):
            if hashlib.sha256(raw.encode()).hexdigest() not in old:
                row=json.loads(raw)
                if t=='authorization_audit_events': assert row['payload']['scope']['workspace_id'] in scopes
                elif t=='workspace_memberships': assert row['workspace_id'] in scopes and row['user_id'] in users
                elif t=='users': assert row['id'] in users
                else: assert row['id'] in scopes and row['payload']['name']=='Mounted workspace'
                additions.append(row)
        assert len(additions)==count
        for row in additions:
            if t=='workspace_memberships': result=c.execute('DELETE FROM workspace_memberships WHERE workspace_id=%s AND user_id=%s',(row['workspace_id'],row['user_id']))
            else: result=c.execute('DELETE FROM '+t+' WHERE id=%s',(row['id'],))
            assert result.rowcount==1
        removed[t]=len(additions)
    assert snapshot(c)==expected, 'Cleanup would not restore exact pre-test rows; rollback'
Path('docs/delivery/v2-development/comic-author-owned-fixture-cleanup-proof.json').write_text(json.dumps({'identity':list(identity),'removed_exact_synthetic_rows':removed,'pre_test_hash_multisets_restored':True},indent=2)+'\n')
print(json.dumps({'removed':removed,'pre_test_hash_multisets_restored':True}))
