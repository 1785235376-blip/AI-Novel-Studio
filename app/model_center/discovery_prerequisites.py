"""Pure, bounded projections of existing catalogue and same-scan advertisements.

This module owns no registry, filesystem, network client or execution permission.
Component names, catalogue validation records and Diffusers indexes cannot prove
an installed component. Only an explicit scan's ComfyUI response is observed.
"""
from __future__ import annotations

import copy
from itertools import islice

from .discovery_types import CatalogComponentRequirement, WorkflowPrerequisiteObservation
from .domain import ModelComponentDefinition, ModelDefinition

MAX_CATALOG_MODELS = 256
MAX_COMPONENT_REQUIREMENTS = 512
MAX_ADAPTERS = 16
MAX_REQUIRED_NODES = 64
MAX_OBJECT_NODES = 4096
MAX_INPUT_GROUPS = 3
MAX_INPUT_FIELDS = 128
MAX_LOADER_OPTIONS = 512


def _text(value, maximum=256):
    return isinstance(value, str) and 0 < len(value) <= maximum and not any(ord(c) < 32 or ord(c) == 127 for c in value)


def _status(current, new):
    return max((current, new), key={'COMPLETE': 0, 'BOUNDED': 1, 'MALFORMED': 2}.__getitem__)


def catalog_requirements(models, components):
    """Read the original ModelCenter owner under its caller-held config lock.

The private identities include all bounded component-definition dimensions so
configuration changes invalidate the original consent receipt. They grant no
compatibility, install or inference assertion and are never returned to clients.
"""
    rows, identities, status = [], [], 'COMPLETE'
    if not isinstance(models, dict) or not isinstance(components, dict):
        return rows, identities, 'MALFORMED'
    if len(models) > MAX_CATALOG_MODELS: status = 'BOUNDED'
    for key, model in islice(models.items(), MAX_CATALOG_MODELS):
        if (not isinstance(model, ModelDefinition) or not _text(model.id) or not _text(model.display_name)
                or key != model.id or not isinstance(model.components, (tuple, list))):
            status = _status(status, 'MALFORMED'); continue
        if not model.components: continue
        if len(model.components) > MAX_COMPONENT_REQUIREMENTS:
            status = _status(status, 'BOUNDED')
        seen = set()
        for identifier in islice(model.components, MAX_COMPONENT_REQUIREMENTS):
            if len(rows) >= MAX_COMPONENT_REQUIREMENTS:
                return rows, identities, _status(status, 'BOUNDED')
            if not _text(identifier) or identifier in seen:
                status = _status(status, 'MALFORMED'); continue
            seen.add(identifier)
            component = components.get(identifier)
            facts = None
            if identifier in components and not isinstance(component, ModelComponentDefinition):
                status = _status(status, 'MALFORMED')
            elif component is not None:
                dimensions = ('component_id', 'component_type', 'family', 'variant', 'architecture', 'version', 'format', 'precision', 'hash')
                facts = {key: getattr(component, key, None) for key in dimensions}
                if (any(not _text(value) for key, value in facts.items() if key != 'hash')
                        or not isinstance(facts['hash'], str) or len(facts['hash']) > 256
                        or not isinstance(component.compatible_models, (list, tuple))
                        or len(component.compatible_models) > MAX_CATALOG_MODELS
                        or any(not _text(value) for value in component.compatible_models)
                        or facts['component_id'] != identifier):
                    status = _status(status, 'MALFORMED'); facts = None
                else:
                    facts['compatible_models'] = list(component.compatible_models)
            rows.append(CatalogComponentRequirement(model_id=model.id, model_display_name=model.display_name,
                component_id=identifier, component_type=facts['component_type'] if facts else None,
                reason='NO_COMPONENT_IDENTITY_EVIDENCE' if facts else 'COMPONENT_DEFINITION_UNAVAILABLE').model_dump())
            identities.append({'model_id': model.id, 'model_display_name': model.display_name,
                               'component_id': identifier, 'definition': facts})
    return rows, identities, status


def prerequisite_template(runtimes, adapters, component_rows, definition_status, *, identities=None):
    """Freeze finite workflow declarations, not independently authoritative state."""
    workflows, status = [], definition_status
    if not isinstance(adapters, list):
        return {'definition_status': 'MALFORMED', 'workflows': [], 'components': component_rows}
    if len(adapters) > MAX_ADAPTERS: status = _status(status, 'BOUNDED')
    runtime_ids, ambiguous = set(), set()
    if not isinstance(runtimes, list):
        return {'definition_status': 'MALFORMED', 'workflows': [], 'components': component_rows}
    if len(runtimes) > 20: status = _status(status, 'BOUNDED')
    for runtime in islice(runtimes, 20):
        if not isinstance(runtime, dict) or not _text(runtime.get('id')):
            status = _status(status, 'MALFORMED'); continue
        if runtime['id'] in runtime_ids:
            ambiguous.add(runtime['id']); status = _status(status, 'MALFORMED')
        runtime_ids.add(runtime['id'])
    seen = set()
    for adapter in islice(adapters, MAX_ADAPTERS):
        if not isinstance(adapter, dict):
            status = _status(status, 'MALFORMED'); continue
        required = adapter.get('required_nodes')
        if isinstance(required, list) and len(required) > MAX_REQUIRED_NODES:
            status = _status(status, 'BOUNDED'); continue
        if (not _text(adapter.get('id'), 100) or adapter['id'] in seen
                or not _text(adapter.get('display_name')) or not _text(adapter.get('model_loader'))
                or not _text(adapter.get('model_input')) or not isinstance(required, list)
                or not required or any(not _text(node) for node in required)
                or len(set(required)) != len(required) or adapter['model_loader'] not in required
                or any(key in adapter and not _text(adapter[key]) for key in ('family', 'capability'))):
            status = _status(status, 'MALFORMED'); continue
        seen.add(adapter['id'])
        if identities is not None:
            identities.append({key: copy.deepcopy(adapter[key]) for key in
                ('id', 'display_name', 'required_nodes', 'model_loader', 'model_input', 'family', 'capability') if key in adapter})
        for runtime in islice(runtimes, 20):
            if (not isinstance(runtime, dict) or not _text(runtime.get('id'))
                    or runtime.get('type') != 'COMFYUI' or runtime['id'] in ambiguous): continue
            workflows.append(WorkflowPrerequisiteObservation(runtime_id=runtime['id'], adapter_id=adapter['id'],
                display_name=adapter['display_name'], nodes=[{'node_class': node} for node in required],
                loader={'node_class': adapter['model_loader'], 'input_field': adapter['model_input']}).model_dump())
    return {'definition_status': status, 'workflows': workflows, 'components': component_rows}


def unknown_observations(rows, status):
    result = copy.deepcopy(rows)
    for row in result:
        row['evidence_status'] = status
        for node in row['nodes']: node['observation'] = 'unknown'
        row['loader'].update(observation='unknown', advertised_count=None, candidate_ids=[])
    return result


def _index_status(info):
    if not isinstance(info, dict): return 'MALFORMED'
    if len(info) > MAX_OBJECT_NODES: return 'BOUNDED'
    for name, definition in info.items():
        if not _text(name) or not isinstance(definition, dict): return 'MALFORMED'
        # Missing input does not invalidate the explicit class advertisement.
        # It will invalidate loader evidence if this is a required model loader.
        if 'input' not in definition: continue
        inputs = definition['input']
        if not isinstance(inputs, dict): return 'MALFORMED'
        if len(inputs) > MAX_INPUT_GROUPS: return 'BOUNDED'
        for group, fields in inputs.items():
            if group not in {'required', 'optional', 'hidden'} or not isinstance(fields, dict): return 'MALFORMED'
            if len(fields) > MAX_INPUT_FIELDS: return 'BOUNDED'
            for field, schema in fields.items():
                if not _text(field): return 'MALFORMED'
                if group == 'hidden':
                    if not _text(schema): return 'MALFORMED'
                    continue
                if not isinstance(schema, list) or not 1 <= len(schema) <= 2: return 'MALFORMED'
                if len(schema) == 2 and not isinstance(schema[1], dict): return 'MALFORMED'
                if isinstance(schema[0], list):
                    if len(schema[0]) > MAX_LOADER_OPTIONS: return 'BOUNDED'
                elif not _text(schema[0]): return 'MALFORMED'
    return 'COMPLETE'


def observe_object_info(rows, info, candidates):
    """Complete means this response fits validation/bounds, not complete install."""
    state = _index_status(info)
    if state != 'COMPLETE': return unknown_observations(rows, state)
    result = copy.deepcopy(rows)
    for row in result:
        loader = row['loader']; node_class, field = loader['node_class'], loader['input_field']
        names = []
        if node_class in info:
            inputs = info[node_class].get('input')
            if not isinstance(inputs, dict):
                return unknown_observations(rows, 'MALFORMED')
            schemas = [fields[field] for group, fields in inputs.items()
                       if group in {'required', 'optional'} and field in fields]
            if len(schemas) != 1 or not isinstance(schemas[0][0], list):
                return unknown_observations(rows, 'MALFORMED')
            options = schemas[0][0]
            if any(not _text(name) for name in options):
                return unknown_observations(rows, 'MALFORMED')
            names = list(dict.fromkeys(options))
        row['evidence_status'] = 'COMPLETE'
        for node in row['nodes']:
            node['observation'] = 'observed' if node['node_class'] in info else 'not_observed'
        loader.update(observation='observed' if names else 'not_observed', advertised_count=len(names), candidate_ids=[])
        allowed_names = set(names)
        for candidate in islice(candidates, MAX_LOADER_OPTIONS):
            if (candidate.get('runtime_id') != row['runtime_id'] or candidate.get('runtime_type') != 'COMFYUI'
                    or candidate.get('model_name') not in allowed_names): continue
            if any(binding == {'node_class': node_class, 'input_field': field}
                   for binding in candidate.get('evidence', {}).get('loader_bindings', [])[:MAX_OBJECT_NODES]):
                loader['candidate_ids'].append(candidate['id'])
    return result


def failed_evidence_status(code):
    if code in {'LOCAL_AI_CANCELLED', 'LOCAL_AI_SCOPE_REVOKED'}: return 'CANCELLED'
    if code in {'LOCAL_AI_SCAN_BUDGET_REACHED', 'LOCAL_AI_RESPONSE_TOO_LARGE'}: return 'BOUNDED'
    if code in {'LOCAL_AI_INVALID_RESPONSE', 'LOCAL_AI_PROBE_INVALID'}: return 'MALFORMED'
    return 'UNAVAILABLE'
