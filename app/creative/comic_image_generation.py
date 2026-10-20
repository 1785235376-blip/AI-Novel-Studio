"""Saved Comic panel adapter to original Image execution and explicit adoption.

No generator, queue, provider, review engine, or Asset owner is introduced.
Comic remains LOCAL_ONLY. Approval and adoption are separate user actions.
"""
from __future__ import annotations

import copy
import hashlib
from contextlib import contextmanager
from pydantic import Field

from .production_contracts import StrictContract, Name, Digest, ProductionSourceSnapshot
from .production_execution_models import MediaCommand, MediaExecutionParameters
from .production_execution import digest
from ..experimental.common import StaleSourceError, check_version
from ..repositories.file.mutation_coordinator import workspace_mutation


class ComicImageRequest(StrictContract):
    expected_version: int = Field(ge=1, strict=True)
    request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")
    provider_id: Name
    model_id: Name
    parameters: MediaExecutionParameters


class ComicImageAdopt(StrictContract):
    expected_version: int = Field(ge=1, strict=True)
    job_id: Name
    expected_job_version: int = Field(ge=1, strict=True)
    expected_request_digest: Digest
    expected_asset_version: int = Field(ge=1, strict=True)
    expected_output_digest: Digest


class ComicImageGeneration:
    def __init__(self, production, comic):
        if (comic.store is not production.store.store or comic.assets is not production.workspace.assets
                or comic.independent_store is not production.store):
            raise ValueError('COMIC_ORIGINAL_PRODUCTION_OWNER_REQUIRED')
        self.production, self.comic = production, comic

    @staticmethod
    def flags():
        from ..experimental.flags import require_flag
        for flag in ('comic_layouts_v2', 'asset_lineage_v2', 'ai_director_v2'):
            require_flag(flag)

    def _saved(self, nid, scope, actor, rid, panel_id, expected_version=None):
        self.flags()
        row = self.comic._row(nid, scope, actor, rid)
        if expected_version is not None:
            check_version(row, expected_version)
        self.comic._current(nid, scope, actor, row)
        panel = next((p for p in row['document']['panels'] if p['id'] == panel_id), None)
        if panel is None:
            raise FileNotFoundError(panel_id)
        if panel.get('artwork_mode', 'IMAGE') != 'IMAGE' or not panel.get('image_brief', '').strip():
            raise ValueError('COMIC_IMAGE_PANEL_BRIEF_REQUIRED')
        if panel.get('appearance_references'):
            raise ValueError('COMIC_IMAGE_APPEARANCE_REFERENCES_UNSUPPORTED')
        return row, panel

    def snapshot(self, nid, scope, actor, row, panel):
        return ProductionSourceSnapshot.model_validate({
            'kind': 'COMIC_PANEL', 'id': row['id'], 'version': row['version'],
            'digest': digest({key: value for key, value in row.items() if key != 'history'}),
            'comic_panel': {'panel_id': panel['id'], 'panel_digest': digest(panel),
                'brief_digest': digest(panel['image_brief']), 'actor': actor,
                'scope_key': self.production.store.key(nid, scope),
                'incarnation': self.production.store.incarnation(nid)}}).model_dump(exclude_none=True, exclude={'reference_only'})

    def source(self, nid, scope, value, guard):
        snapshot = ProductionSourceSnapshot.model_validate(value).model_dump(exclude_none=True, exclude={'reference_only'})
        if snapshot['kind'] != 'COMIC_PANEL':
            raise ValueError('COMIC_IMAGE_SOURCE_REQUIRED')
        pin = snapshot['comic_panel']
        with self.production.store.existing_owner_only():
            row, panel = self._saved(nid, scope, pin['actor'], snapshot['id'], pin['panel_id'], snapshot['version'])
            if snapshot != self.snapshot(nid, scope, pin['actor'], row, panel):
                raise StaleSourceError('COMIC_IMAGE_SOURCE_CHANGED')
        guard()
        return {'snapshot': copy.deepcopy(snapshot), 'row': row}

    def current(self, nid, scope, context, guard):
        command = MediaCommand.model_validate(context['command'])
        sources = [source.model_dump(exclude_none=True, exclude={'reference_only'}) for source in command.source_snapshots]
        if len(sources) != 1 or sources != context['sources'] or sources[0]['kind'] != 'COMIC_PANEL':
            raise ValueError('COMIC_IMAGE_SOURCE_COMMAND_CHANGED')
        pin = sources[0]['comic_panel']
        if (any(pin[key] != context[key] for key in ('actor', 'scope_key', 'incarnation'))
                or digest(command.prompt) != pin['brief_digest'] or context.get('graph_binding') is not None):
            raise StaleSourceError('COMIC_IMAGE_SOURCE_CONTEXT_CHANGED')
        return self.source(nid, scope, sources[0], guard)

    @contextmanager
    def queue_phase(self, nid, scope, context, guard):
        with self.production.store.existing_owner_only(), self.production.store.source_lease(nid, scope):
            with (self.comic.assets._lock, workspace_mutation(self.comic.assets.root, 'asset-library'),
                    self.production.store.owner_lease(nid)):
                self.current(nid, scope, context, guard)
                guard()
                yield
                self.current(nid, scope, context, guard)

    def image_request(self, nid, scope, actor, rid, panel_id, value, guard):
        body = ComicImageRequest.model_validate(value)
        with self.production.store.existing_owner_only(), self.production.store.source_lease(nid, scope):
            self.production._base(nid, scope, actor, guard)
            row, panel = self._saved(nid, scope, actor, rid, panel_id, body.expected_version)
            snapshot = self.snapshot(nid, scope, actor, row, panel)
            if body.parameters.width is None and body.parameters.size is None:
                raise ValueError('COMIC_IMAGE_EXPLICIT_DIMENSIONS_REQUIRED')
            command = MediaCommand.model_validate({'operation_id': 'm5.image.t2i', 'request_id': body.request_id,
                'provider_id': body.provider_id, 'model_id': body.model_id,
                'parameters': body.parameters.model_dump(exclude_none=True), 'prompt': panel['image_brief'],
                'source_snapshots': [snapshot], 'allow_cloud': False})
            binding = self.production._binding(command)
            if not binding['local']:
                raise ValueError('COMIC_IMAGE_LOCAL_PROVIDER_REQUIRED')
            # Use the original passive normalization (including its request-ID
            # seed resolution) before returning a prepared command for consent.
            # A later preview/create sees precisely the same resolved options.
            preview, _, _ = self.production.preview(nid, scope, actor, command, guard)
            guard()
            wire = preview['command']
            return {'contract': 'studio-comic-image-request/1', 'source_snapshot': wire['source_snapshots'][0],
                'command': wire, 'automatic_dispatch': False, 'model_called': False,
                'output_policy': 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW', 'product_acceptance': 'LOCAL_REQUIRED'}

    def adopt(self, nid, scope, actor, rid, panel_id, value, guard):
        body = ComicImageAdopt.model_validate(value)
        self.flags()
        production = self.production
        jobs = production._image(actor)
        # Original queue -> original scope -> asset -> project order. No job
        # lookup occurs under assets, and no provider work occurs in this phase.
        with production.store.existing_owner_only(), jobs._lock, workspace_mutation(jobs.root, 'image-jobs'):
            job, context = production._row(nid, scope, actor, 'image', body.job_id, guard)
            view = production.view(job, 'image')
            candidate = view['output_candidate']
            if (job['status'] != 'APPROVED' or job['version'] != body.expected_job_version
                    or job['request_digest'] != body.expected_request_digest or candidate is None
                    or candidate['digest'] != body.expected_output_digest
                    or view['approved_asset_version'] != body.expected_asset_version):
                raise StaleSourceError('COMIC_IMAGE_APPROVED_JOB_CHANGED')
            sources = context['sources']
            if (len(sources) != 1 or sources[0]['kind'] != 'COMIC_PANEL' or sources[0]['id'] != rid
                    or sources[0]['version'] != body.expected_version or sources[0]['comic_panel']['panel_id'] != panel_id):
                raise StaleSourceError('COMIC_IMAGE_JOB_PANEL_MISMATCH')
            def approved_asset():
                self.current(nid, scope, context, guard)
                with production.workspace._asset_scope(nid, scope):
                    meta = production.workspace.assets.get(candidate['id'], branch_id=scope.get('branch_id'), actor_id=actor)
                    if (meta.get('version') != body.expected_asset_version or meta.get('version') != candidate['version'] + 1
                            or meta.get('sha256') != body.expected_output_digest or meta.get('kind') != 'image'
                            or meta.get('_owner_actor_id') is not None or meta.get('deleted_at') or not meta.get('approved_at')
                            or meta.get('novel_id') != nid or meta.get('branch_id') != scope.get('branch_id')
                            or meta.get('source_job_id') != body.job_id or meta.get('_required_features') != ['narrative_production_v2']
                            or meta.get('_origin_provenance') != production._approved_media_provenance(job, 'image', actor)
                            or meta.get('_studio_result_origin') != production._media_result_origin(context, body.job_id)
                            or meta.get('_project_binding') != {'novel_id': nid, 'branch_id': scope.get('branch_id'),
                                'scope_key': context['scope_key'], 'incarnation': context['incarnation']}):
                        raise StaleSourceError('COMIC_IMAGE_APPROVED_ASSET_CHANGED')
                    data = production.workspace.assets.content(meta['id'], branch_id=scope.get('branch_id'), actor_id=actor)
                    if hashlib.sha256(data).hexdigest() != body.expected_output_digest or len(data) != meta['size']:
                        raise StaleSourceError('COMIC_IMAGE_APPROVED_BYTES_CHANGED')
                    guard()
                    return meta
            return self.comic.adopt_generated_image(nid, scope, actor, rid, panel_id,
                body.expected_version, approved_asset, guard)
