import hashlib, json, os, subprocess, sys
from pathlib import Path
import psycopg

def snapshot():
    with psycopg.connect(os.environ['TEST_POSTGRES_DATABASE_URL']) as c:
        identity=c.execute("SELECT current_database(), (SELECT oid FROM pg_database WHERE datname=current_database()), current_setting('server_encoding'), version()").fetchone()
        assert identity[1] == 16384 and identity[2] == 'UTF8', identity
        rows={table:sorted(r[0] for r in c.execute('SELECT row_to_json(t)::text FROM '+table+' t').fetchall()) for table in ('novels','experimental_scope_documents','generation_jobs','chapters','characters','workspaces','project_workspaces','storylines','storyline_branches','users','workspace_memberships','domain_role_assignments','permission_assignments','authorization_audit_events')}
        return {'identity':list(identity),'row_sha256':{t:[hashlib.sha256(v.encode()).hexdigest() for v in values] for t,values in rows.items()}}
before=snapshot()
command=[sys.executable,'-m','pytest','tests/test_comic_page_archive.py','tests/test_comic_publication.py::test_six_full_pages_order_checksum_and_no_mutation','tests/test_comic_publication.py::test_guard_revoked_after_archive_before_bytes','tests/test_comic_publication_pdf.py::test_actual_ordered_raster_pdf_dimensions_receipt_and_no_mutation','tests/test_comic_publication_pdf.py::test_current_source_is_rechecked_after_pdf_serialization','tests/test_comic_publication_layers.py','tests/test_comic_publication_pdf.py::test_cjk_bubbles_flatten_to_original_exact_pixels','-m','postgres_backend_only','-p','no:cacheprovider','--basetemp=.runtime/v2-checks/comic-page-archive-integration-postgres/pytest','-q']
result=subprocess.run(command, timeout=600)
after=snapshot()
proof={'command':command,'exit_code':result.returncode,'before':before,'after':after,'exact_row_hashes_equal':before==after}
Path('docs/delivery/v2-development/comic-page-archive-integration-postgres-cleanup.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({'exit_code':result.returncode,'exact_row_hashes_equal':before==after}))
assert before==after,'Owned test persistence changed; inspect exact fixture ownership before cleanup'
sys.exit(result.returncode)
