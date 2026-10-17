"""Freeze reviewed merged source only after parent's explicit release."""
import hashlib,json,pathlib,runpy,subprocess,sys
R=pathlib.Path.cwd(); D=R/'docs/delivery/v2-development/parallel-integration-wave2-20261017'
def git(*args): return subprocess.check_output(['git',*args],text=True).strip()
def tree(commit):
 out={}
 for row in subprocess.check_output(['git','ls-tree','-r','-z',commit]).decode().split('\0'):
  if row:
   metadata,path=row.split('\t',1); out[path]=metadata.split()[2]
 return out
assert len(sys.argv)==6,'usage: freeze-tree.py EXPECTED_HEAD DIRECTOR B07 COMIC STORAGE'
head,*commits=sys.argv[1:]; assert git('rev-parse','HEAD')==head
assert not git('diff','HEAD','--name-only'),'tracked edits before freeze'
assert not (D/'release-freeze.json').exists(),'do not overwrite a freeze'
current=tree(head); baseline=tree('d10b72c'); featureproof={}; changed_runtime=[]
for c in commits:
 subprocess.run(['git','merge-base','--is-ancestor',c,head],check=True)
 paths=git('diff-tree','--no-commit-id','--name-only','-r',c).splitlines(); source=tree(c)
 for p in paths:
  assert source.get(p)==current.get(p),(c,p,'merged blob differs')
  if p.startswith('app/') and p not in changed_runtime: changed_runtime.append(p)
 featureproof[git('rev-parse',c)]={p:source.get(p) for p in paths}
# Every pre-wave2 test and document remains exactly baseline, including reconciled inventories.
old_tests=[p for p in baseline if p.startswith(('tests/','frontend/tests/')) or p.startswith('frontend/src/') and ('.test.' in p or '.spec.' in p)]
old_docs=[p for p in baseline if p.startswith('docs/')]
for p in old_tests+old_docs: assert baseline[p]==current.get(p),('protected baseline',p)
for p in baseline:
 if p.startswith(('.github/','scripts/','local_interop_')) or p in {'AGENTS.md','pyproject.toml'}: assert baseline[p]==current.get(p),('protected infrastructure',p)
assert hashlib.sha256((R/'scripts/run_v2_checks.py').read_bytes()).hexdigest()=='64cf16c26412c5a1e36a1d4fb799519111ad409f7594ae15aa0b158e53396cd5'
manifest=json.loads((R/'packaging/public-build.json').read_text()); oldmanifest=json.loads(subprocess.check_output(['git','show','d10b72c:packaging/public-build.json']))
assert set(manifest['files'])-set(oldmanifest['files'])=={'app/creative/director_terminal_evidence.py'}
assert not set(oldmanifest['files'])-set(manifest['files'])
assert hashlib.sha256((R/'packaging/public-build.json').read_bytes()).hexdigest()=='353b92aff6116d873ea4402a1ef627e7899214b46ba823a9b4300ba75c5d0448'
tracked={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in current}
source=runpy.run_path(str(R/'scripts/run_v2_checks.py'))['source_snapshot'](R)
oldsource=json.loads((R/'docs/delivery/v2-development/parallel-integration-backend-r1.json').read_text())['source_sha256']; assert len(oldsource)==2600
added=sorted(set(source)-set(oldsource)); removed=sorted(set(oldsource)-set(source)); assert not removed
result={'status':'FROZEN_AFTER_PARENT_RELEASE','head':head,'tree':git('rev-parse','HEAD^{tree}'),'baseline':'d10b72c','source_commits':featureproof,'changed_runtime':changed_runtime,'tracked_sha256':tracked,'source_sha256':source,'baseline_source_count':len(oldsource),'source_additions':added,'source_removals':removed,'source_count':len(source),'protected_old_tests':len(old_tests),'protected_old_docs':len(old_docs),'manifest_sha256':hashlib.sha256((R/'packaging/public-build.json').read_bytes()).hexdigest(),'lineage':git('log','-12','--format=%H %P %s')}
(D/'release-freeze.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in {'source_commits','tracked_sha256','source_sha256','lineage'}},indent=2))
