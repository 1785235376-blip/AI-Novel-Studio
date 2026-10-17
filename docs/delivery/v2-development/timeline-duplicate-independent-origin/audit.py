import hashlib,json,pathlib,subprocess,datetime
root=pathlib.Path.cwd(); evidence=root/'docs/delivery/v2-development'; base='feade20ce2f6671e5d5a16c0781896f3c5696927'
names=['file-origin','file','file-regression','ui','type','build','token','independent-origin','independent-file','independent-ui']
receipts=[]; manifest=None
for name in names:
 p=evidence/f'timeline-duplicate-{name}-r1.json'; r=json.loads(p.read_text()); assert r['status']=='PASS' and r['exit_code']==0
 assert not r['sources_changed_during_check'] and r['source_sha256_before']==r['source_sha256']
 if manifest is None: manifest=r['source_sha256']
 assert r['source_sha256']==manifest
 log=root/r['log']; assert hashlib.sha256(log.read_bytes()).hexdigest()==r['log_sha256']
 receipts.append({'name':p.stem,'receipt_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'log_sha256':r['log_sha256'],'sources':len(manifest)})
for name,sha in manifest.items(): assert hashlib.sha256((root/name).read_bytes()).hexdigest()==sha,name
basefiles={}
for line in subprocess.check_output(['git','ls-tree','-r',base],text=True).splitlines():
 meta,path=line.split('\t'); basefiles[path]=meta.split()[2]
changed=[]; added=[]; unchanged=0
for name in manifest:
 if name not in basefiles: added.append(name); continue
 body=(root/name).read_bytes(); sha=hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()
 if sha==basefiles[name]: unchanged+=1
 else: changed.append(name)
assert set(changed)=={'frontend/src/creative/StudioTimelineEditor.tsx','frontend/src/creative/useStudioTimelineEditor.ts','frontend/src/nle/ClipInspectorPanel.tsx'}
assert len(added)==5
origin=evidence/'timeline-duplicate-independent-origin'
parent=json.loads((origin/'normal-startup.json').read_text()); child=json.loads((evidence/'timeline-duplicate-independent-origin-r1.log').read_text())
probe=hashlib.sha256((origin/'origin-probe.py').read_bytes()).hexdigest()
assert parent['probe_sha256']==child['probe_sha256']==probe and parent['specs']==child['specs']
assert not parent['product_or_pytest_imported'] and not child['product_or_pytest_imported']
report={'status':'PASS_SCOPED_INDEPENDENT_REVIEW','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'base':base,'runtime_review':'Detached duplicate-all then copied-internal-transition updates, original complete validation and one change/history; exact authored IDs and recursive descriptor checking; guarded selection/input/draft/context/client/permission/busy/UNKNOWN/unmount generations; explicit original Save/CAS/source authority. Legacy single-clip duplicate left unchanged.', 'independent_results':{'file':'53 passed (32 new + 21 existing selection), 1 existing warning','ui':'120 passed in 6 suites (66 new + 54 existing selection); repeated primary coverage, not additional unique tests'},'manifest_entries':len(manifest),'baseline_manifest_entries':unchanged+len(changed),'byte_exact_baseline_entries':unchanged,'baseline_changed_paths':changed,'new_manifest_paths':added,'all_primary_and_independent_maps_equal':True,'current_manifest_verified':True,'origin':{'probe_sha256':probe,'normal_and_actual_child_specs_equal':True,'product_or_pytest_imported':False},'receipts':receipts,'not_run':['PostgreSQL','browser visual/geometry','native/Windows/packaged runtime','render/media quality or measured source duration','provider/GPU','full E2E/release acceptance'],'limit_boundary':'New UI valid selections cannot reach 40 operations/128000 bytes under 30 total clips and 240-character IDs; explicit guards retained, original backend direct limits tested.'}
p=evidence/'timeline-duplicate-independent-review.json'; p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(report,indent=2))
