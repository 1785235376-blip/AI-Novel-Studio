"""Rebind the existing complete API catalog to the current mounted application.

Keeps historical comparisons and owner annotations, adds new routes and rejects
removed routes. Run after implementation changes, before the regression suite.
"""
import gzip
import hashlib
import importlib
import inspect
import json
from pathlib import Path
import sys
import warnings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
METHODS = {'get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace'}


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def references(value):
    if isinstance(value, dict):
        ref = value.get('$ref', '')
        if ref.startswith('#/components/schemas/'):
            yield ref.rsplit('/', 1)[-1]
        for item in value.values():
            yield from references(item)
    elif isinstance(value, list):
        for item in value:
            yield from references(item)


def refresh_discovery_authority(owner, route):
    """Rebind this changed surface's annotations to its mounted host dependency.

    Other historical owner annotations remain intact. This is source inventory,
    not a claim that endpoint inspection constitutes authorization acceptance.
    """
    if route.endpoint.__module__ != 'app.model_center.discovery_api':
        return
    dependencies = [item.call for item in route.dependant.dependencies]
    require = next((item for item in dependencies if item.__name__ == 'require_session'), None)
    host = inspect.getclosurevars(require).nonlocals.get('host_authorization') if require else None
    resolver = host.__globals__.get('resolve_discovery_authority') if callable(host) else None
    if not callable(require) or not callable(host) or not callable(resolver):
        raise RuntimeError('Mounted discovery catalog requires current host-authority provenance')
    name = lambda function: function.__module__ + '.' + function.__qualname__
    gated = route.path.endswith('/environment') or '/onboarding/' in route.path
    owner.update(
        authority_read_method='Mounted dependency closure and current Host resolver source inspection; not runtime verification or a complete authorization proof.',
        observed_authority_functions=[name(host), name(resolver), name(require)],
        router_dependency_functions=[name(item) for item in dependencies],
        conditional_feature_checks=[{'conditional': False, 'expression': "'narrative_production_v2'",
            'function': name(route.endpoint) if route.path.endswith('/environment') else
            'app.model_center.discovery_api.create_local_discovery_router.<locals>.onboarding'}] if gated else [],
        observed_reused_feature_flags=['narrative_production_v2'] if gated else [],
        original_service_classes=['app.model_center.discovery.LocalDiscoveryService'],
    )


def main():
    old = json.loads(gzip.decompress((ROOT / 'API_CATALOG_DETAIL.json.gz').read_bytes()))
    previous = {(item['method'], item['path']): item for item in old['operations']}
    from app.main import app
    from fastapi.routing import APIRoute
    from pydantic import BaseModel
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        app.openapi_schema = None
        spec = app.openapi()
    schemas = spec.get('components', {}).get('schemas', {})
    effective = []
    for route in app.routes:
        if isinstance(route, APIRoute): effective.append(route)
        elif hasattr(route, 'effective_route_contexts'):
            effective.extend(route.effective_route_contexts())
    routes = {(method, route.path): route for route in effective
              for method in route.methods if method.lower() in METHODS}
    mounted = {(method.upper(), path) for path, methods in spec['paths'].items()
               for method in methods if method in METHODS}
    removed = set(previous) - mounted
    if removed:
        raise RuntimeError(f'Existing API routes removed: {sorted(removed)}')
    owners = old['owners']
    validation = old['source_validation_models']
    for name, model in list(validation.items()):
        module_name, class_name = name.rsplit('.', 1)
        cls = getattr(importlib.import_module(module_name), class_name)
        model['schema'] = cls.model_json_schema()
    for module_name, module in list(sys.modules.items()):
        if not module_name.startswith('app.') or module is None:
            continue
        for name, cls in list(vars(module).items()):
            if inspect.isclass(cls) and issubclass(cls, BaseModel) and cls.__module__ == module_name:
                file = inspect.getsourcefile(cls)
                if file:
                    validation[module_name + '.' + name] = {
                        'file': Path(file).relative_to(ROOT).as_posix(), 'schema': cls.model_json_schema()}
    operations = []
    for method, path in sorted(mounted):
        operation = spec['paths'][path][method.lower()]
        route = routes[(method, path)]
        endpoint = route.endpoint
        file = Path(inspect.getsourcefile(endpoint)).relative_to(ROOT).as_posix()
        line = inspect.getsourcelines(endpoint)[1]
        old_row = previous.get((method, path))
        owner_ref = old_row['owner_ref'] if old_row else digest([endpoint.__module__, endpoint.__qualname__, file])
        owner = owners.setdefault(owner_ref, {
            'authority_read_method': 'Mounted endpoint source inspection; no runtime verification claim.',
            'conditional_feature_checks': [], 'observed_authority_functions': [],
            'observed_permission_literals': [], 'observed_reused_feature_flags': [],
            'original_service_classes': [], 'router_dependency_functions': [],
        })
        owner.update(endpoint=endpoint.__module__ + '.' + endpoint.__qualname__, source_file=file, source_line=line)
        refresh_discovery_authority(owner, route)
        refs = set(references(operation))
        pending = list(refs)
        while pending:
            for name in references(schemas[pending.pop()]):
                if name not in refs:
                    refs.add(name)
                    pending.append(name)
        source_refs = list(old_row.get('source_validation_model_refs', [])) if old_row else []
        for field in route.dependant.body_params:
            cls = getattr(field, 'type_', None)
            name = getattr(cls, '__module__', '') + '.' + getattr(cls, '__name__', '')
            if name in validation and name not in source_refs:
                source_refs.append(name)
        operations.append({**(old_row or {}), 'method': method, 'path': path,
            'operation_id': operation.get('operationId'), 'operation_sha256': digest(operation),
            'owner_ref': owner_ref, 'parameters': operation.get('parameters', []),
            'request_body': operation.get('requestBody'), 'responses': operation.get('responses', {}),
            'schema_refs': sorted(refs), 'schema_graph_sha256': digest({name: schemas[name] for name in sorted(refs)}),
            'source_validation_model_refs': source_refs,
            'changes': list(dict.fromkeys((old_row or {}).get('changes', []) +
                (['FULL_RECOVERY_ADDED_ROUTE'] if old_row is None else ['FULL_RECOVERY_SOURCE_REBOUND']))),
            'changed_direct_functions': (old_row or {}).get('changed_direct_functions', []),
        })
    sources = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in sorted((ROOT / 'app').rglob('*.py'))}
    summary = {**old['summary'], 'current_method_paths': len(operations),
               'added': old['summary']['added'] + len(mounted - set(previous)), 'removed': 0}
    value = {**old, 'operations': operations, 'owners': owners, 'source_validation_models': validation,
             'summary': summary, 'openapi_schemas': schemas, 'removed_method_paths': [],
             'application_python_source_hashes': sources, 'application_source_fingerprint_sha256': digest(sources)}
    detail = gzip.compress(encoded(value), mtime=0)
    (ROOT / 'API_CATALOG_DETAIL.json.gz').write_bytes(detail)
    (ROOT / 'API_OPENAPI.json.gz').write_bytes(gzip.compress(encoded(spec), mtime=0))
    index = json.loads((ROOT / 'API_CATALOG.json').read_text(encoding='utf-8'))
    index.update(summary=summary, application_python_source_hashes=sources,
                 application_source_fingerprint_sha256=digest(sources),
                 operations=[{key: row[key] for key in ('method', 'path', 'operation_id', 'owner_ref', 'changes', 'operation_sha256', 'schema_graph_sha256')} for row in operations])
    index['detail']['sha256'] = hashlib.sha256(detail).hexdigest()
    (ROOT / 'API_CATALOG.json').write_bytes((json.dumps(index, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    lines = ['# API Catalog', '',
        'Complete mounted source inventory. This catalog is a source map, not a runtime verification verdict.', '',
        f'Starting method/path operations: {summary["starting_method_paths"]}. Current: {len(operations)}. '
        f'Added: {summary["added"]}. Removed: 0.', '',
        'The complete operation/schema/owner graph is retained in API_CATALOG_DETAIL.json.gz; '
        'API_CATALOG.json binds its digest and all application sources. Original aliases are listed separately.', '',
        '| Method | Mounted path | Source owner | Changes |', '|---|---|---|---|']
    for row in operations:
        owner = owners[row['owner_ref']]
        lines.append(f'| {row["method"]} | `{row["path"]}` | `{owner["source_file"]}:{owner["source_line"]}` | '
                     + ', '.join(row['changes']) + ' |')
    (ROOT / 'API_CATALOG.md').write_bytes(('\n'.join(lines) + '\n').encode('utf-8'))
    print(json.dumps({'operations': len(operations), 'added_this_refresh': len(mounted - set(previous)),
                      'removed': 0, 'source_fingerprint': digest(sources)}))


if __name__ == '__main__':
    main()
