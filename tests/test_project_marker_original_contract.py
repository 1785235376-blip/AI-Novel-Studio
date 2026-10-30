"""Characterize both original File marker consumers before parser sharing."""
import json
from types import SimpleNamespace
from uuid import uuid1, uuid4

import pytest

from app.creative.project_store import CreativeProjectStore
from app.creative.director_binding import _creative_director_owner_lease
from app.experimental.store import ExperimentalStore
from app.file_project_lifecycle import project_operation

pytestmark = pytest.mark.file_backend_only


@pytest.fixture
def marker_owner(tmp_path):
    project = tmp_path / 'novels' / 'synthetic'
    project.mkdir(parents=True)
    owner = CreativeProjectStore(SimpleNamespace(root=tmp_path, backend='file'))
    identity = owner.incarnation('synthetic')  # original explicit initialization
    return tmp_path, owner, project / 'creative_project_v2.json', identity


@pytest.mark.parametrize('case', ['extra', 'missing', 'bool-version', 'float-version',
    'new-version', 'nonstring', 'uppercase', 'non-v4', 'malformed'])
def test_corrupt_or_future_marker_never_adopted(marker_owner, case):
    root, owner, path, identity = marker_owner
    valid = {'schema_version': 1, 'project_incarnation': identity.removeprefix('file:')}
    mutations = {'extra': lambda v: v.update(extra='not-authorized'),
        'missing': lambda v: v.pop('project_incarnation'),
        'bool-version': lambda v: v.update(schema_version=True),
        'float-version': lambda v: v.update(schema_version=1.0),
        'new-version': lambda v: v.update(schema_version=2),
        'nonstring': lambda v: v.update(project_incarnation=12),
        'uppercase': lambda v: v.update(project_incarnation=str(uuid4()).upper()),
        'non-v4': lambda v: v.update(project_incarnation=str(uuid1())),
        'malformed': lambda v: v.update(project_incarnation='not-a-uuid')}
    mutations[case](valid)
    path.write_text(json.dumps(valid), encoding='utf-8')
    before = path.read_bytes()
    with owner.existing_owner_only():
        with pytest.raises(ValueError, match='^CREATIVE_PROJECT_IDENTITY_INVALID$'):
            owner.incarnation('synthetic')
    with pytest.raises(ValueError) as error:
        with project_operation(root, 'synthetic', expected_incarnation=identity):
            pytest.fail('invalid original marker accepted')
    expected = 'badly formed hexadecimal UUID string' if case == 'malformed' else 'GENERATION_REVIEW_PROJECT_OWNER_CHANGED'
    assert str(error.value) == expected
    assert path.read_bytes() == before


def test_same_id_recreation_cannot_adopt_old_marker_identity(marker_owner):
    root, owner, path, identity = marker_owner
    replacement = str(uuid4())
    path.write_text(json.dumps({'schema_version': 1, 'project_incarnation': replacement}), encoding='utf-8')
    with owner.existing_owner_only():
        assert owner.incarnation('synthetic') == 'file:' + replacement
    with pytest.raises(ValueError, match='^GENERATION_REVIEW_PROJECT_OWNER_CHANGED$'):
        with project_operation(root, 'synthetic', expected_incarnation=identity):
            pytest.fail('stale incarnation accepted')


def test_existing_only_does_not_recreate_missing_marker(marker_owner):
    root, owner, path, identity = marker_owner
    path.unlink()
    with owner.existing_owner_only():
        with pytest.raises(FileNotFoundError):
            owner.incarnation('synthetic')
    assert not path.exists()


@pytest.mark.parametrize('damage', ['none', 'extra', 'bool-version', 'bad-uuid', 'recreated'])
def test_director_original_owner_marker_remains_strict(marker_owner, damage):
    root, _, path, identity = marker_owner
    scope = {'mode': 'local', 'novel_id': 'synthetic'}
    raw = ExperimentalStore(root)
    documents = SimpleNamespace(store=CreativeProjectStore(raw))
    with raw.transaction('synthetic', scope) as state:
        state['collections']['synthetic'] = {'item': {'value': 'original'}}
    binding = {'contract': 'CREATIVE_DIRECTOR_SOURCE_V1', 'source_kind': 'STORYBOARD',
        'project_id': 'synthetic', 'project_incarnation': identity, 'actor_id': 'actor',
        'scope': scope, 'source_document_id': 'doc', 'source_version': 1,
        'source_digest': 'a' * 64, 'reviewed_preview_digest': 'b' * 64}
    value = json.loads(path.read_text(encoding='utf-8'))
    if damage == 'extra': value['extra'] = True
    elif damage == 'bool-version': value['schema_version'] = True
    elif damage == 'bad-uuid': value['project_incarnation'] = 'not-uuid'
    elif damage == 'recreated': value['project_incarnation'] = str(uuid4())
    path.write_text(json.dumps(value), encoding='utf-8')
    before = path.read_bytes()
    with raw.transaction('synthetic', scope):
        if damage == 'none':
            with _creative_director_owner_lease(documents, binding) as observed:
                assert observed == identity
        else:
            with pytest.raises(ValueError, match='^CREATIVE_DIRECTOR_SOURCE_OWNER_CHANGED$'):
                with _creative_director_owner_lease(documents, binding):
                    pytest.fail('bad marker accepted by original Director owner')
    assert path.read_bytes() == before
