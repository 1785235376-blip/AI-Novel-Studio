"""Bounded projections of original saved owners, with finite observations.

Tokens are process-local, short-lived positions, not durable snapshots. Equality
at observations does not establish absence of intervening changes (ABA). No
permission cache or lifecycle counter is invented here. Shared-file bytes are
resource costs only and never enter the visible-owner fingerprint or response.
"""
from copy import deepcopy
import hashlib
import json
import re
import secrets
from threading import Lock
import time

from ..experimental.common import StaleSourceError
from ..experimental.store import canonical
from .asset_usage_budget import UsageReadBudget

MAX_DIRECTORY_ROWS = 4096
MAX_CONSUMERS = 16
MAX_REFERENCES = 256
MAX_VALIDATION_REFERENCES = 4096
MAX_RESPONSE_BYTES = 256 * 1024
MAX_TOKENS = 1024
TOKEN_TTL = 300
_tokens = {}
_lock = Lock()


def _checkpoint(stage):
    """Deterministic test barrier; production has no callback or side effect."""


def _hash(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def directory(document, collection, actor, *, excluded_schemas=frozenset()):
    rows = document['collections'].get(collection, {})
    # Physical shared-container enumeration has a hard resource ceiling. It is
    # not published as a count and does not become a change fingerprint.
    if len(rows) > MAX_DIRECTORY_ROWS:
        raise ValueError('STUDIO_USAGE_RESOURCE_UNAVAILABLE')
    result = []
    for key, row in rows.items():
        if (not isinstance(row, dict) or row.get('created_by') != actor or
                row.get('novel_id') != document['novel_id'] or row.get('scope') != document['scope']):
            continue
        definition = row.get('definition', {})
        if excluded_schemas:
            if not isinstance(definition, dict):
                raise ValueError('STUDIO_USAGE_OWNER_IDENTITY_INVALID')
            if definition.get('schema_version') in excluded_schemas:
                continue
        if row.get('id') != key or not isinstance(key, str):
            raise ValueError('STUDIO_USAGE_OWNER_IDENTITY_INVALID')
        result.append((key, _hash(row)))
    return sorted(result)


def query_options(request, *, combined=False):
    if len(request.scope.get('query_string', b'')) > 2048:
        raise ValueError('STUDIO_USAGE_QUERY_INVALID')
    pairs = list(request.query_params.multi_items())
    if not pairs:
        return None
    allowed = {'limit', 'cursor', 'state', 'sources'} if combined else {'limit', 'cursor', 'state'}
    if (len(pairs) > len(allowed) or len({key for key, _ in pairs}) != len(pairs) or
            any(key not in allowed for key, _ in pairs)):
        raise ValueError('STUDIO_USAGE_QUERY_INVALID')
    values = dict(pairs)
    limit = values.get('limit', '')
    if not re.fullmatch(r'[1-9][0-9]{0,2}', limit) or int(limit) > 200:
        raise ValueError('STUDIO_USAGE_QUERY_INVALID')
    cursor = values.get('cursor')
    if cursor is not None and not re.fullmatch(r'[A-Za-z0-9_-]{43}', cursor):
        raise ValueError('STUDIO_USAGE_QUERY_INVALID')
    state = values.get('state')
    if state is not None and state not in {'CURRENT', 'STALE'}:
        raise ValueError('STUDIO_USAGE_QUERY_INVALID')
    result = {'limit': int(limit), 'cursor': cursor, 'state': state}
    if combined:
        sources = values.get('sources', 'graph,timeline')
        if sources not in {'graph', 'timeline', 'graph,timeline'}:
            raise ValueError('STUDIO_USAGE_QUERY_INVALID')
        result['sources'] = sources.split(',')
    return result


def _load(token, binding):
    with _lock:
        now = time.monotonic()
        for key in list(_tokens):
            if _tokens[key]['expires'] <= now:
                del _tokens[key]
        saved = _tokens.get(token)
        if saved is None or saved['binding'] != binding:
            raise StaleSourceError('STUDIO_USAGE_RESTART_REQUIRED')
        return deepcopy(saved)


def _issue(saved):
    with _lock:
        now = time.monotonic()
        for key in list(_tokens):
            if _tokens[key]['expires'] <= now:
                del _tokens[key]
        if saved['expires'] <= now or len(_tokens) >= MAX_TOKENS:
            raise ValueError('STUDIO_USAGE_RESOURCE_UNAVAILABLE')
        token = secrets.token_urlsafe(32)
        _tokens[token] = deepcopy(saved)
        return token


def _positions(row, graph):
    if graph:
        for node in sorted(row['definition']['nodes'], key=lambda item: item['id']):
            yield node
    else:
        for track in sorted(row['timeline']['tracks'], key=lambda item: item['id']):
            for clip in sorted(track['clips'], key=lambda item: item['id']):
                yield track['id'], clip


def _reference(row, position, graph, source, aid):
    if graph:
        node = position
        pin = node['parameters']
        if (node['definition_id'] != 'asset_reference' or pin.get('asset_id') != aid or
                not any(state['node_id'] == node['id'] and state['state'] in {'CURRENT', 'STALE'}
                        for state in row['reference_states'])):
            return None
        pin = {'kind': 'ASSET', 'id': pin['asset_id'], 'version': pin['version'],
               'digest': pin['digest'], 'asset_kind': pin['kind']}
        location = {'node_id': node['id'], 'definition_id': node['definition_id']}
    else:
        track, clip = position
        pin = clip['source_snapshot']
        if pin['id'] != aid or pin.get('kind') != 'ASSET':
            return None
        location = {'track_id': track, 'clip_id': clip['id']}
    return {'owner': 'CREATIVE_GRAPH' if graph else 'STUDIO_TIMELINE',
            'id': row['id'], 'version': row['version'],
            'digest': row['definition_digest' if graph else 'timeline_digest'],
            **location, 'source': deepcopy(pin), 'current_source': deepcopy(source),
            'state': 'CURRENT' if pin == source else 'STALE'}


def paged_usages(service, nid, scope, actor, aid, guard, *, graph, limit, cursor=None, state=None,
                 production=None, sources=None):
    from contextlib import ExitStack
    from .asset_usage_budget import usage_read_budget
    with ExitStack() as contexts:
        contexts.enter_context(service.store.existing_owner_only())
        if production is not None:
            contexts.enter_context(production.store.existing_owner_only())
        contexts.enter_context(usage_read_budget())
        return _paged_usages(service, nid, scope, actor, aid, guard, graph=graph, limit=limit,
                             cursor=cursor, state=state, production=production, sources=sources)


def _paged_usages(service, nid, scope, actor, aid, guard, *, graph, limit, cursor=None, state=None,
                  production=None, sources=None):
    from .asset_usages import _source, _result
    if type(limit) is not int or not 1 <= limit <= 200 or state not in {None, 'CURRENT', 'STALE'}:
        raise ValueError('STUDIO_USAGE_QUERY_INVALID')
    if cursor is not None and (not isinstance(cursor, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', cursor)):
        raise ValueError('STUDIO_USAGE_QUERY_INVALID')
    if sources is None:
        owners = [('CREATIVE_GRAPH', service)] if graph else [('STUDIO_TIMELINE', service)]
        owner = owners[0][0]
    else:
        if sources not in [['graph'], ['timeline'], ['graph', 'timeline']]:
            raise ValueError('STUDIO_USAGE_QUERY_INVALID')
        owners = []
        if 'graph' in sources:
            owners.append(('CREATIVE_GRAPH', service))
        if 'timeline' in sources:
            if production is None:
                raise ValueError('STUDIO_USAGE_SOURCE_UNAVAILABLE')
            owners.append(('STUDIO_TIMELINE', production))
        owner = 'STUDIO_SAVED_ASSET_REFERENCES'
    def discover():
        listing = []
        for name, original in owners:
            reader = original.usage_directory if name == 'CREATIVE_GRAPH' else original.timeline_usage_directory
            listing.extend((name, key, fingerprint) for key, fingerprint in reader(nid, scope, actor, guard))
        return sorted(listing)

    def read(entry):
        name, rid, _ = entry
        original = next(original for selected, original in owners if selected == name)
        reader = original.usage_get if name == 'CREATIVE_GRAPH' else original.timeline_usage_get
        return reader(nid, scope, actor, rid, guard)
    incarnation = service.store.incarnation(nid)
    binding = _hash([str(service.store.root), nid, scope, actor, incarnation, owner,
                     [name for name, _ in owners], aid, limit, state])
    saved = _load(cursor, binding) if cursor else None
    _checkpoint('before_source')
    source = _source(service.workspace, nid, scope, aid, guard)
    _checkpoint('after_source')
    listing = discover()
    fingerprint = _hash([listing, source])
    if saved and saved['fingerprint'] != fingerprint:
        raise StaleSourceError('STUDIO_USAGE_RESTART_REQUIRED')
    consumer, offset = saved['position'] if saved else (0, 0)
    observed = saved['observed'] if saved else 0
    expires = saved['expires'] if saved else time.monotonic() + TOKEN_TTL
    scanned_consumers = scanned_references = 0
    items = []
    stop = False
    response_bytes = 0
    while consumer < len(listing) and scanned_consumers < MAX_CONSUMERS and not stop:
        guard()
        row = read(listing[consumer])
        row_is_graph = listing[consumer][0] == 'CREATIVE_GRAPH'
        scanned_consumers += 1
        # At most one validated owner is resident for projection. The legacy
        # owner parser can validate up to MAX_VALIDATION_REFERENCES separately.
        # Index construction is bounded by the separate original-reader
        # validation allowance, and is explicitly not O(page size).
        positions = list(_positions(row, row_is_graph))
        for index in range(offset, len(positions)):
            position = positions[index]
            if scanned_references >= MAX_REFERENCES or len(items) >= limit:
                stop = True
                break
            item = _reference(row, position, row_is_graph, source, aid)
            if item is not None and (state is None or item['state'] == state):
                size = len(canonical(item).encode('utf-8'))
                if response_bytes + size > MAX_RESPONSE_BYTES - 4096:
                    if not items:
                        raise ValueError('STUDIO_USAGE_RESOURCE_UNAVAILABLE')
                    stop = True
                    break
                items.append(item)
                response_bytes += size
                observed += 1
            scanned_references += 1
            offset = index + 1
        else:
            consumer += 1
            offset = 0
        _checkpoint('after_consumer')
        del row, positions

    def verify():
        guard()
        if (service.store.incarnation(nid) != incarnation or
                _source(service.workspace, nid, scope, aid, guard) != source or
                discover() != listing):
            raise StaleSourceError('STUDIO_USAGE_RESTART_REQUIRED')
        guard()

    _checkpoint('before_issue')
    verify()
    more = consumer < len(listing)
    result = _result(owner, items, source)
    result.update(limit=limit, truncated=False, has_more=more, next_cursor=None,
        observed_count=observed, scanned_consumers=scanned_consumers,
        scanned_references=scanned_references, total=None if more else observed,
        supported_sources=['graph', 'timeline'],
        selected_sources=['graph' if name == 'CREATIVE_GRAPH' else 'timeline' for name, _ in owners],
        excluded_graph_schemas=[6, 7],
        total_scope='VISIBLE_SELECTED_SAVED_DIRECT_ASSET_REFERENCES',
        consistency='VISIBLE_SELECTED_DOUBLE_OBSERVATION',
        consistency_limits={'transient_changes_detected': False, 'strong_aba': False,
                            'durable_snapshot': False, 'token_ttl_seconds': TOKEN_TTL},
        budgets={'consumers_per_page': MAX_CONSUMERS, 'references_per_page': MAX_REFERENCES,
                 'validation_references_per_consumer': MAX_VALIDATION_REFERENCES,
                 'response_bytes': MAX_RESPONSE_BYTES, 'directory_entries_per_collection': MAX_DIRECTORY_ROWS,
                 'scope_document_bytes': UsageReadBudget.MAX_SCOPE_BYTES,
                 'scope_asset_metadata_read_bytes': UsageReadBudget.MAX_READ_BYTES,
                 'scope_asset_metadata_reads': UsageReadBudget.MAX_READS,
                 'authority_reads_in_budget': False,
                 'storage_read_mode': 'BOUNDED_WHOLE_DOCUMENT'})
    if more:
        result['next_cursor'] = _issue({'binding': binding, 'fingerprint': fingerprint,
            'position': (consumer, offset), 'observed': observed, 'expires': expires})
    try:
        _checkpoint('before_return')
        verify()
        if len(canonical(result).encode('utf-8')) > MAX_RESPONSE_BYTES:
            raise ValueError('STUDIO_USAGE_RESOURCE_UNAVAILABLE')
        guard()
    except BaseException:
        if result['next_cursor']:
            with _lock:
                _tokens.pop(result['next_cursor'], None)
        raise
    return result
