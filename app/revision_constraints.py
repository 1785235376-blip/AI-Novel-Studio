"""Small always-on application constraints for opt-in paragraph locks.

Locks live in the original document, including original immutable history. No
experimental IO, model, or feature activation occurs at this persistence fence.
These are authoring constraints, not security or filesystem protection.
"""
from copy import deepcopy
import hashlib
import json

LOCK_ATTRIBUTE = 'aiRevisionLock'


class RevisionConstraintError(RuntimeError):
    code = 'AI_PARAGRAPH_LOCKED_OR_STALE'

    def __init__(self, message='A paragraph is AI-locked or its lock has drifted. Review and explicitly unlock it before AI acceptance.'):
        super().__init__(message)


def node_digest(node):
    value = deepcopy(node)
    attrs = value.get('attrs', {})
    attrs.pop(LOCK_ATTRIBUTE, None)
    if not attrs: value.pop('attrs', None)
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def lock_nodes(document):
    result = []
    def visit(node, path):
        marker = (node.get('attrs') or {}).get(LOCK_ATTRIBUTE)
        if marker is not None: result.append((path, node, marker))
        for index, child in enumerate(node.get('content', [])):
            visit(child, (*path, index))
    visit(document, ())
    return result


def at_path(document, path):
    node = document
    try:
        for index in path: node = node['content'][index]
        return node
    except (KeyError, IndexError, TypeError):
        raise RevisionConstraintError('A locked paragraph was moved or removed. Explicitly unlock before changing its structure.') from None


def marker_id(marker):
    if isinstance(marker, dict) and marker.get('id'): return marker['id']
    return hashlib.sha256(json.dumps(marker, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def active_lock(marker):
    # Unknown/corrupt markers fail closed instead of becoming unlocked.
    return not (isinstance(marker, dict) and marker.get('state') == 'UNLOCKED' and marker.get('id'))


def assert_ai_locks(before, after):
    for path, node, marker in lock_nodes(before):
        if not active_lock(marker): continue
        if not isinstance(marker, dict) or marker.get('state') != 'LOCKED' or not marker.get('id') or marker.get('digest') != node_digest(node):
            raise RevisionConstraintError()
        if at_path(after, path) != node:
            raise RevisionConstraintError()


def preserve_revision_constraints(before, after, source):
    """AI cannot remove markers. Legacy USER Markdown saves retain lock intent.

    Normal documents return unchanged. Manual text/mark changes are permitted,
    retaining the old digest so the lock becomes visibly STALE, never unlocked.
    Only an explicit tombstone carrying the original ID clears lock intent.
    """
    rows = [(p, n, m) for p, n, m in lock_nodes(before) if active_lock(m)]
    if not rows: return after
    if source == 'AI_ACCEPT':
        assert_ai_locks(before, after)
        return after
    result = deepcopy(after)
    for path, node, marker in rows:
        target = at_path(result, path)
        if target.get('type') != node.get('type'):
            raise RevisionConstraintError('Explicitly unlock a paragraph before changing its block type.')
        provided = (target.get('attrs') or {}).get(LOCK_ATTRIBUTE)
        if isinstance(provided, dict) and provided.get('id') == marker_id(marker) and provided.get('state') == 'UNLOCKED':
            continue
        target.setdefault('attrs', {})[LOCK_ATTRIBUTE] = deepcopy(marker)
    return result
