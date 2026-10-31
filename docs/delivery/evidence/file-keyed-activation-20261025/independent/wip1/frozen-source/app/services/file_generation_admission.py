"""Trusted new-key File admission; generic preparation never binds a Job."""
from copy import deepcopy


def prepare_admission(manager, owner, novels, chapters, operation, payload, actor, scope, branch):
    from ..config import settings
    from ..jobs import JobManager, runtime
    # Eligibility is a request-mode choice. Bad composition within this mode
    # refuses below, never falls through to legacy unbound execution.
    if (owner.backend != 'file' or settings.enable_collaboration_runtime
            or settings.enable_narrative_context or actor is not None or scope is not None or branch
            or operation not in {'continue', 'rewrite'} or payload.get('profile', 'LOCAL_ONLY') != 'LOCAL_ONLY'
            or any(payload.get(key) for key in ('source', 'selected_text', 'style_profile_id', 'plot_plan_id',
                'creation_records', 'expected_request_digest', 'variant_group_id', 'request_scope'))
            or getattr(getattr(manager, 'contexts', None), 'enable_narrative_context', False)):
        return None
    from .file_generation_execution import classify_route
    route = classify_route(runtime, payload)
    if route is None:
        return None
    if type(manager) is not JobManager:
        raise ValueError('GENERATION_WRITER_MANAGER_UNVERIFIED')
    pins = manager._file_writer_pins
    pins.validate()
    root = manager._file_review_pins.validate()
    from .novel_service import NovelService
    if (type(novels) is not NovelService or chapters is not manager.chapters
            or novels.novels is not pins.novels or owner.root != root or pins.root != root):
        raise ValueError('GENERATION_WRITER_API_PORT_MISMATCH')
    return _Admission(manager, owner, novels, chapters, operation, deepcopy(payload), route)


class _Admission:
    def __init__(self, manager, owner, novels, chapters, operation, payload, route):
        self.manager, self.owner, self.novels, self.chapters = manager, owner, novels, chapters
        self.operation, self.payload, self.route = operation, payload, route
        self.ports = None

    def capture(self, incarnation):
        self.ports = self.manager._file_writer_pins.prepare_source(
            self.payload['novel_id'], self.payload['chapter_id'], incarnation)

    def revalidate(self, manager, novels, chapters):
        from ..config import settings
        if (manager is not self.manager or novels is not self.novels or chapters is not self.chapters
                or settings.enable_collaboration_runtime or settings.enable_narrative_context
                or novels.novels is not self.manager._file_writer_pins.novels):
            raise ValueError('GENERATION_WRITER_API_PORT_CHANGED')
        self.manager._file_review_pins.validate()
        self.ports.source()

    def prepare(self, authorization):
        from .generation_project_binding import IDENTITY_FIELDS, ordinary_job_binding
        from .file_generation_execution import bind
        # Source get in original prepare_job may lazily migrate chapter data.
        # The inherited expectation is consumed by its original File guards.
        with self.ports.guard():
            job = self.manager.prepare_job(self.operation, self.payload, request_authorization=authorization)
        binding = {'schema_version': 2, 'project_incarnation': self.ports.binding['project_incarnation'],
            'job_id': job.id, 'project_id': job.novel_id,
            'base_chapter_version': job.base_chapter_version, 'base_chapter_digest': job.base_chapter_digest,
            **{key: deepcopy(getattr(job, key)) for key in IDENTITY_FIELDS}}
        job.ordinary_project_binding = binding
        ordinary_job_binding(job.record())
        self.ports = self.manager._file_writer_pins.prepare(binding)
        job._ordinary_read_verifier = self.manager._ordinary_record_available
        bind(self.manager, job, self.ports, self.route)
        return job
