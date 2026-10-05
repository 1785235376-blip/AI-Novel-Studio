"""Bounded read-only U07 view of the original author JobManager.

Only the manager's recent identifier window is inspected. Each candidate still
passes the original generation endpoint, including its origin feature gates.
Nothing here executes, retries, persists or creates a second task authority.
"""
from copy import deepcopy
from itertools import islice

from fastapi import HTTPException

from ..jobs import require_generation_content
from .ux import safe_code

MAX_AUTHOR_TASK_SCAN = 1000
MAX_AUTHOR_TASKS = 200


def _owned(ctx, job):
    if job.novel_id != ctx.novel_id:
        return False
    if ctx.scope.get('mode') == 'local':
        return ctx.actor == 'local-author' and not ctx.branch and not job.scope and not job.actor_id and not job.workspace_id
    raw = job.scope
    return (ctx.scope.get('mode') == 'collaboration' and isinstance(raw, dict)
            and ctx.branch == ctx.scope.get('branch_id') and bool(ctx.branch)
            and job.actor_id == ctx.actor and job.workspace_id == ctx.scope.get('workspace_id')
            and raw.get('kind') == 'BRANCH' and raw.get('project_id') == ctx.novel_id
            and all(raw.get(key) == ctx.scope.get(key) for key in ('workspace_id', 'storyline_id', 'branch_id')))


def create_author_task_reader(manager, authorize, require_flag, read_generation):
    """Inject the existing generation read, not an alternate authorization path."""
    def read(ctx):
        def current():
            require_flag('workspace_tools_v2')
            if authorize(ctx.novel_id, ctx.token, ctx.branch, 'domain.read') != (ctx.actor, ctx.scope):
                raise HTTPException(403, {'code': 'AUTHOR_TASK_AUTHORITY_CHANGED'})

        def source(jid):
            job = manager.get(jid)
            if not _owned(ctx, job):
                return None
            require_generation_content(job)
            chapter = manager.chapters.get(job.chapter_id)
            if (chapter.get('id') != job.chapter_id or chapter.get('novel_id') != ctx.novel_id
                    or chapter.get('is_archived') or type(job.base_chapter_version) is not int
                    or job.base_chapter_version < 1):
                return None
            return job, chapter

        current()
        # Snapshot IDs only under the manager lock. Never copy prompt/output or
        # sort/materialize the entire history to render the task center.
        with manager.lock:
            identifiers = tuple(islice(reversed(manager.jobs), MAX_AUTHOR_TASK_SCAN))
        candidates = []
        for jid in identifiers:
            current()
            try:
                before = source(jid)
                if before is None:
                    continue
                state = read_generation(jid, ctx.token)
                current()
                after = source(jid)
                if after is None:
                    continue
                job, chapter = after
                if (state.get('id') != jid or state.get('novel_id') != ctx.novel_id
                        or state.get('chapter_id') != job.chapter_id
                        or state.get('base_chapter_version') != job.base_chapter_version
                        or state.get('actor_id') != job.actor_id or state.get('scope') != job.scope):
                    continue
                candidates.append({'id': jid, 'novel_id': ctx.novel_id, 'scope': deepcopy(ctx.scope),
                    'actor_id': ctx.actor, 'chapter_id': job.chapter_id,
                    'experimental_origin': job.experimental_origin,
                    'base_chapter_version': job.base_chapter_version, 'status': state.get('status', 'UNKNOWN'),
                    'stale': chapter.get('version') != job.base_chapter_version,
                    'error_code': safe_code(state['error_code']) if state.get('error_code') else None})
                # An extra *authorized* visible row establishes has_more. A
                # foreign, denied, missing or origin-OFF row never contributes.
                if len(candidates) > MAX_AUTHOR_TASKS:
                    break
            except (FileNotFoundError, KeyError):
                continue
            except HTTPException as exc:
                if exc.status_code not in {400, 401, 403, 404}:
                    raise
        current()
        result = []
        for row in candidates:
            try:
                latest = source(row['id'])
                if latest is not None and latest[0].chapter_id == row['chapter_id'] and latest[0].base_chapter_version == row['base_chapter_version']:
                    result.append({**row, 'experimental_origin': latest[0].experimental_origin,
                        'stale': latest[1].get('version') != row['base_chapter_version']})
            except (FileNotFoundError, KeyError):
                continue
            except HTTPException as exc:
                if exc.status_code not in {401, 403, 404}:
                    raise
        current()
        return {'items': result[:MAX_AUTHOR_TASKS], 'has_more': len(result) > MAX_AUTHOR_TASKS}
    return read
