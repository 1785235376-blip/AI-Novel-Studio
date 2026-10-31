"""Actual File source/context/snapshot fences, independent of execution grants."""
from copy import deepcopy
import json

import pytest

from app.author_request import chapter_digest
from app.services.ordinary_writer_ports import FileWriterPins
from test_passive_generation_manager_binding import source, _record, _replace_owner


def ports_for(source):
    pins = FileWriterPins(source.manager)
    row = _record(source)
    binding = dict(row['ordinary_project_binding'], schema_version=2,
                   base_chapter_version=source.chapter['version'],
                   base_chapter_digest=chapter_digest(source.chapter))
    # Lower-port fixture only: inert durable state, never an execution grant.
    row.update(status='GENERATING', ordinary_project_binding=binding,
               base_chapter_digest=binding['base_chapter_digest'])
    source.persistence.save(row)
    return pins.prepare(binding)


def test_original_context_and_deferred_snapshot(source):
    ports = ports_for(source)
    context = source.contexts.for_chapter(source.chapter['id'], 'continue', False, 'continue', _file_writer=ports)
    result = source.contexts.save_snapshot(source.chapter['id'], source.chapter['version'], context,
                                          'writer:v1', 'mock-writer', _file_writer=ports)
    assert result['chapter_version_id'] == source.chapter['id'] + ':v1'
    paths = list((source.root/'novels'/source.chapter['novel_id']/'lore/context_snapshots').glob('*.json'))
    assert len(paths) == 1
    assert json.loads(paths[0].read_text())['context'] == context


@pytest.mark.parametrize('seam', ['source', 'novel', 'lore', 'snapshot'])
def test_same_thread_owner_replacement_refuses_at_original_ports(source, monkeypatch, seam):
    ports = ports_for(source)
    if seam == 'source': target, name = source.bundle.chapters.backend, 'chapter'
    elif seam == 'novel': target, name = source.bundle.novels, 'get_context_sources'
    elif seam == 'lore': target, name = source.bundle.lore, '_lore_root'
    else:
        from app.services.context_snapshot_service import ContextSnapshotService
        target, name = ContextSnapshotService, 'create'
    original = getattr(target, name)
    def replace(*args, **kwargs):
        monkeypatch.setattr(target, name, original)
        _replace_owner(source)
        return original(*args, **kwargs)
    monkeypatch.setattr(target, name, replace)
    with pytest.raises((ValueError, FileNotFoundError)):
        if seam == 'snapshot':
            source.contexts.save_snapshot(source.chapter['id'], 1, {}, 'writer:v1', 'mock', _file_writer=ports)
        else:
            source.contexts.for_chapter(source.chapter['id'], _file_writer=ports)
    assert not (source.root/'novels'/source.chapter['novel_id']/'lore/context_snapshots').exists()


@pytest.mark.parametrize('port', ['novels', 'chapters', 'lore'])
def test_same_root_repository_rotation_refused(source, monkeypatch, port):
    ports = ports_for(source)
    if port == 'lore':
        original = source.contexts.lore.repository
        monkeypatch.setattr(source.contexts.lore, 'repository', type(original)(original.backend))
    else:
        original = getattr(source.contexts, port)
        monkeypatch.setattr(source.contexts, port, type(original)(original.backend))
    with pytest.raises(ValueError, match='FILE_PORT_MISMATCH'):
        source.contexts.for_chapter(source.chapter['id'], _file_writer=ports)


def test_same_version_changed_content_refused(source):
    ports = ports_for(source)
    path = source.root/'novels'/source.chapter['novel_id']/'documents/chapter-0001.json'
    package = json.loads(path.read_text())
    from app.document import markdown_to_document
    package['document'] = markdown_to_document('DIFFERENT SOURCE')
    path.write_text(json.dumps(package))
    with pytest.raises(ValueError, match='SOURCE_CHANGED'):
        source.contexts.for_chapter(source.chapter['id'], _file_writer=ports)


def test_prebinding_source_capture_guards_lazy_package(source):
    pins = FileWriterPins(source.manager)
    path = source.root/'novels'/source.chapter['novel_id']/'documents/chapter-0001.json'
    path.unlink()
    ports = pins.prepare_source(source.chapter['novel_id'], source.chapter['id'], source.incarnation)
    with ports.guard():
        chapter = source.chapters.get(source.chapter['id'])
    assert chapter['version'] == 1 and path.exists()


@pytest.mark.parametrize('change', ['version', 'archive'])
def test_source_state_change_refuses_context_and_snapshot(source, change):
    ports = ports_for(source)
    if change == 'version':
        source.chapters.save(source.chapter['id'], {'version': 1, 'content': 'NEW'})
    else:
        source.chapters.archive(source.chapter['id'], 1)
    with pytest.raises(ValueError, match='SOURCE_CHANGED'):
        source.contexts.for_chapter(source.chapter['id'], _file_writer=ports)
    with pytest.raises(ValueError, match='SOURCE_CHANGED'):
        source.contexts.save_snapshot(source.chapter['id'], 1, {}, 'writer:v1', 'mock', _file_writer=ports)


def test_falsey_forged_expectation_does_not_downgrade(source):
    with pytest.raises(ValueError, match='PORTS_REQUIRED'):
        source.contexts.for_chapter(source.chapter['id'], _file_writer={})


def test_late_lore_root_rotation_cannot_write_other_project(source, monkeypatch, tmp_path):
    ports = ports_for(source)
    from app.repositories.factory import create_repository_bundle
    other = create_repository_bundle(source.config, tmp_path/'other')
    from app.services import NovelService, ChapterService
    novels = NovelService(other.novels, other.chapters)
    novels.create({'id': source.chapter['novel_id'], 'title': 'Other root'})
    ChapterService(other.chapters).create(source.chapter['novel_id'], {'title': 'One', 'content': 'OTHER'})
    original = source.bundle.lore._lore_root
    def rotate(*args, **kwargs):
        source.bundle.lore.backend = other.lore.backend
        return original(*args, **kwargs)
    monkeypatch.setattr(source.bundle.lore, '_lore_root', rotate)
    with pytest.raises(ValueError, match='PORT_MISMATCH'):
        source.contexts.for_chapter(source.chapter['id'], _file_writer=ports)
    assert not (tmp_path/'other/novels'/source.chapter['novel_id']/'lore').exists()


def test_context_owner_lease_blocks_cross_thread_replacement(source, monkeypatch):
    from threading import Event, Thread
    ports = ports_for(source)
    entered, release, attempting, deleted = Event(), Event(), Event(), Event()
    original = source.bundle.lore._lore_root
    def pause(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)
    monkeypatch.setattr(source.bundle.lore, '_lore_root', pause)
    errors, result = [], []
    def build():
        try: result.append(source.contexts.for_chapter(source.chapter['id'], _file_writer=ports))
        except BaseException as exc: errors.append(exc)
    def replace():
        attempting.set()
        try: _replace_owner(source)
        except BaseException as exc: errors.append(exc)
        finally: deleted.set()
    worker = Thread(target=build); worker.start()
    assert entered.wait(5)
    replacement = Thread(target=replace); replacement.start()
    assert attempting.wait(5)
    assert not deleted.wait(.1)
    release.set(); worker.join(5); replacement.join(5)
    assert not errors and result and deleted.is_set()
    with pytest.raises(ValueError):
        source.contexts.save_snapshot(source.chapter['id'], 1, result[0], 'writer:v1', 'mock', _file_writer=ports)


@pytest.mark.parametrize('filename', ['documents/chapter-0001.json', 'chapter_identity.json'])
def test_bound_source_missing_metadata_is_not_lazily_rebuilt(source, filename):
    ports = ports_for(source)
    path = source.root/'novels'/source.chapter['novel_id']/filename
    path.unlink()
    with pytest.raises(ValueError, match='METADATA_MISSING'):
        source.contexts.for_chapter(source.chapter['id'], _file_writer=ports)
    assert not path.exists()


def test_receipt_expectation_survives_missing_source_but_cannot_use_context(source):
    ports = ports_for(source).for_receipt()
    path = source.root/'novels'/source.chapter['novel_id']/'documents/chapter-0001.json'
    path.unlink()
    with ports.guard(ports.pins.generation_repository):
        pass
    with pytest.raises(ValueError, match='RECEIPT_PORT_REQUIRED'):
        source.contexts.for_chapter(source.chapter['id'], _file_writer=ports)
    with pytest.raises(ValueError):
        ports.source()
    assert not path.exists()


@pytest.mark.parametrize('seam', ['source_paths', 'lore_root'])
def test_after_return_wrapper_cannot_write_replacement(source, monkeypatch, seam):
    ports = ports_for(source)
    target, name = ((source.bundle.chapters, '_paths') if seam == 'source_paths'
                    else (source.bundle.lore, '_novel_root'))
    original = getattr(target, name)
    def replace_after(*args, **kwargs):
        result = original(*args, **kwargs)
        monkeypatch.setattr(target, name, original)
        _replace_owner(source)
        return result
    monkeypatch.setattr(target, name, replace_after)
    with pytest.raises((ValueError, FileNotFoundError)):
        source.contexts.for_chapter(source.chapter['id'], _file_writer=ports)
    replacement_root = source.root/'novels'/source.chapter['novel_id']
    assert not (replacement_root/'documents/chapter-0001.json').exists()
    assert not (replacement_root/'lore').exists()


def test_foreign_same_project_chapter_not_materialized(source):
    second = source.chapters.create(source.chapter['novel_id'], {'title': 'Second', 'content': 'Second source'})
    ports = ports_for(source)
    path = source.root/'novels'/source.chapter['novel_id']/'documents/chapter-0002.json'
    assert not path.exists()
    with pytest.raises(ValueError, match='SOURCE_CHANGED'):
        source.contexts.for_chapter(second['id'], _file_writer=ports)
    assert not path.exists()


def test_snapshot_refuses_durable_failed_state(source):
    ports = ports_for(source)
    row = source.persistence.get(ports.binding['job_id'])
    row['status'] = 'FAILED'
    source.persistence.save(row)
    with pytest.raises(ValueError, match='SNAPSHOT_STATE_CHANGED'):
        source.contexts.save_snapshot(source.chapter['id'], 1, {}, 'writer:v1', 'mock', _file_writer=ports)
    assert not (source.root/'novels'/source.chapter['novel_id']/'lore/context_snapshots').exists()
