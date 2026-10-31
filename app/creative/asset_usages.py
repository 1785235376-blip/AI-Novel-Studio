"""Bounded observations of direct saved pins; no refresh or execution authority.

Callers must use the original Graph/Timeline route invoker, including its Host
and incarnation guards. This module has no raw-store or fallback reader.
"""
from copy import deepcopy

from ..experimental.common import StaleSourceError

MAX_USAGE_ROWS = 200
MAX_OWNER_ROWS = 25


def _source(workspace, nid, scope, aid, guard):
    guard()
    with workspace._asset_scope(nid, scope):
        row = workspace._row(nid, scope, aid)
        # Actor-private candidates are not public asset-reference inputs.
        if row.get('_owner_actor_id'):
            raise FileNotFoundError('STUDIO_USAGE_SOURCE_UNAVAILABLE')
        from .production_execution_models import TimelineAssetSnapshot
        result = TimelineAssetSnapshot.model_validate({'kind': 'ASSET', 'id': row['id'],
            'version': row['version'], 'digest': row['sha256'], 'asset_kind': row['kind']}).model_dump()
    guard()
    return result


def _bounded(rows):
    if len(rows) > MAX_OWNER_ROWS:
        raise ValueError('STUDIO_USAGE_OWNER_LIMIT')
    if len({row['id'] for row in rows}) != len(rows):
        raise ValueError('STUDIO_USAGE_OWNER_IDENTITY_INVALID')
    return sorted(rows, key=lambda row: row['id'])


def _identity(rows, digest_key):
    return [(row['id'], row['version'], row[digest_key]) for row in rows]


def _result(owner, items, source):
    return {'owner': owner, 'source': deepcopy(source), 'items': items[:MAX_USAGE_ROWS],
            'coverage': 'EXACT_SAVED_DIRECT_ASSET_REFERENCES',
            'truncated': len(items) > MAX_USAGE_ROWS, 'limit': MAX_USAGE_ROWS,
            'read_only': True, 'automatic_regeneration': False,
            'other_dependencies': 'UNKNOWN'}


def graph_asset_usages(service, nid, scope, actor, aid, guard, *, limit=None, cursor=None, state=None):
    """Original list/get perform schema and reference redaction checks."""
    if limit is not None:
        from .asset_usage_paging import paged_usages
        from .asset_usage_budget import usage_read_budget
        with usage_read_budget():
            return paged_usages(service, nid, scope, actor, aid, guard, graph=True,
                                limit=limit, cursor=cursor, state=state)
    if cursor is not None or state is not None:
        raise ValueError('STUDIO_USAGE_QUERY_INVALID')
    source = _source(service.workspace, nid, scope, aid, guard)
    def read():
        listed = _bounded(service.list(nid, scope, actor, guard)['items'])
        return [service.get(nid, scope, actor, row['id'], guard) for row in listed]

    rows = read()
    result = []
    for row in rows:
        guard()
        states = {item['node_id']: item['state'] for item in row['reference_states']}
        for node in sorted(row['definition']['nodes'], key=lambda item: item['id']):
            pin = node['parameters']
            if (node['definition_id'] != 'asset_reference' or pin.get('asset_id') != aid
                    or states.get(node['id']) not in {'CURRENT', 'STALE'}):
                continue
            recorded = {'kind': 'ASSET', 'id': pin['asset_id'], 'version': pin['version'],
                        'digest': pin['digest'], 'asset_kind': pin['kind']}
            result.append({'owner': 'CREATIVE_GRAPH', 'id': row['id'],
                'version': row['version'], 'digest': row['definition_digest'],
                'node_id': node['id'], 'definition_id': node['definition_id'],
                'source': recorded, 'current_source': deepcopy(source),
                'state': 'CURRENT' if recorded == source else 'STALE'})
    # Do not return a mixture after source edits, consumer edits, or admission
    # changes. Original lists retain their actor/incarnation/feature checks.
    after = read()
    if (_identity(rows, 'definition_digest') != _identity(after, 'definition_digest')
            or _source(service.workspace, nid, scope, aid, guard) != source):
        raise StaleSourceError('STUDIO_USAGE_SOURCE_OR_CONSUMER_CHANGED')
    guard()
    return _result('CREATIVE_GRAPH', result, source)


def timeline_asset_usages(service, nid, scope, actor, aid, guard, *, limit=None, cursor=None, state=None):
    if limit is not None:
        from .asset_usage_paging import paged_usages
        from .asset_usage_budget import usage_read_budget
        with usage_read_budget():
            return paged_usages(service, nid, scope, actor, aid, guard, graph=False,
                                limit=limit, cursor=cursor, state=state)
    if cursor is not None or state is not None:
        raise ValueError('STUDIO_USAGE_QUERY_INVALID')
    source = _source(service.workspace, nid, scope, aid, guard)

    def read():
        # list is discovery only; get validates each exact original owner row.
        listed = _bounded(service.timeline_list(nid, scope, actor, guard)['items'])
        return [service.timeline_get(nid, scope, actor, row['id'], guard) for row in listed]

    rows, result = read(), []
    for row in rows:
        guard()
        for track in sorted(row['timeline']['tracks'], key=lambda item: item['id']):
            for clip in sorted(track['clips'], key=lambda item: item['id']):
                pin = clip['source_snapshot']
                if pin['id'] != aid:
                    continue
                result.append({'owner': 'STUDIO_TIMELINE', 'id': row['id'],
                    'version': row['version'], 'digest': row['timeline_digest'],
                    'track_id': track['id'], 'clip_id': clip['id'],
                    'source': deepcopy(pin), 'current_source': deepcopy(source),
                    'state': 'CURRENT' if pin == source else 'STALE'})
    after = read()
    if (_identity(rows, 'timeline_digest') != _identity(after, 'timeline_digest')
            or _source(service.workspace, nid, scope, aid, guard) != source):
        raise StaleSourceError('STUDIO_USAGE_SOURCE_OR_CONSUMER_CHANGED')
    guard()
    return _result('STUDIO_TIMELINE', result, source)
