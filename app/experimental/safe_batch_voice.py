"""U16 capability wrapper around the existing B03 queue, executor and assets.

No TTS implementation, queue or cost store lives here. Batch marking conceals
adopted jobs from generic controls. Only exact original broker AUDIO admission
can authorize a send; localhost alone is never evidence of a zero fee.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from .flags import enabled_flags

_context = ContextVar('safe_batch_voice', default=None)


def batch_voice_visible(row):
    binding = row.get('safe_batch_binding')
    if not binding: return True
    current = _context.get()
    return 'safe_batches_v2' in enabled_flags() and current is not None and all(binding.get(k) == current.get(k) for k in ('id', 'actor', 'scope'))


@contextmanager
def voice_context(ctx, batch_id):
    token = _context.set({'id': batch_id, 'actor': ctx.actor, 'scope': deepcopy(ctx.scope)})
    try: yield
    finally: _context.reset(token)


class BatchVoiceAuthority:
    def __init__(self, voice, executor_factory, resolver):
        self.voice, self.executor_factory, self.resolver = voice, executor_factory, resolver

    def job(self, ctx, jid, batch_id=None, current=True):
        with voice_context(ctx, batch_id):
            executor = self.executor_factory(ctx.scope, ctx.actor)
            job = executor.find(executor.store.load(ctx.novel_id), jid)
            binding = job.get('direction_binding', {})
            if job.get('experimental_origin') != 'voice_direction_v2' or binding.get('actor') != ctx.actor or binding.get('scope') != ctx.scope: raise FileNotFoundError('voice task unavailable')
            if current: self.voice.as_actor(ctx.actor, self.voice.assert_job, ctx.novel_id, ctx.scope, ctx.actor, job)
            plan = self.voice.owned_plan(ctx.novel_id, ctx.scope, ctx.actor, binding['plan_id'], current=current)
            segment = next((s for s in plan['segments'] if s['id'] == binding['segment_id']), None)
            if segment is None: raise FileNotFoundError('voice segment unavailable')
            profile = self.voice.as_actor(ctx.actor, self.voice.get, ctx.novel_id, ctx.scope, self.voice.PROFILES, segment['profile_id'])
            records = [plan, profile]
            if segment.get('character_id') not in {None, '__narrator__'}:
                records.append(self.voice._character(ctx.novel_id, ctx.scope, segment['character_id']))
            if any(r.get('hidden') or r.get('secret') or str(r.get('visibility', '')).upper() in {'PRIVATE', 'SECRET', 'DENIED'} for r in records): raise FileNotFoundError('voice source unavailable')
            return job

    def catalog(self, ctx):
        executor = self.executor_factory(ctx.scope, ctx.actor); result = []
        for job in executor.store.load(ctx.novel_id)['jobs']:
            if job.get('experimental_origin') != 'voice_direction_v2' or job.get('safe_batch_binding') or job['status'] not in {'QUEUED', 'SUCCEEDED'}: continue
            try: self.job(ctx, job['id'])
            except (FileNotFoundError, ValueError): continue
            result.append({'id': job['id'], 'chapter_id': job['chapter_id'], 'segment_id': job['direction_binding']['segment_id'], 'provider_id': job['provider_id'], 'model_id': job['model_id'], 'request_digest': job['request_sha256'], 'status': job['status'], 'approval_status': job['approval_status']})
        return result[-100:]

    def snapshot(self, ctx, item, batch_id=None):
        job = self.job(ctx, item.voice_job_id, batch_id)
        if job['request_sha256'] != item.expected_voice_digest: raise ValueError('BATCH_VOICE_REQUEST_CHANGED')
        if not batch_id and job['status'] not in {'QUEUED', 'SUCCEEDED'}: raise ValueError('BATCH_VOICE_NEW_PREVIEW_REQUIRES_ORIGINAL_QUEUED_JOB')
        if job.get('max_cost') != 0 or job.get('local_only') is not True: raise ValueError('BATCH_VOICE_ORIGINAL_ZERO_LOCAL_APPROVAL_REQUIRED')
        return {k: deepcopy(job.get(k)) for k in ('id', 'chapter_id', 'request_sha256', 'source_version', 'source_content_sha256', 'direction_binding', 'provider_id', 'model_id', 'local_only', 'max_cost')}

    def dispatch(self, ctx, rid, index, item, guard, before_send):
        with voice_context(ctx, rid):
            executor = self.executor_factory(ctx.scope, ctx.actor)
            def bind(state):
                job = executor.find(state, item.voice_job_id)
                self.voice.as_actor(ctx.actor, self.voice.assert_job, ctx.novel_id, ctx.scope, ctx.actor, job)
                if job['request_sha256'] != item.expected_voice_digest: raise ValueError('BATCH_VOICE_REQUEST_CHANGED')
                binding = {'id': rid, 'actor': ctx.actor, 'scope': deepcopy(ctx.scope), 'index': index}
                if job.get('safe_batch_binding') not in (None, binding): raise ValueError('BATCH_VOICE_ALREADY_OWNED')
                if job['status'] != 'QUEUED': raise ValueError('BATCH_ORIGINAL_VOICE_NOT_QUEUED')
                guard(); job['safe_batch_binding'] = binding
                return job
            executor.store.mutate(ctx.novel_id, bind)
            return self.voice.as_actor(ctx.actor, self.voice.execute_local_job, ctx.novel_id, ctx.scope, ctx.actor, item.voice_job_id, executor, self.resolver, guard, before_send)

    def result(self, ctx, job):
        if job['status'] != 'SUCCEEDED' or not job.get('asset_id'): raise ValueError('BATCH_VOICE_RESULT_UNAVAILABLE')
        asset = self.voice.assets.get(job['asset_id'], branch_id=ctx.scope.get('branch_id'), actor_id=ctx.actor)
        self.voice.assets.content(asset['id'], branch_id=ctx.scope.get('branch_id'), actor_id=ctx.actor)
        return {'job_id': job['id'], 'asset_id': asset['id'], 'asset_version': asset['version'], 'approval_status': job['approval_status'], 'duration_ms': job['duration_ms'], 'media_type': asset['media_type'], 'verification': 'ORIGINAL_AUDIO_DECODER_NOT_VOICE_QUALITY'}

    def retry(self, ctx, rid, item):
        with voice_context(ctx, rid):
            executor = self.executor_factory(ctx.scope, ctx.actor)
            job = self.job(ctx, item['voice_job_id'], rid)
            if job['status'] == 'FAILED': executor.transition(ctx.novel_id, job['id'], 'QUEUED')
            elif job['status'] != 'QUEUED': raise ValueError('BATCH_ORIGINAL_VOICE_NOT_FAILED')

    def approve(self, ctx, rid, jid, asset_version, guard):
        with voice_context(ctx, rid):
            executor = self.executor_factory(ctx.scope, ctx.actor); job = self.job(ctx, jid, rid)
            if job['status'] != 'SUCCEEDED': raise ValueError('BATCH_VOICE_RESULT_UNAVAILABLE')
            asset = self.voice.assets.get(job['asset_id'], branch_id=ctx.scope.get('branch_id'), actor_id=ctx.actor)
            if job['approval_status'] == 'APPROVED':
                if asset['version'] != asset_version: raise ValueError('BATCH_VOICE_ASSET_CHANGED')
                return self.result(ctx, job)
            asset = self.voice.assets.promote_owned(job['asset_id'], actor_id=ctx.actor, branch_id=ctx.scope.get('branch_id'), expected_version=asset_version,
                provenance={'job_id': jid, 'direction_binding': job['direction_binding'], 'source_version': job['source_version'], 'source_digest': job['source_content_sha256'], 'safe_batch_id': rid}, guard=guard)
            def accept(state):
                current = executor.find(state, jid); guard()
                if current['request_sha256'] != job['request_sha256']: raise ValueError('BATCH_VOICE_REQUEST_CHANGED')
                current.update(approval_status='APPROVED', asset_version=asset['version']); return current
            return self.result(ctx, executor.store.mutate(ctx.novel_id, accept))
