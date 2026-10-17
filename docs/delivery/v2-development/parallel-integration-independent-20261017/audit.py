import hashlib,json,pathlib,subprocess,tarfile,zipfile
R=pathlib.Path.cwd();D=R/'docs/delivery/v2-development/parallel-integration-independent-20261017';P=R/'docs/delivery/v2-development/parallel-integration-20261017'
def sha(data):return hashlib.sha256(data).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],text=True).strip()
assert git('rev-parse','HEAD')=='39ba1c7bc6d8438cc7c7d59f5767ba67f97aca0a'
assert not git('diff','HEAD','--name-only')
reference=json.loads((P/'tree-before.json').read_text())['tracked_sha256']
assert all(sha((R/p).read_bytes())==h for p,h in reference.items())
assert set(reference)==set(git('ls-files').splitlines())
receipts={};common=None
for label in ['origin-before','backend','ui','type','build','token','packaging','origin-after','independent-origin','independent-backend','independent-ui']:
 p=R/'docs/delivery/v2-development'/f'parallel-integration-{label}-r1.json';j=json.loads(p.read_text());m=j['source_sha256']
 assert j['status']=='PASS' and j['exit_code']==0 and not j['sources_changed_during_check']
 assert j['head']==git('rev-parse','HEAD') and m==j['source_sha256_before']
 assert all(sha((R/n).read_bytes())==h for n,h in m.items())
 assert sha((R/j['log']).read_bytes())==j['log_sha256']
 if common is None:common=m
 else: assert common==m
 receipts[label]={'receipt':str(p.relative_to(R)),'sha256':sha(p.read_bytes()),'log_sha256':j['log_sha256'],'command':j['command'],'status':j['status'],'source_count':len(m)}
archives=[]
for item in json.loads((P/'packaging-evidence/index.json').read_text())['archives']:
 a=R/item['archive'];h=sha(a.read_bytes());receipt=json.loads((a.parent.parent/(item['kind']+'-receipt.json')).read_text());assert h==item['sha256']==receipt['artifact_sha256']
 if item['kind']=='wheel':
  with zipfile.ZipFile(a) as z:
   assert len(z.namelist())==len(set(z.namelist()));payload={n:z.read(n) for n in z.namelist() if not n.endswith('/')}
 else:
  with tarfile.open(a) as z:
   ms=z.getmembers();assert len(ms)==len({m.name for m in ms});assert all(m.isfile() or m.isdir() for m in ms);payload={m.name:z.extractfile(m).read() for m in ms if m.isfile()}
 assert not any('studio_private_extensions' in n for n in payload)
 for row in receipt['files']:assert sha(payload[row['path']])==row['sha256']==sha((R/row['source_path']).read_bytes())
 assert all(n in {row['source_path'] for row in receipt['files']} for n in item['changed_modules'])
 archives.append({'path':item['archive'],'sha256':h,'source_rows_verified':len(receipt['files']),'payload_file_count':len(payload),'changed_modules':item['changed_modules']})
assert len(archives)==4
manifest=sha((R/'packaging/public-build.json').read_bytes());assert manifest=='c54c87073dbd7c09d4844c6b9884c1a466491b3a9e86064511fa1983acbc9178'
assert json.loads((R/'packaging/public-build.json').read_text())['files'].count('app/experimental/terminology_portability.py')==1
result={'status':'PASS_SCOPED_INDEPENDENT_COMBINED_REVIEW','head':git('rev-parse','HEAD'),'tree':git('rev-parse','HEAD^{tree}'),'full_tracked_files_unchanged':len(reference),'source_count':len(common),'source_sha256':common,'receipts':receipts,'archives':archives,'public_manifest_sha256':manifest,'original_runner_sha256':sha((R/'scripts/run_v2_checks.py').read_bytes()),'limits':['Five baseline Audio listing-error-precedence failures excluded, not resolved','No PostgreSQL, real browser, Windows/native, provider, hosted CI, release, or full V2 acceptance','Historical thin-worktree feature receipts prove their declared code/test scopes; full tracked-document preservation verified separately','No archive extraction, installation or product imports in independent archive audit']}
(D/'evidence-index.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in {'source_sha256','receipts','archives'}},indent=2))
