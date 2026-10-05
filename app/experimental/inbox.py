"""Unified projection and dispatch, never a second approval authority.

Each binding owns listing, scope validation and the actual review transition.
Batch processing has an explicit per-item checkpoint receipt, never an implied
cross-domain transaction or an unversioned approve-all operation.
"""
from __future__ import annotations
import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Callable
from .common import check_version
from .flags import enabled_flags


@dataclass(frozen=True)
class ReviewContext:
    novel_id: str
    scope: dict
    actor: str
    token: str | None = None
    branch: str | None = None


@dataclass(frozen=True)
class ReviewBinding:
    domain: str
    list_items: Callable
    review: Callable | None = None
    feature: str | None = None
    batch_actions: frozenset[str] = frozenset()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), default=str).encode()).hexdigest()


def legacy_version(row):
    # Old objects without CAS versions get a content-bound inbox review token.
    # The domain adapter rechecks under its original service lock before dispatch.
    return int(digest(row)[:12], 16) + 1


class UnifiedReviewInbox:
    def __init__(self):
        self.bindings: dict[str, ReviewBinding] = {}

    def register(self, binding):
        if binding.domain in self.bindings:
            raise ValueError('duplicate inbox domain')
        self.bindings[binding.domain] = binding

    def _binding(self, domain):
        binding = self.bindings.get(domain)
        if not binding or (binding.feature and binding.feature not in enabled_flags()):
            raise FileNotFoundError(domain)
        return binding

    @staticmethod
    def _normalize(binding, context, row):
        item = copy.deepcopy(row)
        rid = str(item.get('id') or item.get('item_id') or '')
        if not rid:
            raise ValueError('domain returned review item without id')
        if item.get('novel_id', context.novel_id) != context.novel_id or item.get('scope', context.scope) != context.scope:
            raise ValueError('review projection escaped its authorized scope')
        allowed = list(item.get('allowed_actions') or []) if binding.review else []
        item.update(id=rid, domain=binding.domain, novel_id=context.novel_id,
                    project=context.novel_id, workspace=context.scope.get('workspace_id'),
                    branch=context.scope.get('branch_id'), scope=copy.deepcopy(context.scope),
                    source=item.get('source', binding.domain),
                    source_versions=item.get('source_versions', item.get('sources', {})),
                    source_hash=item.get('source_hash') or digest(item.get('sources', item.get('source_versions', {}))),
                    created_by=item.get('created_by', item.get('actor_id', 'UNKNOWN')),
                    status=item.get('status', 'UNKNOWN'), stale=bool(item.get('stale', False)),
                    risk=item.get('risk', 'REVIEW_REQUIRED'),
                    privacy_state=item.get('privacy_state', item.get('privacy_level', 'LOCAL_ONLY')),
                    preview=item.get('preview', item.get('title', '')),
                    target=item.get('target', {'id': rid, 'domain': binding.domain}),
                    version=item.get('version', legacy_version(row)),
                    allowed_actions=allowed,
                    batch_safe=bool(binding.batch_actions.intersection(allowed)),
                    batch_actions=sorted(binding.batch_actions.intersection(allowed)))
        return item

    def list(self, context, *, domain=None, status=None, search=None, stale=None):
        bindings = [self._binding(domain)] if domain else [b for b in self.bindings.values() if not b.feature or b.feature in enabled_flags()]
        rows = []
        unavailable = []
        for binding in bindings:
            projected = binding.list_items(context)
            if isinstance(projected, dict):
                unavailable.extend(projected.get('unavailable', []))
                projected = projected.get('items', [])
            rows.extend(self._normalize(binding, context, row) for row in projected)
        if status:
            rows = [r for r in rows if r['status'] == status]
        if stale is not None:
            rows = [r for r in rows if r['stale'] == stale]
        if search:
            needle = search.casefold()
            rows = [r for r in rows if needle in json.dumps([r['domain'], r['source'], r['preview'], r['target']], ensure_ascii=False).casefold()]
        rows.sort(key=lambda r: (r.get('created_at', ''), r['domain'], r['id']), reverse=True)
        return {'items': rows, 'total': len(rows), 'unavailable': unavailable,
                'approval_authority': 'DOMAIN_SERVICE', 'batch_semantics': 'PER_ITEM_CHECKPOINT'}

    def get(self, context, domain, item_id):
        rows = self.list(context, domain=domain)['items']
        item = next((r for r in rows if r['id'] == item_id), None)
        if item is None:
            raise FileNotFoundError(item_id)
        return item

    def review(self, context, domain, item_id, action, expected_version):
        binding = self._binding(domain)
        item = self.get(context, domain, item_id)
        check_version(item, expected_version)
        if not binding.review or action not in item['allowed_actions']:
            raise ValueError('this action requires its original domain review flow')
        # This callback invokes that domain's service or original authenticated
        # route. The inbox never changes Canon, artifacts or domain status itself.
        return binding.review(context, item_id, action, expected_version)

    def batch(self, context, items, reauthorize):
        identities = [(i.domain, i.id) for i in items]
        if len(set(identities)) != len(identities):
            raise ValueError('duplicate review item in batch')
        # Validate all explicit targets before any mutation.
        for request in items:
            binding = self._binding(request.domain)
            current = self.get(context, request.domain, request.id)
            check_version(current, request.expected_version)
            if request.action not in binding.batch_actions or request.action not in current['allowed_actions']:
                raise ValueError('domain/action does not permit batch review')
        results = []
        for request in items:
            try:
                reauthorize()
                result = self.review(context, request.domain, request.id, request.action, request.expected_version)
                results.append({'domain': request.domain, 'id': request.id, 'status': 'SUCCEEDED', 'result': result})
            except Exception as exc:
                # Successful prior domain transactions remain committed. Return
                # their identities so the UI never silently repeats them.
                from fastapi import HTTPException
                if isinstance(exc, HTTPException):
                    code = f'HTTP_{exc.status_code}'
                elif hasattr(exc, 'current'):
                    code = 'VERSION_CONFLICT'
                else:
                    code = type(exc).__name__
                results.append({'domain': request.domain, 'id': request.id, 'status': 'FAILED', 'code': code})
                return {'status': 'PARTIAL' if len(results) > 1 else 'FAILED', 'results': results, 'remaining': len(items)-len(results), 'retry': 'REFRESH_AND_SELECT_FAILED_ITEMS'}
        return {'status': 'COMPLETED', 'results': results, 'remaining': 0}
