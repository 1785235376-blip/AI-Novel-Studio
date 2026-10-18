"""Remove only exact synthetic fixture residues observed in the failed check.

This is evidence-specific test cleanup, not a product migration or repair.
"""
import hashlib, json, os
from pathlib import Path
import psycopg
proof = json.loads(Path('docs/delivery/v2-development/graph-local-reuse-integration-postgres-cleanup.json').read_text())
scopes = {'w-67292efe668a418f90b73eb1ed20bfa0', 'w-c7ce88a3dd2546f4aef3c41aaae69ab8', 'w-5ef0f76d4ccc494a8594f0a8871d1180', 'w-37d2c1fb5945415f9cec6912e26bf512', 'w-13cb1ebc03e34a7a8bc3f890daae63e2', 'w-a4676a6da2e64f7ab7f03565c223b4fe', 'w-ce3af6d37dfd4a47a6699c38596937d0', 'w-578bfe9a8cf64123883ae3dc3de1b750'}
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
    for t,count in (('authorization_audit_events',26),('workspace_memberships',16),('users',16),('workspaces',8)):
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
Path('docs/delivery/v2-development/graph-owned-fixture-cleanup-proof.json').write_text(json.dumps({'identity':list(identity),'removed_exact_synthetic_rows':removed,'pre_test_hash_multisets_restored':True},indent=2)+'\n')
print(json.dumps({'removed':removed,'pre_test_hash_multisets_restored':True}))
