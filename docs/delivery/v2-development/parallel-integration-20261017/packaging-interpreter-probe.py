"""Inspect already-installed offline packaging tools without application imports."""
import hashlib, importlib.machinery, importlib.metadata, json, pathlib, site, sys
base=pathlib.Path('/opt/codex/runtimes/codex-primary-runtime/dependencies/python')
assert pathlib.Path(sys.executable)==base/'bin/python3.12'
assert hashlib.sha256(pathlib.Path(sys.executable).read_bytes()).hexdigest()=='fa67443527ed9647f760d807e2a38f26340757123e643c4639cf273ed15d5ea7'
assert not site.ENABLE_USER_SITE
prefixes=('app','local_interop_protocol','local_interop_desktop')
assert not any(n==p or n.startswith(p+'.') for n in sys.modules for p in prefixes)
modules={}
for name in ('setuptools','wheel'):
    spec=importlib.machinery.PathFinder.find_spec(name,sys.path)
    assert spec and spec.origin and pathlib.Path(spec.origin).is_relative_to(base/'lib/python3.12/site-packages')
    modules[name]={'origin':spec.origin,'version':importlib.metadata.version(name),'sha256':hashlib.sha256(pathlib.Path(spec.origin).read_bytes()).hexdigest()}
print(json.dumps({'status':'PASS_INSTALLED_PACKAGING_TOOLS','executable':sys.executable,'executable_sha256':hashlib.sha256(pathlib.Path(sys.executable).read_bytes()).hexdigest(),'sys_path':sys.path,'meta_path':[type(x).__module__+'.'+type(x).__name__ for x in sys.meta_path],'modules':modules,'product_imported':False,'tool_installation':False},indent=2))
