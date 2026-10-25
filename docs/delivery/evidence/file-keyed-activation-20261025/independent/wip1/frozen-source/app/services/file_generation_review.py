"""Short-lived composition of original File manual review ports.

No persisted authority and no general ordinary mutation eligibility. A review
context can be consumed only by its original manager/job on its entering thread.
"""
from contextlib import contextmanager
from pathlib import Path
from threading import get_ident
from types import SimpleNamespace


class _ReviewPort:
    def __init__(self, context, owner, names):
        self.context = context
        self.calls = {name: getattr(owner, name) for name in names}

    def __getattr__(self, name):
        original = self.calls[name]
        def call(*args, **kwargs):
            self.context.check()
            if self.context.binding["schema_version"] == 2 and name in {"create", "save"}:
                source = self.context.chapters.get(self.context.job.chapter_id)
                from ..author_request import chapter_digest
                if (source["version"] != self.context.binding["base_chapter_version"]
                        or chapter_digest(source) != self.context.binding["base_chapter_digest"]):
                    raise ValueError("GENERATION_WRITER_SOURCE_CHANGED")
                if name == "create":
                    kwargs["_file_writer"] = self.context.manager._file_writer_pins.prepare(self.context.binding)
                if name == "save":
                    kwargs["_expected_source_digest"] = self.context.binding["base_chapter_digest"]
            return original(*args, **kwargs, _project_incarnation=self.context.binding['project_incarnation'],
                            _project_root=self.context.pins.root.parent.parent)
        return call


class FileReviewPins:
    """Capture objects before restore; legacy managers need not compose them."""
    def __init__(self, manager):
        self.manager = manager
        self.services = (manager.persistence, manager.chapters, manager.canon, manager.memory_extractor)
        from ..services import GenerationService, ChapterService, CanonService
        from ..repositories.file import FileChapterRepository, FileCanonRepository
        self.repositories = tuple(service.repository if type(service) is expected else None
                                  for service, expected in zip(self.services[:3], (GenerationService, ChapterService, CanonService)))
        self.backends = tuple(repository.backend if type(repository) is expected else None
                              for repository, expected in zip(self.repositories[1:], (FileChapterRepository, FileCanonRepository)))
        self.root = manager._ordinary_repository_root

    def validate(self):
        from ..repositories.file import FileGenerationRepository, FileChapterRepository, FileCanonRepository
        from ..repositories.generation_repository import GenerationRepository, GenerationProjectIdentityError
        from ..repository import FileRepository
        from ..services import GenerationService, ChapterService, CanonService
        from ..lore.memory_agent import MemoryAgentRunner
        manager = self.manager
        current = (manager.persistence, manager.chapters, manager.canon, manager.memory_extractor)
        if tuple(type(x) for x in current) != (GenerationService, ChapterService, CanonService, MemoryAgentRunner):
            raise GenerationProjectIdentityError('GENERATION_REVIEW_FILE_PORT_MISMATCH')
        repositories = tuple(service.repository for service in current[:3])
        if (any(a is not b for a, b in zip(current, self.services))
                or any(a is not b for a, b in zip(repositories, self.repositories))
                or tuple(type(x) for x in current) != (GenerationService, ChapterService, CanonService, MemoryAgentRunner)
                or type(repositories[0]) not in (GenerationRepository, FileGenerationRepository)
                or type(repositories[1]) is not FileChapterRepository or type(repositories[2]) is not FileCanonRepository
                or self.root is None or Path(repositories[0].root).resolve() != self.root):
            raise GenerationProjectIdentityError('GENERATION_REVIEW_FILE_PORT_MISMATCH')
        root = self.root.parent.parent
        for repository, backend in zip(repositories[1:], self.backends):
            if (repository.backend is not backend or type(backend) is not FileRepository
                    or Path(backend.data).resolve() != root or Path(backend.novels).resolve() != root/'novels'):
                raise GenerationProjectIdentityError('GENERATION_REVIEW_FILE_PORT_MISMATCH')
        memory = current[3]
        if (memory.chapters is not repositories[1] or memory.generations.repository is not repositories[0]
                or memory._bound_data != root):
            raise GenerationProjectIdentityError('GENERATION_REVIEW_MEMORY_PORT_MISMATCH')
        return root


class _FileReview:
    def __init__(self, pins, job):
        from .generation_project_binding import ordinary_job_binding
        self.pins, self.manager, self.job = pins, pins.manager, job
        self.binding = ordinary_job_binding(job.record())
        self.active = False
        self.thread = None
        self.accept_body_started = False
        self.chapters = _ReviewPort(self, pins.services[1], ('get', 'save', 'create', 'save_summary', 'history'))
        self.canon = _ReviewPort(self, pins.services[2], ('save_pending',))
        self._save = pins.repositories[0].save
        self._read = pins.repositories[0].get
        self._enqueue = pins.services[3].enqueue

    @staticmethod
    def local(job, actor=None, scope=None):
        from ..jobs import generation_required_features, GENERATION_ORIGINS
        from ..config import settings
        from fastapi import HTTPException
        # Current local request authorization is checked before entering the
        # owner lease. No collaborative/preview/source-resolver callback is
        # admitted beneath it, including on a cold restored record.
        try:
            supported = (actor is None and scope is None and not settings.enable_collaboration_runtime
                and all(getattr(job, key, None) is None for key in
                        ('actor_id', 'workspace_id', 'scope', 'scope_type', 'scope_id', 'experimental_origin',
                         'author_context_resolver', 'character_context_resolver', 'character_viewpoint',
                         'author_preparation_guard', 'expected_request_digest', 'revision_selection_binding'))
                and not job.partial_revision_only
                and not ((job.request_scope or {}).get('added_sources'))
                and generation_required_features(job).issubset(GENERATION_ORIGINS['model_broker']))
        except (ValueError, TypeError, AttributeError):
            supported = False
        if not supported:
            raise HTTPException(409, {'code': 'GENERATION_ORDINARY_MUTATION_NOT_INTEGRATED'})

    def check(self):
        from .generation_project_binding import ordinary_job_binding
        from ..repositories.generation_repository import GenerationProjectIdentityError
        if not self.active or self.thread != get_ident() or self.manager.jobs.get(self.job.id) is not self.job:
            raise GenerationProjectIdentityError('GENERATION_REVIEW_CONTEXT_EXPIRED')
        self.local(self.job)
        self.pins.validate()
        # Reentrant injected lifecycle actions must not be mistaken for a
        # continuous owner merely because this thread still owns an RLock.
        from ..file_project_lifecycle import project_operation
        with project_operation(self.pins.root.parent.parent, self.job.novel_id,
                               expected_incarnation=self.binding['project_incarnation']):
            pass
        from ..lore.memory_project_binding import create_binding
        self.pins.services[3]._bound_check(create_binding(self.job.novel_id, self.job.chapter_id, 1,
                                                        self.binding['project_incarnation']))
        if ordinary_job_binding(self.job.record()) != self.binding:
            raise GenerationProjectIdentityError('GENERATION_REVIEW_IDENTITY_CHANGED')
        # This is the original trusted verifier, never an arbitrary callback
        # supplied on a Job or reconstructed from a serialized record.
        if self.job._ordinary_read_verifier != self.manager._ordinary_record_available:
            raise GenerationProjectIdentityError('GENERATION_REVIEW_VERIFIER_CHANGED')

    def claim_accept_body(self, actor=None, scope=None):
        self.check()
        self.local(self.job, actor, scope)
        if self.accept_body_started or self.job.status != 'ACCEPTING':
            raise ValueError('GENERATION_REVIEW_HELPER_ALREADY_CONSUMED')
        self.accept_body_started = True

    def read(self):
        self.check()
        from .generation_project_binding import ordinary_job_binding
        current = self._read(self.job.id)  # Missing is never an injected-cache fallback.
        if ordinary_job_binding(current) != self.binding:
            raise ValueError('GENERATION_REVIEW_DURABLE_IDENTITY_CHANGED')
        return current

    def persist(self):
        self.check()
        self._save(self.job.record(), _expected_root=self.pins.root)

    def enqueue(self, nid, cid, version, profile):
        self.check()
        return self._enqueue(nid, cid, version, profile,
                             project_incarnation=self.binding['project_incarnation'])

    @contextmanager
    def enter(self):
        from ..creative.project_store import CreativeProjectStore
        from ..runtime_events import runtime_events
        from ..repositories.generation_repository import GenerationProjectIdentityError
        root = self.pins.validate()
        owner = CreativeProjectStore(SimpleNamespace(backend='file', root=root))
        failure = None
        # This is not a multi-file rollback. Flush notifications for committed
        # partial effects and the uncertain receipt even when review raises,
        # but only after all project/review/condition locks have unwound.
        with runtime_events.transaction():
            try:
                with owner.existing_owner_only(), owner.owner_lease(self.job.novel_id) as incarnation:
                    if incarnation != self.binding['project_incarnation']:
                        raise GenerationProjectIdentityError('GENERATION_REVIEW_PROJECT_OWNER_CHANGED')
                    # Validate the actual original memory ports before ACCEPTING, not
                    # after a chapter has already been committed.
                    memory = self.pins.services[3]
                    from ..lore.memory_project_binding import create_binding
                    memory._bound_check(create_binding(self.job.novel_id, self.job.chapter_id, 1, incarnation))
                    self.active, self.thread = True, get_ident()
                    try:
                        self.check()
                        yield self
                    finally:
                        self.active, self.thread = False, None
            except BaseException as exc:
                failure = (exc, exc.__traceback__)
        if failure is not None:
            raise failure[0].with_traceback(failure[1])



def require_review(context, manager, job):
    if type(context) is not _FileReview or context.manager is not manager or context.job is not job:
        from fastapi import HTTPException
        raise HTTPException(409, {'code': 'GENERATION_ORDINARY_MUTATION_NOT_INTEGRATED'})
    context.check()
    return context
