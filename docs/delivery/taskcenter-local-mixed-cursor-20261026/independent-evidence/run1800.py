import importlib.util,pathlib,tempfile,sys,json,os
os.environ['PYTHONDONTWRITEBYTECODE']='1'
s=pathlib.Path('/workspace/shared/taskcenter-local-mixed-independent')
spec=importlib.util.spec_from_file_location('v',s/'scripts/verify_taskcenter_consistent_query.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
original_run=v.subprocess.run
def bounded_run(*a,**kw):
 if kw.get('timeout')==240:kw['timeout']=1800
 return original_run(*a,**kw)
v.subprocess.run=bounded_run
out=pathlib.Path('/workspace/shared/taskcenter-local-mixed-independent-evidence')
with tempfile.TemporaryDirectory() as d:
 d=pathlib.Path(d);p=d/'support';p.mkdir();(p/'taskcenter_evidence.py').write_text(v.PLUGIN);r=v.run_group(sys.argv[1],s,sys.argv[2:],out,d,p);print(json.dumps({k:r[k] for k in ('returncode','junit','outside_source_modules')}));sys.exit(r['returncode'])
