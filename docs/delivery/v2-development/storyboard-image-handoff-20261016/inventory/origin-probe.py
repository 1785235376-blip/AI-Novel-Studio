"""Stdlib-only import-location proof. Never imports product or pytest modules."""
import datetime, hashlib, importlib.machinery, importlib.metadata, json, os, pathlib, site, subprocess, sys

ROOT = pathlib.Path('/workspace/scratch/20a0022d2b33/studio-storyboard-handoff')
ENV = pathlib.Path('/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1')
SITE = ENV / 'lib/python3.12/site-packages'
BASE = pathlib.Path('/opt/codex/runtimes/codex-primary-runtime/dependencies/python')
OLD = '/workspace/scratch/20a0022d2b33/studio-overnight'
PREFIXES = ('app', 'local_interop_desktop', 'local_interop_protocol')
require_cwd = pathlib.Path.cwd() == ROOT
assert require_cwd, 'wrong actual child cwd'
errors = []
def require(value, message):
    if not value:
        raise AssertionError(message)

require(pathlib.Path(sys.executable) == ENV / 'bin/python', 'not new virtualenv executable')
require(pathlib.Path(sys.prefix) == ENV, 'wrong virtualenv prefix')
require(pathlib.Path(sys.base_prefix) == BASE, 'wrong base prefix')
require(site.ENABLE_USER_SITE is False, 'user site is enabled')
require(not any(OLD in str(value) for value in sys.path), 'old candidate path on sys.path')
require(not any('__editable__' in str(value) for value in sys.path), 'editable namespace placeholder')
for entry in sys.path:
    if not entry:
        raise AssertionError('implicit current-directory sys.path entry')
    path = pathlib.Path(entry).resolve()
    require(path.is_relative_to(ROOT) or path.is_relative_to(ENV) or path.is_relative_to(BASE), 'unapproved sys.path: ' + entry)
meta = [getattr(x, '__module__', type(x).__module__) + '.' + getattr(x, '__name__', type(x).__name__) for x in sys.meta_path]
require(all(x in {'_frozen_importlib.BuiltinImporter', '_frozen_importlib.FrozenImporter', '_frozen_importlib_external.PathFinder'} for x in meta), 'unexpected meta_path finder: ' + repr(meta))
require(not any('__editable__' in name or name in {'_virtualenv','sitecustomize','usercustomize'} for name in sys.modules), 'startup hook imported')
require(not any(name == p or name.startswith(p + '.') for name in sys.modules for p in PREFIXES), 'product module already imported')
for name in ('PYTHONHOME','PYTHONSTARTUP','PYTHONUSERBASE','PYTEST_ADDOPTS','PYTEST_PLUGINS','PACKAGED_RUNTIME_INSTANCE_ID','PACKAGED_BOOTSTRAP_SECRET','PACKAGED_CONTROL_PIPE'):
    require(name not in os.environ, 'unsafe inherited setting present: ' + name)
for name,value in {'PYTHONNOUSERSITE':'1','PYTHONDONTWRITEBYTECODE':'1','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1','PACKAGED_WINDOWS_MODE':'false','PYTHONPATH':str(ROOT)}.items():
    require(os.environ.get(name)==value, 'missing explicit environment: ' + name)
specs={}
def locate(fullname, start_paths):
    spec=importlib.machinery.PathFinder.find_spec(fullname.rsplit('.', 1)[-1], start_paths)
    require(spec is not None, 'missing explicit spec: ' + fullname)
    locations=list(spec.submodule_search_locations or [])
    paths=([spec.origin] if spec.origin not in (None,'namespace','built-in','frozen') else [])+locations
    require(paths and all(pathlib.Path(x).resolve().is_relative_to(ROOT) for x in paths), 'product spec outside current root: ' + fullname)
    require(all(OLD not in x for x in paths), 'old candidate spec: ' + fullname)
    specs[fullname]={'lookup_name': fullname.rsplit('.', 1)[-1], 'origin':spec.origin,'submodule_search_locations':locations}
    return locations
for package in PREFIXES:
    locate(package,sys.path)
    require(specs[package]['origin']==str(ROOT/package/'__init__.py'), 'wrong actual top-level origin: '+package)
    require(specs[package]['submodule_search_locations']==[str(ROOT/package)], 'wrong actual top-level path: '+package)
app_paths=specs['app']['submodule_search_locations']
application_paths=locate('app.application',app_paths)
locate('app.application.persistence',application_paths)
locate('app.autosave',app_paths)
locate('app.project_retirement',app_paths)
for fullname in ('app.application','app.autosave'):
    require(specs[fullname]['origin'] is None and specs[fullname]['submodule_search_locations']==[str(ROOT.joinpath(*fullname.split('.')))], 'wrong exact namespace: '+fullname)
for fullname in ('app.application.persistence','app.project_retirement'):
    require(specs[fullname]['origin']==str(ROOT.joinpath(*fullname.split('.')).with_suffix('.py')) and not specs[fullname]['submodule_search_locations'], 'wrong exact child origin: '+fullname)
for package in ('pytest','pydantic','fastapi','psycopg'):
    spec=importlib.machinery.PathFinder.find_spec(package,sys.path)
    require(spec is not None and spec.origin and pathlib.Path(spec.origin).resolve().is_relative_to(SITE),'dependency origin outside new site: '+package)
    require(spec.origin==str(SITE/package/'__init__.py'), 'wrong actual dependency origin: '+package)
    specs[package]={'origin':spec.origin,'submodule_search_locations':list(spec.submodule_search_locations or [])}
setup=json.loads((ENV/'setup-receipt.json').read_text())
actual=sorted((d.metadata['Name'],d.version) for d in importlib.metadata.distributions(path=[str(SITE)]))
expected=sorted((d['name'],d['version']) for d in setup['distributions'])
require(actual==expected,'dependency metadata does not match copied allowlist')
require(not any(name == p or name.startswith(p + '.') for name in sys.modules for p in PREFIXES),'PathFinder probe imported product')
require('pytest' not in sys.modules, 'probe imported pytest')
result={'status':'PASS_STARTUP_AND_EXPLICIT_PATHFINDER_ONLY','child': '--child' in sys.argv,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'executable':sys.executable,'prefix':sys.prefix,'base_prefix':sys.base_prefix,'sys_path':sys.path,'meta_path':meta,'user_site_enabled':site.ENABLE_USER_SITE,'product_or_pytest_imported':False,'dependency_distributions':actual,'specs':specs,'probe_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'setup_receipt_sha256':hashlib.sha256((ENV/'setup-receipt.json').read_bytes()).hexdigest()}
if '--child' not in sys.argv:
    command=[sys.executable,str(pathlib.Path(__file__)),'--child']
    child=subprocess.run(command,cwd=ROOT,env=os.environ.copy(),capture_output=True,text=True)
    result['child_command']=command
    result['child_exit_code']=child.returncode
    result['child_stdout']=child.stdout
    result['child_stderr']=child.stderr
    require(child.returncode==0,'child probe failed: '+child.stdout+child.stderr)
    result['child_receipt']=json.loads(child.stdout)
    require(result['child_receipt']['status']==result['status'],'child status mismatch')
print(json.dumps(result,indent=2))
