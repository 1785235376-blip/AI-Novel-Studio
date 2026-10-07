"""Read-through projections and original-service review dispatch for V1 queues.

Unversioned Canon/media/export gates remain visibly read-only here. Their
original detail flow supplies evidence/selection inputs that a generic inbox
button must not invent. Ownership and branch checks are reused, not weakened.
"""
from __future__ import annotations
from fastapi import HTTPException
from .inbox import ReviewBinding, legacy_version, digest
from .common import check_version


def _row(row, *, preview=None, target=None, allowed=(), version=None, stale=False):
    return {**row, 'preview': preview if preview is not None else row.get('title', row.get('name', '')),
            'target': target or {'id': row['id']}, 'version': version if version is not None else row.get('version', legacy_version(row)),
            'source_hash': digest(row), 'stale': stale, 'allowed_actions': list(allowed), 'batch_safe': False,
            'risk': 'DOMAIN_REVIEW_REQUIRED', 'privacy_state': row.get('privacy_state', row.get('privacy_level', 'UNKNOWN')),
            'execution_target': row.get('target') if isinstance(row.get('target'), str) else None}


def register_legacy_bindings(inbox):
    # Imports are evaluated lazily to avoid API composition cycles and keep
    # tests/host service replacement aligned with the existing route boundary.
    def imports(ctx):
        from .. import api
        rows = api.list_import_knowledge_reviews(ctx.novel_id, None, ctx.token, ctx.branch)['items']
        return [_row(r, preview=r.get('candidates', {}), target={'module': 'import', 'review_id': r['id']}) for r in rows]
    inbox.register(ReviewBinding('legacy_import', imports))

    def creation(ctx):
        from .. import api
        result = api.creation_workbench_service.list_records(ctx.novel_id, ctx.scope)
        out = []
        for row in result['items']:
            stale = False
            for cid, version in row.get('source_versions', {}).items():
                try:
                    current = api.creation_workbench_service.chapters_for(ctx.scope).get(cid)
                    from ..source_privacy import content_digest
                    stale |= current.get('novel_id') != ctx.novel_id or current.get('version') != version or (cid in row.get('source_digests', {}) and content_digest(current) != row['source_digests'][cid])
                except (FileNotFoundError, KeyError):
                    stale = True
            out.append(_row(row, allowed=['approve'] if row['status'] == 'DRAFT' and not stale else [], stale=stale, target={'module': 'creation', 'id': row['id']}))
        return out
    def review_creation(ctx, rid, action, version):
        from .. import api
        actor, scope = api._workbench_authorize(ctx.novel_id, ctx.token, ctx.branch, 'domain.write')
        if actor != ctx.actor or scope != ctx.scope:
            raise ValueError('review scope changed')
        return api.creation_workbench_service.transition_record(ctx.novel_id, ctx.scope, ctx.actor, rid, action, version)
    inbox.register(ReviewBinding('legacy_planning', creation, review_creation))

    def canon(ctx):
        from .flags import enabled_flags
        from .finding_review_composition import CANON_DOMAIN, FEATURE
        replacement = inbox.bindings.get(CANON_DOMAIN)
        if FEATURE in enabled_flags() and replacement is not None and replacement.feature == FEATURE:
            return []
        if ctx.scope['mode'] != 'local':
            return {'items': [], 'unavailable': [{'domain': 'legacy_canon', 'reason': 'LEGACY_CANON_HAS_NO_BRANCH_SCOPE'}]}
        from .. import api
        rows = [_row(r, preview=r.get('proposals', []), target={'module': 'canon', 'id': r['id']}) for r in api.canon_service.list_pending(ctx.novel_id)]
        return rows
    inbox.register(ReviewBinding('legacy_canon', canon))

    def lore(ctx):
        if ctx.scope['mode'] != 'local':
            return {'items': [], 'unavailable': [{'domain': 'legacy_world_rule', 'reason': 'LEGACY_LORE_HAS_NO_BRANCH_SCOPE'}]}
        from .. import api
        return [_row(r, preview=r.get('payload', {}), target={'module': 'world', 'proposal_id': r['id']}) for r in api.lore_service.repository.list_proposals(ctx.novel_id)]
    inbox.register(ReviewBinding('legacy_world_rule', lore))

    def agents(ctx):
        from .. import api
        if not ctx.token:
            return {'items': [], 'unavailable': [{'domain': 'legacy_agent', 'reason': 'ORIGINAL_DOMAIN_REQUIRES_SESSION'}]}
        current = api._agent_job_read_actor(ctx.token)
        api._validate_agent_job_filter(current, ctx.novel_id, ctx.branch, 'domain.read')
        rows, page = [], 1
        while True:
            result = api.agent_job_service.list(novel_id=ctx.novel_id, branch_id=ctx.branch, page=page, page_size=100, visibility=api._agent_job_visibility(ctx.token))
            for row in result['items']:
                if row.get('branch_id') != ctx.branch:
                    continue
                api._agent_job_actor_for_record(ctx.token, row)
                actions = ['approve', 'reject'] if row.get('execution_mode') == 'model' and row['status'] == 'COMPLETED' else []
                rows.append(_row(row, preview=(row.get('result') or {}).get('structured_output', {}), allowed=actions, version=legacy_version(row), target={'module': 'agents', 'job_id': row['id']}))
            if not result['has_more']:
                break
            page += 1
        return rows
    def review_agent(ctx, rid, action, version):
        from .. import api
        with api.agent_job_service.lock:
            row = api.get_agent_job(rid, ctx.token)
            if row['novel_id'] != ctx.novel_id or row.get('branch_id') != ctx.branch:
                raise FileNotFoundError(rid)
            check_version({'version': legacy_version(row)}, version)
            body = api.AgentJobReviewIn(decision='ACCEPTED' if action == 'approve' else 'REJECTED', reviewed_by=ctx.actor, actions=[])
            return api.review_agent_job(rid, body, ctx.token)
    inbox.register(ReviewBinding('legacy_agent', agents, review_agent))

    def workflows(ctx):
        from .. import workflow_api as workflow
        if not ctx.token:
            return {'items': [], 'unavailable': [{'domain': 'legacy_workflow', 'reason': 'ORIGINAL_DOMAIN_REQUIRES_SESSION'}]}
        definitions = workflow.workflows(ctx.novel_id, ctx.token)['items']
        output = []
        for definition in definitions:
            if definition.get('branch_id') != ctx.branch:
                continue
            for run in workflow.runs(definition['id'], ctx.token)['items']:
                for node in run['definition_snapshot']['nodes']:
                    state = run.get('node_states', {}).get(node['id'], {})
                    if node['type'] != 'manual_approval' or state.get('status') != 'WAITING_APPROVAL':
                        continue
                    row = {**run, 'id': run['id'] + ':' + node['id'], 'status': state['status']}
                    output.append(_row(row, preview={'name': node['name'], 'node_state': state}, allowed=['approve', 'reject'], target={'module': 'workflow', 'run_id': run['id'], 'node_id': node['id']}))
        return output
    def review_workflow(ctx, rid, action, version):
        from .. import workflow_api as workflow
        run_id, node_id = rid.split(':', 1)
        with workflow.service._lock:
            _, run = workflow.read_run(run_id, ctx.token, 'domain.review')
            if run['novel_id'] != ctx.novel_id or run.get('branch_id') != ctx.branch:
                raise FileNotFoundError(rid)
            check_version(run, version)
            operation = workflow.approve if action == 'approve' else workflow.reject
            return operation(run_id, node_id, '', ctx.token)
    inbox.register(ReviewBinding('legacy_workflow', workflows, review_workflow))

    def media(ctx):
        from .. import api
        output = []
        for screenplay in api.screenplay_service.list(ctx.novel_id):
            if screenplay.get('branch_id') != ctx.branch:
                continue
            # Original guard validates project, membership and branch before
            # projecting any nested task/artifact metadata.
            api._authorize_motion(ctx.novel_id, screenplay['id'], ctx.token, 'domain.read', ctx.branch)
            for collection, kind in (('asset_tasks', 'IMAGE'), ('motion_tasks', 'VIDEO')):
                for task in screenplay.get(collection, []):
                    row = {**task, 'id': f"{screenplay['id']}:{kind}:{task['id']}"}
                    output.append(_row(row, preview={'kind': kind, 'status': task.get('status'), 'approval_status': task.get('approval_status')}, target={'module': 'media', 'screenplay_id': screenplay['id'], 'task_id': task['id']}))
        for task in api.list_audiobook_jobs(ctx.novel_id, ctx.token, ctx.branch)['items']:
            output.append(_row(task, preview={'kind': 'AUDIO', 'status': task.get('status'), 'approval_status': task.get('approval_status')}, target={'module': 'audio', 'job_id': task['id']}))
        return output
    inbox.register(ReviewBinding('legacy_media', media))

    def gates(ctx):
        from .. import api
        rows = []
        # Release gates lack actor/branch provenance in V1, so only local
        # project gates are displayable. No release or export is triggered.
        if ctx.scope['mode'] == 'local':
            for gate in api.v1_capability_service.list_release_gates(ctx.novel_id)['items']:
                rows.append(_row(gate, preview=gate.get('checks', []), target={'module': 'release', 'gate_id': gate['id']}))
        context = {**ctx.scope, 'actor_id': ctx.actor}
        offset = 0
        while True:
            result = api.export_job_service.list(ctx.novel_id, permission_context=context, limit=100, offset=offset)
            for row in result['items']:
                rows.append(_row(row, preview={'format': row.get('format'), 'status': row.get('status'), 'source_versions': row.get('source_versions')}, target={'module': 'export', 'job_id': row['id']}))
            if result['next_offset'] is None:
                break
            offset = result['next_offset']
        return rows
    inbox.register(ReviewBinding('export_release_gate', gates))
