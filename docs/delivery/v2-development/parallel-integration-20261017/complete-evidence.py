"""Bind independently frozen primary and reviewer evidence without modifying either."""
import hashlib,json,pathlib,subprocess
R=pathlib.Path.cwd(); E=R/'docs/delivery/v2-development'; D=E/'parallel-integration-20261017'; V=E/'parallel-integration-independent-20261017'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text())
primary=read(D/'evidence-index.json'); reviewer=read(V/'evidence-index.json')
assert primary['head']==reviewer['head']==subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
artifacts={}
for inventory in (primary['artifacts'],read(V/'artifact-hashes.json')):
    for p,h in inventory.items(): assert sha(R/p)==h,p
    artifacts.update(inventory)
for folder in (D,V):
    for p in folder.rglob('*'):
        if p.is_file() and p.name!='complete-index.json': artifacts[p.relative_to(R).as_posix()]=sha(p)
receipts={}
for p in sorted(E.glob('parallel-integration-*-r1.json')):
    rec=read(p)
    assert rec['head']==primary['head'] and rec['status']=='PASS' and rec['exit_code']==0,p
    assert rec['source_sha256']==rec['source_sha256_before']==reviewer['source_sha256'] and not rec['sources_changed_during_check'],p
    assert sha(R/rec['log'])==rec['log_sha256'],p
    artifacts[p.relative_to(R).as_posix()]=sha(p); artifacts[rec['log']]=rec['log_sha256']
    receipts[p.relative_to(R).as_posix()]={'sha256':sha(p),'log':rec['log'],'log_sha256':rec['log_sha256']}
assert len(receipts)==11,len(receipts)
for p,h in reviewer['source_sha256'].items(): assert sha(R/p)==h,p
frozen=read(D/'tree-before.json')['tracked_sha256']
assert frozen==read(D/'tree-after.json')['tracked_sha256']
for p,h in frozen.items(): assert sha(R/p)==h,p
for arc in primary['archives']['archives']: assert sha(R/arc['archive'])==arc['sha256'],arc['archive']
result={'status':'PASS_COMPLETE_SCOPED_INTEGRATION_CLOSURE','head':primary['head'],'tree':primary['tree'],'primary_index':{'path':(D/'evidence-index.json').relative_to(R).as_posix(),'sha256':sha(D/'evidence-index.json')},'independent_index':{'path':(V/'evidence-index.json').relative_to(R).as_posix(),'sha256':sha(V/'evidence-index.json')},'independent_report':{'path':(V/'review.md').relative_to(R).as_posix(),'sha256':sha(V/'review.md')},'source_path_count':len(reviewer['source_sha256']),'all_tracked_files_unchanged':len(frozen),'receipts':receipts,'artifacts':artifacts,'actual_archive_count':4,'primary_counts':{'backend_passed':811,'backend_pg_deselected':303,'frontend_passed':1076,'frontend_files':71,'public_passed':87},'independent_overlapping_counts':{'backend_passed':245,'backend_pg_deselected':117,'frontend_passed':146,'frontend_files':8},'known_listing_failures_unresolved_and_excluded':5,'counts_must_not_be_added':True,'global_green':False,'canonical_inventory':'PENDING_PARENT_OWNED_SEPARATE_RECONCILIATION'}
(D/'complete-index.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':result['status'],'receipt_count':len(receipts),'artifact_count':len(artifacts),'complete_index_sha256':sha(D/'complete-index.json')},indent=2))
