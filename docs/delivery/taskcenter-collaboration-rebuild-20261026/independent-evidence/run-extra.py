import importlib.util,pathlib,tempfile,json,sys
source=pathlib.Path('/workspace/scratch/20a0022d2b33/taskcenter-rebuild-independent')
spec=importlib.util.spec_from_file_location('runner',source/'scripts/verify_taskcenter_consistent_query.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
out=pathlib.Path(__file__).parent
with tempfile.TemporaryDirectory(prefix='independent-taskcenter-') as td:
 scratch=pathlib.Path(td);support=scratch/'support';support.mkdir();(support/'taskcenter_evidence.py').write_text(m.PLUGIN)
 r=m.run_group(sys.argv[1],source,['tests/test_taskcenter_external_window.py',*sys.argv[2:]],out,scratch,support)
 print(json.dumps({k:r[k] for k in ('returncode','junit','outside_source_modules')},ensure_ascii=False));sys.exit(r['returncode'])
