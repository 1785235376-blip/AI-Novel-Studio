"""Bounded CAS for the original adaptation authority, shared by both backends."""
from copy import deepcopy
import json
from .chapter_repository import VersionConflict

MAX_PROPOSALS = 100
MAX_SOURCE_CHAPTERS = 40
MAX_SOURCE_BYTES = 8_000_000
MAX_REVISIONS = 400
FINALIZATION_RESERVE = 32
MAX_PROPOSAL_BYTES = 32_000_000
FINALIZATION_BYTES = 4_000_000
MAX_HISTORY_SNAPSHOT_BYTES = 2_000_000
MAX_MANIFEST_DRAFT_BYTES = 1_000_000
MAX_ATTEMPTS = 10


def size(value): return len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())

def check_revision(current, expected_revision):
    if expected_revision is not None and (type(expected_revision) is not int or expected_revision < 0):
        raise ValueError('ADAPTATION_REVISION_INVALID')
    if expected_revision is not None and int((current or {}).get('revision', 0)) != expected_revision:
        raise VersionConflict({'id': (current or {}).get('id'), 'version': int((current or {}).get('revision', 0))},
                              resource_id=(current or {}).get('id'), expected_version=expected_revision)


def snapshot(row):
    return {key:deepcopy(value) for key,value in row.items() if key not in {'revision_history','source_snapshots'}}


def reserve_transitions(item, transitions):
    """Reject new multi-step work before it can consume recovery headroom."""
    if len(item.get('revision_history',[]))+transitions > MAX_REVISIONS-FINALIZATION_RESERVE:
        raise ValueError('ADAPTATION_CAPACITY_REVISION_LIMIT')
    # Conservative materialization overhead for up to forty receipt/task pairs.
    if size(item)+transitions*(size(snapshot(item))+40_000) > MAX_PROPOSAL_BYTES-FINALIZATION_BYTES:
        raise ValueError('ADAPTATION_CAPACITY_BYTES_LIMIT')


def versioned_adaptation(current, proposed, expected_revision=None, *, finalize=False):
    check_revision(current, expected_revision)
    if current and (current.get('novel_id'), current.get('branch_id')) != (proposed.get('novel_id'), proposed.get('branch_id')):
        raise ValueError('ADAPTATION_SCOPE_IMMUTABLE')
    if len(proposed.get('source_versions',[])) > MAX_SOURCE_CHAPTERS or len(proposed.get('execution_manifest',[])) > MAX_SOURCE_CHAPTERS:
        raise ValueError('ADAPTATION_CAPACITY_SOURCE_LIMIT')
    if size(proposed.get('source_snapshots',[])) > MAX_SOURCE_BYTES:
        raise ValueError('ADAPTATION_CAPACITY_SOURCE_BYTES_LIMIT')
    if size([row.get('draft') for row in proposed.get('execution_manifest',[])]) > MAX_MANIFEST_DRAFT_BYTES:
        raise ValueError('ADAPTATION_CAPACITY_DRAFT_LIMIT')
    history = deepcopy((current or {}).get('revision_history', []))
    if current: history.append(snapshot(current))
    if len(history) > MAX_REVISIONS-(0 if finalize else FINALIZATION_RESERVE):
        raise ValueError('ADAPTATION_CAPACITY_REVISION_LIMIT')
    result = {key:deepcopy(value) for key,value in proposed.items() if key not in {'revision_history','expected_revision'}}
    result['revision'] = int((current or {}).get('revision', 0)) + 1
    result['revision_history'] = history
    if size(snapshot(result)) > MAX_HISTORY_SNAPSHOT_BYTES:
        raise ValueError('ADAPTATION_CAPACITY_SNAPSHOT_LIMIT')
    if size(result) > MAX_PROPOSAL_BYTES-(0 if finalize else FINALIZATION_BYTES):
        raise ValueError('ADAPTATION_CAPACITY_BYTES_LIMIT')
    return result
