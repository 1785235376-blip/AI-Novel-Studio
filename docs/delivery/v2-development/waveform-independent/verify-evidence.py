import hashlib, json, pathlib, runpy, tarfile, zipfile
root=pathlib.Path.cwd()
evidence=root/'docs/delivery/v2-development'
sha=lambda b:hashlib.sha256(b).hexdigest()
labels=['waveform-independent-origin-r1','waveform-independent-backend-r1','waveform-independent-ui-r1']
receipts=[json.loads((evidence/(label+'.json')).read_text()) for label in labels]
current=runpy.run_path(str(root/'scripts/run_v2_checks.py'))['source_snapshot'](root)
for item in receipts:
    assert item['status']=='PASS' and item['exit_code']==0
    assert not item['sources_changed_during_check']
    assert item['source_sha256']==item['source_sha256_before']==current
    assert sha((root/item['log']).read_bytes())==item['log_sha256']
assert len(current)==2578
manifest=sha((root/'packaging/public-build.json').read_bytes())
assert manifest=='57f657057a391fa9ebdd8586fba62262ea6f3bb5fb1e2fe71f0c5ff27ad573be'
assert (evidence/'waveform-independent/manifest-before.sha256').read_bytes()==(evidence/'waveform-independent/manifest-after.sha256').read_bytes()
original=json.loads((evidence/'waveform-packaging/packaging-evidence/index.json').read_text())
records=[]
for entry in original['archives']:
    path=root/entry['archive']; assert sha(path.read_bytes())==entry['sha256']
    if entry['kind']=='sdist':
        with tarfile.open(path,'r:gz') as archive:
            members=archive.getmembers(); assert all(not x.issym() and not x.islnk() for x in members)
            payload={x.name:archive.extractfile(x).read() for x in members if x.isfile()}
        normalized={name.split('/',1)[1]:data for name,data in payload.items()}
    else:
        with zipfile.ZipFile(path) as archive:
            names=[x for x in archive.namelist() if not x.endswith('/')]
            assert len(names)==len(set(names)); payload={x:archive.read(x) for x in names}
        normalized=payload
    assert len(payload)==entry['payload_file_count']
    checked=0
    for name,data in normalized.items():
        if name.startswith(('app/','local_interop_desktop/','local_interop_protocol/')):
            assert (root/name).read_bytes()==data, name
            checked+=1
    for name, record in entry['changed_modules'].items():
        assert normalized[name]==(root/name).read_bytes()
        assert sha(normalized[name])==record['sha256']
    records.append({'archive':entry['archive'],'sha256':sha(path.read_bytes()),'payload_file_count':len(payload),'runtime_files_matching_current':checked,'changed_modules_matching_current':len(entry['changed_modules'])})
assert len(records)==4
assert runpy.run_path(str(root/'scripts/run_v2_checks.py'))['source_snapshot'](root)==current
result={'status':'PASS_INDEPENDENT_TEST_AND_ARCHIVE_AUDIT','receipts':labels,'source_count':len(current),'source_map_sha256':sha(json.dumps(current,sort_keys=True,separators=(',',':')).encode()),'all_source_maps_match_current':True,'all_log_hashes_match':True,'manifest_sha256':manifest,'archives':records,'archive_extraction':False,'product_import_or_install_for_audit':False,'postgres_windows_browser_native':'NOT_RUN'}
(evidence/'waveform-independent/verified-evidence.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
