"""U07 adapters for original task owners; no task persistence or execution loop.

All actions are cancellation only. Retry/resume/review stays with its domain's
preflight, source version, consent and budget authority. New readers preserve
original route authorization and strip opaque payloads before projection.
"""
from dataclasses import replace
from fastapi import HTTPException
from .ux import TaskReader


def extend_workspace_task_readers(readers, legacy, imports, teams, media, audiobook, inbox, authorize, require_flag):
    def guard(ctx, flag=None, permission='domain.write'):
        require_flag('workspace_tools_v2')
        if flag: require_flag(flag)
        if authorize(ctx.novel_id, ctx.token, ctx.branch, permission) != (ctx.actor, ctx.scope):
            raise HTTPException(403, {'code': 'WORKSPACE_AUTHORITY_CHANGED'})

    def transition(service, flag):
        def cancel(ctx, rid, version=None):
            guard(ctx, flag)
            result = service.transition(ctx.novel_id, ctx.scope, ctx.actor, rid, 'cancel', version)
            guard(ctx, flag)
            return result
        return cancel

    def original(function, **extra):
        def cancel(ctx, rid, version=None):
            guard(ctx)
            return function(ctx, rid, **extra)
        return cancel

    from .. import workflow_api
    cancellers = {
        'workflows': (original(lambda ctx, rid: workflow_api.transition(run_id=rid, action='cancel', x_session_token=ctx.token)), frozenset({'QUEUED', 'RUNNING', 'WAITING_APPROVAL', 'PAUSED'})),
        'semantic_import': (transition(imports, 'semantic_import_v2'), frozenset({'QUEUED', 'ANALYZING', 'PAUSED', 'FAILED', 'NEEDS_REVIEW', 'STALE'})),
        'agent_team': (transition(teams, 'agent_team_recipes'), frozenset({'QUEUED', 'RUNNING', 'WAITING_APPROVAL', 'PAUSED'})),
        'media': (transition(media, 'cover_storyboard_generation'), frozenset({'QUEUED', 'RUNNING'})),
        'agents': (original(lambda ctx, rid: legacy.cancel_agent_job(job_id=rid, x_session_token=ctx.token)), frozenset({'QUEUED', 'WORKING'})),
        'exports': (original(lambda ctx, rid: legacy.cancel_export(job_id=rid, x_session_token=ctx.token, x_branch_id=ctx.branch)), frozenset({'QUEUED', 'RUNNING'})),
        'images': (original(lambda ctx, rid: legacy.cancel_image_job(nid=ctx.novel_id, job_id=rid, x_session_token=ctx.token, x_branch_id=ctx.branch)), frozenset({'QUEUED', 'RUNNING'})),
    }
    result = [replace(reader, cancel=cancellers[reader.name][0], cancel_states=cancellers[reader.name][1])
              if reader.name in cancellers else reader for reader in readers]

    def audio(ctx):
        rows = legacy.list_audiobook_jobs(nid=ctx.novel_id, x_session_token=ctx.token, x_branch_id=ctx.branch)['items']
        # Experimental voice jobs have stronger origin/actor bindings and their
        # existing voice_direction projection must remain the only entry.
        return {'items': [{**row, 'novel_id': ctx.novel_id, 'scope': ctx.scope}
                          for row in rows if not row.get('experimental_origin')
                          and row.get('branch_id') in {None, ctx.branch}]}

    def motion(ctx):
        rows = legacy.list_media_tasks(nid=ctx.novel_id, x_session_token=ctx.token, x_branch_id=ctx.branch)['motion']
        return {'items': [{**row, 'novel_id': ctx.novel_id, 'scope': ctx.scope}
                          for row in rows if row.get('branch_id') in {None, ctx.branch}]}

    def cancel_motion(ctx, rid, version=None):
        guard(ctx)
        row = next((row for row in motion(ctx)['items'] if row['id'] == rid), None)
        if row is None: raise FileNotFoundError('motion task')
        return legacy.cancel_motion_task(nid=ctx.novel_id, screenplay_id=row['screenplay_id'], task_id=rid,
                                        x_session_token=ctx.token, x_branch_id=ctx.branch)

    def cancel_voice(ctx, rid, version=None):
        from .voice_direction_api import create_runtime_executor
        from .voice_direction import VOICE_FLAG
        guard(ctx, VOICE_FLAG); require_flag('audiobook_v2')
        executor = create_runtime_executor(ctx.scope, ctx.actor)
        job = executor.find(executor.store.load(ctx.novel_id), rid)
        binding = job.get('direction_binding', {})
        if job.get('experimental_origin') != VOICE_FLAG or binding.get('actor') != ctx.actor or binding.get('scope') != ctx.scope:
            raise FileNotFoundError('voice job')
        guard(ctx, VOICE_FLAG)
        from ..services.audiobook_service import AudiobookError
        try: return executor.transition(ctx.novel_id, rid, 'CANCELLED')
        except AudiobookError as exc: raise HTTPException(exc.status, {'code': exc.code}) from None

    result = [replace(reader, cancel=cancel_voice, cancel_states=frozenset({'QUEUED', 'RUNNING'}))
              if reader.name == 'voice_direction' else reader for reader in result]
    def reviews(ctx):
        from .inbox import ReviewContext
        guard(ctx, 'unified_review_inbox', 'domain.read')
        value = inbox.list(ReviewContext(ctx.novel_id, ctx.scope, ctx.actor, ctx.token, ctx.branch))
        guard(ctx, 'unified_review_inbox', 'domain.read')
        return {'items': [{'id': row['domain'] + ':' + row['id'], 'review_id': row['id'], 'review_domain': row['domain'],
                          'novel_id': ctx.novel_id, 'scope': ctx.scope, 'status': row['status'], 'version': row['version'],
                          'stale': row.get('stale', False)} for row in value['items'][:201]],
                'has_more': len(value['items']) > 200 or bool(value.get('unavailable'))}

    result.extend((
        TaskReader('review_inbox', '原领域待审核项', 'unified_review_inbox', reviews, 'unified_review_inbox'),
        TaskReader('audio_tts', '音频 / TTS 任务', 'audiobook', audio,
                   cancel=original(lambda ctx, rid: legacy.cancel_audiobook_job(nid=ctx.novel_id, job_id=rid, x_session_token=ctx.token, x_branch_id=ctx.branch)),
                   cancel_states=frozenset({'QUEUED', 'RUNNING'})),
        TaskReader('motion', '视频 / Motion 任务', 'screenplay', motion, cancel=cancel_motion,
                   cancel_states=frozenset({'PENDING', 'RUNNING'})),
    ))
    return tuple(result)
