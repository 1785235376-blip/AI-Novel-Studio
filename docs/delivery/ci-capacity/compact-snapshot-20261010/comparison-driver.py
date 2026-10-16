"""Compare opt-in compact snapshots with two existing immutable full snapshots."""
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib, io, json, subprocess, sys, time
from pathlib import Path
ROOT=Path.cwd().resolve()
sys.path.insert(0,str(ROOT))
from scripts.refresh_v2_staged_catalog import compact_snapshot, generate_catalog, OUTPUTS
A=ROOT.parent/'AI-Novel-Studio-cloud'
BASE=ROOT/'.runtime/ci-capacity/catalog-analysis/final'
sha=lambda b:hashlib.sha256(b).hexdigest()
reports=[]
for short in ('efca85593b86','b7e1605713fd'):
 receipt=A/f'docs/delivery/v2-development/catalog-{short}.json'
 ref=json.loads(receipt.read_text()); tree=ref['staged_tree']; full=Path(ref['cwd'])
 assert tree.startswith(short) and ref['exit_code']==0
 assert all(sha((full/n).read_bytes())==ref['sha256'][n] for n in OUTPUTS)
 folder=BASE/f'compact-{short}'; folder.mkdir()
 started=datetime.now(timezone.utc).isoformat(); start=time.monotonic()
 snapshot=compact_snapshot(ROOT,tree,folder); extracted=time.monotonic()-start
 assert not (folder/'docs/delivery').exists()
 generator=folder/'scripts/refresh_product_api_catalog.py'
 assert generator.read_bytes()==(full/'scripts/refresh_product_api_catalog.py').read_bytes()
 log=io.StringIO(); start=time.monotonic()
 with redirect_stdout(log): command, outputs=generate_catalog(folder,True)
 seconds=time.monotonic()-start
 (BASE/f'compact-{short}.log').write_text(log.getvalue())
 hashes={n:sha(v) for n,v in outputs.items()}
 same={n:hashes[n]==ref['sha256'][n] for n in OUTPUTS}
 unchanged=all(sha((full/n).read_bytes())==ref['sha256'][n] for n in OUTPUTS)
 assert unchanged
 origins=json.loads((folder/'.profile/catalog-import-origins.json').read_text())
 report={'status':'EQUIVALENT' if all(same.values()) else 'NOT_EQUIVALENT',
  'coverage_verdict':'NOT_EVALUATED','started_utc':started,'staged_tree':tree,
  'reference_receipt':str(receipt),'reference_receipt_sha256':sha(receipt.read_bytes()),
  'reference_snapshot':str(full),'candidate_snapshot':str(folder),
  'snapshot':snapshot,'materialization_seconds':round(extracted,3),'generator_seconds':round(seconds,3),
  'generator_sha256':sha(generator.read_bytes()),'generator_unchanged':True,
  'wrapper_sha256':sha((ROOT/'scripts/refresh_v2_staged_catalog.py').read_bytes()),
  'candidate_output_sha256':hashes,'reference_output_sha256':ref['sha256'],'byte_equivalent':same,
  'reference_outputs_unchanged':unchanged,'project_import_origins':origins,
  'project_import_origins_sha256':sha((folder/'.profile/catalog-import-origins.json').read_bytes()),
  'publication':'NOT_PERFORMED','limits':['One exact staged tree per comparison; future optional reads require review.',
   'No existing snapshot is deleted and no repository-root catalog is written.',
   'Catalog equivalence is not backend test or security acceptance.']}
 with (BASE/f'compact-{short}.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
 print(json.dumps({k:v for k,v in report.items() if k!='project_import_origins'},indent=2),flush=True)
 reports.append(report)
 if report['status']!='EQUIVALENT':raise SystemExit(1)
print('BOTH_STAGED_TREES_EQUIVALENT')
