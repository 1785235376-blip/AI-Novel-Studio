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
