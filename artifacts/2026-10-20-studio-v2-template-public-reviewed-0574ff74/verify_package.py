"""Read-only verifier: python verify_package.py ARTIFACT_DIRECTORY RESTORED_GIT_DIRECTORY."""
from pathlib import Path, PurePosixPath
from collections import Counter
import hashlib, json, os, re, struct, subprocess, sys, zipfile

def check(condition, description):
    if not condition: raise RuntimeError(description)
def sha(data): return hashlib.sha256(data).hexdigest()
def blob(data): return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()

def main():
    folder=Path(sys.argv[1]).resolve();repo=Path(sys.argv[2]).resolve()
    env={k:v for k,v in os.environ.items() if k not in ['GIT_ALTERNATE_OBJECT_DIRECTORIES','GIT_OBJECT_DIRECTORY','GIT_DIR','GIT_WORK_TREE']}
    env.update(GIT_OPTIONAL_LOCKS='0',GIT_NO_REPLACE_OBJECTS='1')
    def git(*args):
        q=subprocess.run(['git','--git-dir='+str(repo),*args],capture_output=True,env=env)
        check(q.returncode==0,'git '+repr(args)+' '+q.stderr.decode(errors='replace'))
        return q.stdout
    def text(*args): return git(*args).decode('utf-8').strip()
    def obj(oid,typ): return git('cat-file',typ,oid)
    manifest=json.loads((folder/'MANIFEST.json').read_text(encoding='utf-8'))
    sums=(folder/'SHA256SUMS').read_text(encoding='utf-8').splitlines()
    actual_paths={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
    expected_paths=set()
    for line in sums:
        digest,name=line.split('  ',1);expected_paths.add(name)
        check(not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts,'Unsafe artifact path')
        check(sha((folder/name).read_bytes())==digest,'SHA256 mismatch: '+name)
    check(actual_paths==expected_paths|{'SHA256SUMS'},'Unexpected or missing artifact files')
    for x in manifest['payload_hashes']:
        data=(folder/x['path']).read_bytes()
        check(len(data)==x['bytes'] and sha(data)==x['sha256'] and blob(data)==x['git_blob'],'Payload receipt: '+x['path'])
    source=json.loads((folder/'source-files.json').read_text(encoding='utf-8'))
    objects=json.loads((folder/'introduced-objects.json').read_text(encoding='utf-8'))
    graph=json.loads((folder/'commit-graph.json').read_text(encoding='utf-8'))
    base=manifest['product_base'];tip=manifest['product_tip']
    check(not (repo/'objects/info/alternates').exists(),'Alternates are disallowed for this verification')
    check(not (repo/'shallow').exists(),'Shallow history is disallowed')
    check(text('rev-parse',tip+'^{tree}')==manifest['product_tree'],'Product tree differs')
    check(set(text('rev-list',base+'..'+tip).splitlines())==set(x['commit'] for x in graph),'Unexpected commits')
    for row in graph:
        raw=obj(row['commit'],'commit').decode('utf-8')
        check(re.findall(r'^parent (.*)$',raw,re.M)==row['parents'],'Commit parent mismatch')
        check(text('rev-parse',row['commit']+'^{tree}')==row['tree'],'Commit tree mismatch')
    added=set(x.split()[0] for x in text('rev-list','--objects',base+'..'+tip).splitlines())
    check(added==set(x['oid'] for x in objects),'Introduced object set differs')
    for row in objects:
        data=obj(row['oid'],row['type'])
        check(len(data)==row['bytes'] and sha(data)==row['sha256'],'Raw object mismatch')
        check(hashlib.sha1((row['type']+' '+str(len(data))+'\0').encode()+data).hexdigest()==row['oid'],'Git object ID mismatch')
    source_paths=set(x['path'] for x in source)
    check(set(text('diff','--name-only',base,tip).splitlines())==source_paths,'Changed source paths differ')
    with zipfile.ZipFile(folder/'source-delta.zip') as z:
        check(z.testzip() is None,'Source ZIP CRC')
        check(set(z.namelist())==source_paths,'Source ZIP entries differ')
        for row in source:
            data=z.read(row['path'])
            check(sha(data)==row['sha256'] and len(data)==row['bytes'] and blob(data)==row['oid'],'Source snapshot mismatch')
            check(text('rev-parse',tip+':'+row['path'])==row['oid'],'Final tree blob mismatch')
            check(obj(row['oid'],'blob')==data,'Git/source snapshot mismatch')
    source_hash_receipts=0
    with zipfile.ZipFile(folder/'evidence-exact.zip') as z:
        check(z.testzip() is None,'Evidence ZIP CRC')
        names=z.namelist();check(len(names)==len(set(names)),'Duplicate ZIP entry')
        for name in names: check(not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts,'Unsafe evidence path')
        hashes={}
        for line in z.read('SHA256SUMS').decode().splitlines():
            digest,name=line.split('  ',1);hashes[name]=digest
            check(sha(z.read(name))==digest,'Evidence SHA256: '+name)
        check(set(names)==set(hashes)|{'SHA256SUMS'},'Evidence inventory differs')
        index=json.loads(z.read('evidence-provenance.json'))
        for row in index: check(sha(z.read(row['path']))==row['sha256'],'Original evidence receipt mismatch')
        # Reviewer module hashes are bound to the actual historical commit, including c40 controls.
        for name in names:
            if not name.endswith('-source-hashes.json'): continue
            commit=tip if name.startswith('independent-p2-0574/') else (base if 'same-batch-c40-baseline' in name else manifest['template_commit'])
            rows=json.loads(z.read(name))
            for row in rows:
                check(sha(git('show',commit+':'+row['path']))==row['sha256'],'Pinned reviewer module mismatch: '+name+' '+row['path'])
                source_hash_receipts+=1
        fixed=json.loads(z.read('author-p2-0574/fixed-result.json'))
        for row in fixed['files']:
            data=git('show',tip+':'+row['path'])
            check(blob(data)==row['blob'] and sha(data)==row['sha256'],'Author fix source binding mismatch')
        reviewed=json.loads(z.read('independent-public-16f/fixed-source-review.json'))
        for row in reviewed['source_reviews']:
            data=git('show',base+':'+row['path'])
            check(sha(data)==row['sha256'] and git('show',tip+':'+row['path'])==data,'Public closure source differs')
        for path in reviewed['unchanged_guards']:
            check(text('rev-parse',base+':'+path)==text('rev-parse',tip+':'+path),'Original guard changed')
        final_review=json.loads(z.read('independent-p2-0574/review-result.json'))
        check(final_review['decision']=='PASS_SCOPED_READY_FOR_ISOLATED_INTEGRATION' and final_review['commit']==tip and final_review['blocking_findings']==[],'Final scoped review not accepted')
    binary=(folder/manifest['bundle_filename']).read_bytes();header,pack=binary.split(b'\n\n',1)
    check(re.findall(rb'^-([a-f0-9]{40}) ',header,re.M)==[base.encode()],'Bundle prerequisites differ')
    check(struct.unpack('>I',pack[8:12])[0]==len(objects),'PACK object count differs')
    git('bundle','verify',str(folder/manifest['bundle_filename']))
    git('fsck','--full','--strict','--no-dangling')
    print(json.dumps({'status':'PASS','product_tip':tip,'product_tree':manifest['product_tree'],
        'commits':len(graph),'introduced_objects':len(objects),'types':dict(Counter(x['type'] for x in objects)),
        'source_files':len(source),'evidence_entries':len(names),'evidence_original_files':len(index),
        'reviewer_module_source_hashes_verified':source_hash_receipts,'no_alternates':True,'fsck_full_strict':'PASS'},indent=2))

if __name__=='__main__': main()
