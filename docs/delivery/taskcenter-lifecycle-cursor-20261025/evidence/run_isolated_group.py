import os
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
import importlib.util, pathlib, sys, tempfile, json
source = pathlib.Path('/workspace/shared/taskcenter-lifecycle-6363')
spec=importlib.util.spec_from_file_location('verify',source/'scripts/verify_taskcenter_consistent_query.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
out=pathlib.Path('/workspace/shared/taskcenter-lifecycle-evidence')
name=sys.argv[1]
with tempfile.TemporaryDirectory(prefix='taskcenter-slice-') as temporary:
    scratch=pathlib.Path(temporary);support=scratch/'support';support.mkdir()
    (support/'taskcenter_evidence.py').write_text(v.PLUGIN)
    paths=sys.argv[2:] or v.REGRESSION
    result=v.run_group(name,source,paths,out,scratch,support)
    (out/(name+'-result.json')).write_text(json.dumps(result,indent=2))
    print(json.dumps({k:result[k] for k in ('returncode','junit','outside_source_modules')},indent=2))
