"""Current-authority reads over the original AssetLibraryService history owner."""
from __future__ import annotations
import base64
import copy
import hashlib
import hmac
import json
import re
import secrets
import time
from .audio_asset_history_models import version_view

_CURSOR_KEY = secrets.token_bytes(32)
MAX_CURSOR_BYTES = 8192
MAX_SOURCE_VISITS = 100
MAX_SOURCE_DEPTH = 16
MAX_HISTORY_BYTES = 25 * 1024 * 1024

class HistorySourceUnavailable(FileNotFoundError):
    pass

def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')

def _b64(value):
    return base64.urlsafe_b64encode(value).decode('ascii').rstrip('=')

def _unb64(value):
    return base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True)

class AudioAssetHistoryService:
    def __init__(self, workspace):
        self.workspace = workspace

    def _context(self, nid, scope, actor, aid, authority, limit):
        return hashlib.sha256(_canonical([self.workspace.store.key(nid, scope),
            self.workspace.store.incarnation(nid), actor, aid, authority, limit])).hexdigest()

    def _cursor(self, value, context):
        if value is None:
            return None
        try:
            if not isinstance(value, str) or len(value) > MAX_CURSOR_BYTES:
                raise ValueError()
            encoded, signature = value.split('.')
            raw = _unb64(encoded)
            if not hmac.compare_digest(hmac.new(_CURSOR_KEY, raw, hashlib.sha256).hexdigest(), signature):
                raise ValueError()
            payload = json.loads(raw)
            if set(payload) != {'context', 'expires', 'cursor'} or payload['context'] != context or type(payload['expires']) is not int or payload['expires'] < int(time.time()):
                raise ValueError()
            return payload['cursor']
        except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
            raise ValueError('AUDIO_HISTORY_CURSOR_INVALID') from None

    def _next(self, value, context):
        if value is None:
            return None
        raw = _canonical({'context': context, 'expires': int(time.time()) + 600, 'cursor': value})
        result = _b64(raw) + '.' + hmac.new(_CURSOR_KEY, raw, hashlib.sha256).hexdigest()
        if len(result) > MAX_CURSOR_BYTES:
            raise ValueError('AUDIO_HISTORY_CURSOR_INVALID')
        return result

    def validate_row(self, nid, scope, actor, row):
        """Validate owner-visible history metadata, including private media candidates."""
        branch = scope.get('branch_id')
        if not isinstance(actor, str) or not actor:
            raise FileNotFoundError('AUDIO_HISTORY_UNAVAILABLE')
        if (not isinstance(row, dict) or row.get('novel_id') != nid or row.get('branch_id') != branch
                or type(row.get('version')) is not int or row['version'] < 1
                or not self.workspace.assets._in_scope(row, branch, actor)):
            raise FileNotFoundError('AUDIO_HISTORY_UNAVAILABLE')
        binding = row.get('_project_binding')
        if (not isinstance(binding, dict) or binding.get('scope_key') != self.workspace.store.key(nid, scope)
                or binding.get('incarnation') != self.workspace.store.incarnation(nid)):
            raise FileNotFoundError('AUDIO_HISTORY_UNAVAILABLE')
        if row.get('source_job_id') and row.get('_owner_actor_id') == actor and not row.get('_origin_provenance'):
            origin = row.get('_studio_result_origin')
            if (row.get('kind') not in {'audio', 'image', 'video'} or not isinstance(origin, dict)
                    or origin.get('contract') != 'studio-production-result/1'
                    or origin.get('actor') != actor or origin.get('scope_key') != binding['scope_key']
                    or origin.get('incarnation') != binding['incarnation']
                    or origin.get('job_id') != row.get('source_job_id')
                    or not isinstance(origin.get('request_digest'), str)
                    or not re.fullmatch(r'[a-f0-9]{64}', origin['request_digest'])
                    or 'narrative_production_v2' not in row.get('_required_features', [])
                    or len(json.dumps(origin, ensure_ascii=False).encode('utf-8')) > 24 * 1024):
                raise ValueError('AUDIO_HISTORY_CANDIDATE_INVALID')
            try:
                self.workspace.assets._identifier(origin.get('job_id'), 'job_id')
                self.workspace._production_asset_ids(origin)
                if 'graph_binding' in origin:
                    from .graph_media_binding import validate_graph_binding
                    if origin['graph_binding'] is None:
                        raise ValueError('invalid graph binding')
                    validate_graph_binding(origin['graph_binding'], origin)
                if 'storyboard_shot' in origin:
                    from .production_execution_models import StoryboardShotPin
                    pin = StoryboardShotPin.model_validate(origin['storyboard_shot'])
                    if (not str(origin.get('operation_id', '')).startswith('m7.') or not any(
                            source.get('kind') == 'CREATIVE_DOCUMENT' and
                            (source.get('id'), source.get('version'), source.get('digest')) ==
                            (pin.document_snapshot.id, pin.document_snapshot.version, pin.document_snapshot.digest)
                            for source in origin.get('sources', []))):
                        raise ValueError('invalid storyboard binding')
            except (ValueError, TypeError, KeyError):
                raise ValueError('AUDIO_HISTORY_CANDIDATE_INVALID') from None
            return row
        return self.workspace._validate_asset_row(nid, scope, row)

    def row(self, nid, scope, actor, aid, *, deleted=False):
        value = self.workspace.assets.get(aid, branch_id=scope.get('branch_id'),
            include_deleted=deleted, actor_id=actor)
        return self.validate_row(nid, scope, actor, value)

    def authorize_source(self, nid, scope, actor, guard):
        """Recheck current sources and prove historical pins before projecting IDs."""
        from ..services.audio_asset_history_store import digest, snapshot, ORIGIN
        visits = 0
        traces, chains = {}, {}
        branch = scope.get('branch_id')

        def unavailable():
            raise HistorySourceUnavailable('AUDIO_HISTORY_SOURCE_UNAVAILABLE')

        def scalar_id(value):
            if not isinstance(value, str) or not value or len(value) > 240 or any(ord(c) < 32 or ord(c) == 127 for c in value):
                unavailable()
            return value

        def pin_value(source_id, version, checksum, record_id=None, metadata_digest=None):
            scalar_id(source_id)
            if type(version) is not int or version < 1 or not isinstance(checksum, str) or not re.fullmatch(r'[a-f0-9]{64}', checksum):
                unavailable()
            for optional in (record_id, metadata_digest):
                if optional is not None and (not isinstance(optional, str) or not re.fullmatch(r'[a-f0-9]{64}', optional)):
                    unavailable()
            return (source_id, version, checksum, record_id, metadata_digest)

        def historical(source, pin):
            if source.get('kind') != 'audio':
                unavailable()
            key = digest(source)
            if key not in chains:
                records = self.workspace.assets._audio_history_store.chain(source, guard=guard)
                if not isinstance(records, list) or len(records) > 100:
                    raise ValueError('AUDIO_HISTORY_SOURCE_LIMIT')
                chains[key] = records
            matches = []
            for record in chains[key]:
                guard()
                if record.get('asset_version') != pin[1] or record.get('sha256') != pin[2]:
                    continue
                if pin[3] is not None and record.get('version_id') != pin[3]:
                    continue
                if pin[4] is not None and record.get('metadata_digest') != pin[4]:
                    continue
                matches.append(record)
            if len(matches) != 1:
                unavailable()
            target = matches[0].get('metadata')
            if not isinstance(target, dict) or target.get('deleted_at') or not self.workspace.assets._in_scope(target, branch, actor):
                unavailable()
            self.validate_row(nid, scope, actor, target)
            return target

        def check(row, trail=()):
            nonlocal visits
            guard()
            if not isinstance(row, dict) or len(trail) >= MAX_SOURCE_DEPTH:
                raise ValueError('AUDIO_HISTORY_SOURCE_LIMIT')
            self.validate_row(nid, scope, actor, row)
            row_id = scalar_id(row.get('id'))
            if row_id in trail:
                unavailable()
            declared = row.get('source_asset_ids') or []
            if not isinstance(declared, list) or len(declared) > MAX_SOURCE_VISITS:
                raise ValueError('AUDIO_HISTORY_SOURCE_LIMIT')
            declared = [scalar_id(value) for value in declared]
            pins = []
            origin = row.get('_studio_result_origin')
            if row.get('source_job_id') and not isinstance(origin, dict):
                unavailable()
            if origin is not None:
                if not isinstance(origin, dict) or not isinstance(origin.get('sources'), list) or len(origin['sources']) > MAX_SOURCE_VISITS:
                    unavailable()
                for source in origin['sources']:
                    if not isinstance(source, dict) or source.get('kind') != 'ASSET':
                        unavailable()
                    pins.append(pin_value(source.get('id'), source.get('version'), source.get('digest')))
            parameters = row.get('parameters')
            lineage = parameters.get('asset_lineage_v2') if isinstance(parameters, dict) else None
            if lineage is not None:
                if not isinstance(lineage, dict) or not isinstance(lineage.get('parents', {}), dict):
                    unavailable()
                parents = lineage.get('parents', {})
                if len(parents) > MAX_SOURCE_VISITS:
                    raise ValueError('AUDIO_HISTORY_SOURCE_LIMIT')
                if lineage.get('sources'):
                    unavailable()
                for source_id, source in parents.items():
                    if not isinstance(source, dict):
                        unavailable()
                    pins.append(pin_value(source_id, source.get('version'), source.get('digest')))
            restored = row.get(ORIGIN)
            if restored is not None:
                if (not isinstance(restored, dict) or restored.get('contract') != 'audio-history-restore/1'
                        or restored.get('asset_id') != row_id
                        or restored.get('scope_key') != self.workspace.store.key(nid, scope)
                        or restored.get('incarnation') != row.get('_project_binding', {}).get('incarnation')):
                    unavailable()
                pins.append(pin_value(restored.get('source_asset_id'), restored.get('target_asset_version'),
                    restored.get('target_sha256'), restored.get('target_version_id'), restored.get('target_metadata_digest')))
            if len(declared) + len(pins) > MAX_SOURCE_VISITS:
                raise ValueError('AUDIO_HISTORY_SOURCE_LIMIT')
            pins = list(dict.fromkeys(pins))
            pinned_ids = {pin[0] for pin in pins}
            requirements = pins + [(source_id, None, None, None, None)
                for source_id in dict.fromkeys(declared) if source_id not in pinned_ids]
            projected = []
            for pin in requirements:
                guard()
                visits += 1
                if visits > MAX_SOURCE_VISITS:
                    raise ValueError('AUDIO_HISTORY_SOURCE_LIMIT')
                source_id = pin[0]
                if source_id == row_id or source_id in trail:
                    unavailable()
                try:
                    source = self.row(nid, scope, actor, source_id)
                except FileNotFoundError:
                    unavailable()
                check(source, (*trail, row_id))
                if pin[1] is None:
                    projected.append({'kind': 'ASSET', 'id': source_id, 'state': 'UNVERSIONED_DECLARATION', 'content_verified': False})
                    continue
                is_current = (source.get('version'), source.get('sha256')) == (pin[1], pin[2])
                if not is_current or pin[3] is not None or pin[4] is not None:
                    target = historical(source, pin)
                    check(target, (*trail, row_id))
                projected.append({'kind': 'ASSET', 'id': source_id, 'version': pin[1],
                    'digest': pin[2], 'state': 'CURRENT' if is_current else 'HISTORICAL_VERIFIED', 'content_verified': False})
            guard()
            traces[digest(snapshot(row))] = projected

        def project(record):
            value = version_view(record)
            trace = traces.get(record.get('metadata_digest'))
            if trace is None:
                raise ValueError('AUDIO_HISTORY_SOURCE_UNVERIFIED')
            return {**value, 'sources': copy.deepcopy(trace)}

        check.project = project
        return check

    def run(self, nid, scope, actor, aid, guard, callback):
        guard()
        with self.workspace._asset_scope(nid, scope):
            current = self.row(nid, scope, actor, aid, deleted=True)
            if current.get('kind') != 'audio':
                raise FileNotFoundError('AUDIO_HISTORY_UNAVAILABLE')
            source_guard = self.authorize_source(nid, scope, actor, guard)
            source_guard(current)
            result = callback(source_guard)
            guard()
            return result

    def list(self, nid, scope, actor, aid, guard, *, authority, limit=20, cursor=None):
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError('AUDIO_HISTORY_LIMIT_INVALID')
        context = self._context(nid, scope, actor, aid, authority, limit)
        owner_cursor = self._cursor(cursor, context)
        def operation(source_guard):
            value = self.workspace.assets.audio_history(aid, branch_id=scope.get('branch_id'), actor_id=actor,
                limit=limit, cursor=owner_cursor, guard=guard, authorize_source=source_guard)
            items = value.get('items')
            if not isinstance(items, list) or len(items) > limit:
                raise ValueError('AUDIO_HISTORY_LIMIT_INVALID')
            return {'asset_id': aid, 'current_version': value['current_version'], 'head': value.get('head'),
                'coverage': value.get('coverage'), 'items': [source_guard.project(row) for row in items],
                'next_cursor': self._next(value.get('next_cursor'), context)}
        return self.run(nid, scope, actor, aid, guard, operation)

    def detail(self, nid, scope, actor, aid, version_id, guard):
        if not isinstance(version_id, str) or not re.fullmatch(r'[a-f0-9]{64}', version_id):
            raise ValueError('AUDIO_HISTORY_VERSION_INVALID')
        def operation(source_guard):
            value = self.workspace.assets.audio_history_detail(aid, version_id, branch_id=scope.get('branch_id'),
                actor_id=actor, guard=guard, authorize_source=source_guard)
            return {'asset_id': aid, 'current_version': value['current_version'], 'head': value.get('head'),
                'version': source_guard.project(value['version'])}
        return self.run(nid, scope, actor, aid, guard, operation)

    def content(self, nid, scope, actor, aid, version_id, guard):
        if not isinstance(version_id, str) or not re.fullmatch(r'[a-f0-9]{64}', version_id):
            raise ValueError('AUDIO_HISTORY_VERSION_INVALID')
        def operation(source_guard):
            value = self.workspace.assets.audio_history_detail(aid, version_id, branch_id=scope.get('branch_id'),
                actor_id=actor, guard=guard, authorize_source=source_guard)
            view = source_guard.project(value['version'])
            data = self.workspace.assets.audio_history_content(aid, version_id, branch_id=scope.get('branch_id'),
                actor_id=actor, max_bytes=MAX_HISTORY_BYTES, guard=guard, authorize_source=source_guard)
            guard()
            return view, data
        return self.run(nid, scope, actor, aid, guard, operation)
