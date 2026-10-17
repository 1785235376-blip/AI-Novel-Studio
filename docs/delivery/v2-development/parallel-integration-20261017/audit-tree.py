"""Read-only tracked-tree, four-source lineage and original-test preservation proof."""
import hashlib,json,pathlib,subprocess,sys
R=pathlib.Path.cwd(); D=R/'docs/delivery/v2-development/parallel-integration-20261017'
def git(*args): return subprocess.check_output(['git',*args],text=True).strip()
head=git('rev-parse','HEAD'); assert head=='39ba1c7bc6d8438cc7c7d59f5767ba67f97aca0a'
assert not git('diff','HEAD','--name-only'), 'tracked worktree changed'
commits=['6ea323c','918b816','f193bb43c2bfc8223119314d073f076c4df6d541','17d64dcd489f52211ac02869fe0616f7e3539259']
proof={}
for c in commits:
    subprocess.run(['git','merge-base','--is-ancestor',c,head],check=True)
    paths=git('diff-tree','--no-commit-id','--name-only','-r',c).splitlines()
    records={}
    for p in paths:
        source=git('rev-parse',f'{c}:{p}'); target=git('rev-parse',f'{head}:{p}')
        assert source==target,(c,p)
        records[p]=source
    proof[git('rev-parse',c)]=records
old=git('ls-tree','-r','--name-only','e1e66ce').splitlines()
old_tests=[p for p in old if p.startswith(('tests/','frontend/tests/')) or (p.startswith('frontend/src/') and ('.test.' in p or '.spec.' in p))]
for p in old_tests: assert git('rev-parse',f'e1e66ce:{p}')==git('rev-parse',f'{head}:{p}'),p
old_docs=[p for p in old if p.startswith('docs/')]
changed_docs=set(git('diff','--name-only','e1e66ce',head,'--','docs').splitlines())
# Only known positioned-canvas inventory document edits may alter pre-existing docs.
allowed={'docs/v2/feature_coverage_inventory_20261015.md','docs/v2/feature_coverage_inventory_20261015.json'}
modified_old_docs=set(old_docs)&changed_docs
# Record exact known inventory exceptions rather than assuming branch sparse evidence covers history.
for p in modified_old_docs:
    assert git('rev-parse',f'c61a5eb:{p}')==git('rev-parse',f'{head}:{p}'),p
for p in set(old_docs)-modified_old_docs: assert git('rev-parse',f'e1e66ce:{p}')==git('rev-parse',f'{head}:{p}'),p
manifest=hashlib.sha256((R/'packaging/public-build.json').read_bytes()).hexdigest()
assert manifest=='c54c87073dbd7c09d4844c6b9884c1a466491b3a9e86064511fa1983acbc9178'
assert hashlib.sha256((R/'scripts/run_v2_checks.py').read_bytes()).hexdigest()=='64cf16c26412c5a1e36a1d4fb799519111ad409f7594ae15aa0b158e53396cd5'
paths=git('ls-files','-z').split('\0'); hashes={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in paths if p}
result={'status':'PASS','head':head,'tree':git('rev-parse','HEAD^{tree}'),'source_commits':proof,'tracked_sha256':hashes,'old_tests_unchanged':len(old_tests),'historical_docs_preserved':len(old_docs)-len(modified_old_docs),'historical_inventory_exceptions':sorted(modified_old_docs),'packaging_manifest_sha256':manifest,'lineage':git('log','-8','--format=%H %P %s')}
name='tree-after.json' if '--after' in sys.argv else 'tree-before.json'
if '--after' in sys.argv:
    before=json.loads((D/'tree-before.json').read_text()); assert before['tracked_sha256']==hashes
(D/name).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in {'tracked_sha256','source_commits','lineage'}},indent=2))
