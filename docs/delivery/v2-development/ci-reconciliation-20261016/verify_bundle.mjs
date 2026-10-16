// Read-only evidence verification. No pytest/product imports or service access.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import zlib from 'node:zlib';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const bundle=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(bundle,'../../../..');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const read=p=>fs.readFileSync(path.join(bundle,p));
const json=p=>JSON.parse(read(p));
const canonical=x=>JSON.stringify(Array.isArray(x)?x.map(y=>JSON.parse(canonical(y))):x&&typeof x==='object'?Object.fromEntries(Object.keys(x).sort().map(k=>[k,JSON.parse(canonical(x[k]))])):x);
const equal=(a,b)=>canonical(a)===canonical(b);
const checks=[];
function check(name,ok){checks.push({name,ok:!!ok});if(!ok)throw Error(name);}
function source(p){check('safe source path '+p,!path.isAbsolute(p)&&!p.split('/').includes('..'));return fs.readFileSync(path.join(root,p));}
function files(dir,prefix=''){let found=[];for(const e of fs.readdirSync(dir,{withFileTypes:true})){check('regular evidence entry '+prefix+e.name,!e.isSymbolicLink());let p=prefix+e.name;if(e.isDirectory())found.push(...files(path.join(dir,e.name),p+'/'));else if(e.isFile())found.push(p);else throw Error('Special evidence file '+p);}return found.sort();}
const index=json('evidence-files.json');
check('exact evidence closure',equal(files(bundle).filter(p=>p!=='evidence-files.json'),index.files.map(x=>x.path).sort()));
for(const item of index.files){let b=read(item.path);check('evidence hash '+item.path,sha(b)===item.sha256&&b.length===item.bytes);}
for(const item of json('artifact-relocation-map.json').copies)check('relocation bytes '+item.destination,sha(read(item.destination))===item.sha256);
const sourceMap=json('source-126-map.json');
check('source checkpoint',sourceMap.source_commit==='14ced1025b51af3b9636fc9564366bd5aba1946d'&&sourceMap.paths.length===126);
for(const item of sourceMap.paths){check('committed source '+item.path,sha(execFileSync('git',['show',sourceMap.source_commit+':'+item.path],{cwd:root}))===item.sha256);check('working source '+item.path,sha(source(item.path))===item.sha256);}
const rawNames=files(path.join(bundle,'inventory')).filter(p=>/^raw-(review|candidate|confirmation)-collection-.*\.json$/.test(p));
check('three immutable collection archives',rawNames.length===3);
const raws=rawNames.map(p=>read('inventory/'+p));
check('raw bytes identical',raws.every(b=>sha(b)==='b921230f2888db9f7be9fd32f1f3e3d2dfaf45c2ce528886897a17ba7fa78ede'));
const rows=JSON.parse(raws[0]);check('collection success',rows.exit_code===0&&rows.errors.length===0&&rows.rows.length===15617);
check('unique node IDs',new Set(rows.rows.map(x=>x.nodeid)).size===rows.rows.length);
const oldRaw=read('inventory/old-15142-collection-rows.json.gz');check('old receipt bytes',sha(oldRaw)==='8a63aa4ad872695d1699816910647dec8070f2566f9a8aea3eb3943ffa9bbd34');
const old=JSON.parse(zlib.gunzipSync(oldRaw)),oldIds=new Set(old.rows.map(x=>x.nodeid));check('full old ordered/classified rows',old.rows.length===15142&&equal(rows.rows.filter(x=>oldIds.has(x.nodeid)),old.rows));
const approved='bffc623ae02c28b8cf8c4022b3ed33674e6b14b9fc7a1ccab2326c36ccf3bb5c';
const current=source('.github/ci/coverage_manifest_v2.json.gz');check('canonical approved bytes',sha(current)===approved);
const manifest=JSON.parse(zlib.gunzipSync(current));check('manifest node order',equal(manifest.product_nodes,rows.rows.map(x=>x.nodeid)));
const rowDigest=sha(Buffer.from(JSON.stringify(rows.rows).replace(/[^\x00-\x7f]/g,c=>'\\u'+c.charCodeAt(0).toString(16).padStart(4,'0'))));check('classification digest',rowDigest===manifest.v2_extension.collection_classifications_sha256);
const frozen=source('.github/ci/coverage_manifest.json.gz');check('frozen V1 bytes',sha(frozen)==='6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262');const v1=JSON.parse(zlib.gunzipSync(frozen));
const oldV2=JSON.parse(zlib.gunzipSync(execFileSync('git',['show','72e636f87c7299a62cb3357bcb6a6e44a9388883:.github/ci/coverage_manifest_v2.json.gz'],{cwd:root})));
check('skips and external gates retained',equal(manifest.skips,oldV2.skips)&&equal(manifest.external_gates,oldV2.external_gates));
check('old source paths retained',Object.keys(oldV2.source_files).every(p=>p in manifest.source_files));
const before=json('inventory/source-provenance-before.json'),after=json('inventory/source-provenance-confirmation-after.json');check('stable source and omitted-directory companion',equal(before.source_sha256,after.source_sha256)&&equal(before.omitted_frontend_companion,after.omitted_frontend_companion));
const expected=Object.fromEntries(Object.entries(before.source_sha256).filter(([p])=>!p.startsWith('frontend/scripts/')&&!p.startsWith('frontend/e2e/')));for(const p of Object.keys(v1.source_files))expected[p]=sha(source(p));
check('exact 2576-source generator closure',Object.keys(expected).length===2576&&equal(expected,manifest.source_files));
for(const [p,h]of Object.entries(manifest.source_files))check('manifest fingerprint '+p,sha(source(p))===h);
for(const [p,h]of Object.entries(before.omitted_frontend_companion))check('omitted-directory fingerprint '+p,sha(source(p))===h);
const companionPaths=['frontend/scripts','frontend/e2e'].flatMap(p=>files(path.join(root,p)).map(f=>p+'/'+f)).sort();check('omitted-directory closure',equal(companionPaths,Object.keys(before.omitted_frontend_companion).sort()));
const audit=json('audits/ci-reconciliation-audit-20261016.json');for(const item of audit.guard_and_manifest_boundaries)check('guard boundary '+item.path,sha(source(item.path))===(item.path==='.github/ci/coverage_manifest_v2.json.gz'?approved:item.base_sha256));
for(const item of audit.protected_tests)check('restored protected source '+item.path,sha(source(item.path))===item.expected_sha256);
const migrations=manifest.v2_extension.baseline_test_migrations;check('sole reviewed Windows migration',migrations.length===1&&migrations[0].path==='tests/test_windows_portable_entry.py'&&migrations[0].commit==='1b7ff50a7e64742916bc64730df884cea819b379');
console.log(JSON.stringify({status:'PASS_READ_ONLY_EVIDENCE_CHECK',source_commit:sourceMap.source_commit,evidence_files:index.files.length,checks:checks.length,inventory_rows:rows.rows.length,old_rows:old.rows.length,source_map_entries:Object.keys(manifest.source_files).length,companion_files:Object.keys(before.omitted_frontend_companion).length,tests_executed:false,product_imports:false},null,2));
