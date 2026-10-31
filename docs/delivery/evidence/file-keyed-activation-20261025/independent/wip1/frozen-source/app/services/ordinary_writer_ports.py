"""Transient expected original File writer ports, never execution authority.

The scoped value forwards a private expectation through nested original source
getters. It cannot admit or start a job and is never persisted.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from types import MappingProxyType

_current = ContextVar('ordinary_file_writer_ports', default=None)
_reading_source = ContextVar('ordinary_file_writer_source_check', default=False)


def current_writer_ports():
    return _current.get()


@contextmanager
def suspend_writer_ports():
    token = _current.set(None)
    try:
        yield
    finally:
        _current.reset(token)


class FileWriterPins:
    def __init__(self, manager):
        from .context_service import ContextService
        from .chapter_service import ChapterService
        from .generation_service import GenerationService
        from .lore_service import LoreService
        from ..repositories.file.chapter import FileChapterRepository
        from ..repositories.file.novel import FileNovelRepository
        from ..repositories.file.lore import FileLoreRepository
        from ..repositories.generation_repository import GenerationRepository
        from ..repositories.file.generation import FileGenerationRepository
        self.manager = manager
        self.supported = False
        self.persistence, self.contexts, self.chapters = manager.persistence, manager.contexts, manager.chapters
        if (type(self.persistence) is not GenerationService or type(self.contexts) is not ContextService
                or type(self.chapters) is not ChapterService):
            return
        self.generation_repository = self.persistence.repository
        if type(self.generation_repository) not in (GenerationRepository, FileGenerationRepository):
            return
        self.chapter_repository = self.chapters.repository
        self.novels = self.contexts.novels
        self.context_chapters = self.contexts.chapters
        self.lore = self.contexts.lore
        if (type(self.chapter_repository) is not FileChapterRepository
                or type(self.novels) is not FileNovelRepository or type(self.lore) is not LoreService):
            return
        self.lore_repository = self.lore.repository
        if type(self.lore_repository) is not FileLoreRepository:
            return
        self.repositories = (self.chapter_repository, self.novels, self.lore_repository)
        self.backends = tuple(repo.backend for repo in self.repositories)
        root = manager._ordinary_repository_root
        self.root = root.parent.parent if root is not None else None
        self.ports = (self.persistence, self.generation_repository, self.contexts, self.chapters,
                      *self.repositories, self.lore, *self.backends)
        self.supported = True

    def validate(self, target=None):
        if not self.supported:
            raise ValueError("GENERATION_WRITER_FILE_PORT_MISMATCH")
        from .generation_service import GenerationService
        from ..repositories.generation_repository import GenerationRepository
        from ..repositories.file.generation import FileGenerationRepository
        from .context_service import ContextService
        from .chapter_service import ChapterService
        from .lore_service import LoreService
        from ..repositories.file.chapter import FileChapterRepository
        from ..repositories.file.novel import FileNovelRepository
        from ..repositories.file.lore import FileLoreRepository
        from ..repository import FileRepository
        if (type(self.persistence) is not GenerationService
                or type(self.generation_repository) not in (GenerationRepository, FileGenerationRepository)
                or self.manager.persistence is not self.persistence
                or self.persistence.repository is not self.generation_repository
                or self.root is None
                or Path(self.generation_repository.root).resolve() != self.root / "runtime" / "jobs"
                or type(self.contexts) is not ContextService or type(self.chapters) is not ChapterService
                or type(self.lore) is not LoreService
                or tuple(type(repo) for repo in self.repositories) != (FileChapterRepository, FileNovelRepository, FileLoreRepository)
                or self.manager.contexts is not self.contexts or self.manager.chapters is not self.chapters
                or self.chapters.repository is not self.chapter_repository
                or self.contexts.chapters is not self.chapter_repository
                or self.contexts.novels is not self.novels or self.contexts.lore is not self.lore
                or self.lore.repository is not self.lore_repository
                or self.root is None or self.contexts.enable_narrative_context
                or (target is not None and not any(target is port for port in self.ports))):
            raise ValueError('GENERATION_WRITER_FILE_PORT_MISMATCH')
        for repository, backend in zip(self.repositories, self.backends):
            if (repository.backend is not backend or type(backend) is not FileRepository
                    or Path(backend.data).resolve() != self.root
                    or Path(backend.novels).resolve() != self.root / 'novels'):
                raise ValueError('GENERATION_WRITER_FILE_PORT_MISMATCH')
        return self.root

    def prepare_source(self, project_id, chapter_id, incarnation):
        self.validate()
        return _FileWriterPorts(self, MappingProxyType({'project_id': project_id,
            'chapter_id': chapter_id, 'project_incarnation': incarnation}))

    def prepare(self, binding):
        from copy import deepcopy
        self.validate()
        if binding.get('schema_version') != 2:
            raise ValueError('GENERATION_WRITER_BINDING_REQUIRED')
        return _FileWriterPorts(self, MappingProxyType(deepcopy(binding)))


@dataclass(frozen=True)
class _FileWriterPorts:
    pins: FileWriterPins
    binding: object

    @property
    def root(self):
        return self.pins.root

    def check(self, target=None):
        self.pins.validate(target)

    def source(self):
        from ..repositories.chapter_repository import ChapterRepository
        from ..author_request import chapter_digest
        token = _reading_source.set(True)
        try:
            chapter = ChapterRepository.get(self.pins.chapter_repository, self.binding['chapter_id'], _file_writer=self)
            if (chapter.get('id') != self.binding['chapter_id']
                    or chapter.get('novel_id') != self.binding['project_id'] or chapter.get('is_archived')
                    or ('base_chapter_version' in self.binding and
                        (chapter.get('version') != self.binding['base_chapter_version']
                         or chapter_digest(chapter) != self.binding['base_chapter_digest']))):
                raise ValueError('GENERATION_WRITER_SOURCE_CHANGED')
            return chapter
        finally:
            _reading_source.reset(token)

    @contextmanager
    def guard(self, target=None, project_id=None):
        from ..file_project_lifecycle import project_operation
        self.check(target)
        if project_id is not None and project_id != self.binding['project_id']:
            raise ValueError('GENERATION_WRITER_PROJECT_CHANGED')
        with project_operation(self.root, self.binding['project_id'], expected_root=self.root,
                               expected_incarnation=self.binding['project_incarnation']):
            self.check(target)
            token = _current.set(self)
            try:
                if not _reading_source.get():
                    self.source()
                yield
                self.check(target)
                if not _reading_source.get():
                    self.source()
            finally:
                _current.reset(token)


def require_writer_ports(value, target=None):
    if type(value) is not _FileWriterPorts:
        raise ValueError('GENERATION_WRITER_FILE_PORTS_REQUIRED')
    value.check(target)
    return value


def writer_file_port(method):
    @wraps(method)
    def call(owner, *args, **kwargs):
        expected = kwargs.pop('_file_writer', None) or current_writer_ports()
        if expected is None:
            return method(owner, *args, **kwargs)
        expected = require_writer_ports(expected, owner)
        with expected.guard(owner):
            return method(owner, *args, **kwargs)
    return call
