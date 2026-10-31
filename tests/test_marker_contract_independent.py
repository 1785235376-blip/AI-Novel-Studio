"""Independent legacy File marker compatibility and invalid-binding controls."""
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.creative.director_binding import _creative_director_owner_lease
from app.creative.project_store import CreativeProjectStore
from app.experimental.store import ExperimentalStore
from app.file_project_lifecycle import project_operation
from app.repositories.generation_repository import GenerationProjectIdentityError, GenerationRepository
from app.services.generation_project_binding import FIELD

pytestmark = pytest.mark.file_backend_only
VALID = '11111111-1111-4111-8111-111111111111'
NID = 'synthetic'
SCOPE = {'mode': 'local', 'novel_id': NID}


@pytest.fixture
def owner(tmp_path):
    project = tmp_path / 'novels' / NID
    project.mkdir(parents=True)
    marker = project / 'creative_project_v2.json'
    marker.write_text(json.dumps({'schema_version': 1, 'project_incarnation': VALID}), encoding='utf-8')
    raw = ExperimentalStore(tmp_path)
    creative = CreativeProjectStore(raw)
    with raw.transaction(NID, SCOPE) as doc:
        doc['collections']['synthetic'] = {'item': {'value': 'original'}}
    return SimpleNamespace(root=tmp_path, marker=marker, raw=raw, creative=creative,
                           repository=GenerationRepository(tmp_path))


@pytest.mark.parametrize('document', [
    {'schema_version': 1, 'project_incarnation': VALID},
    {'schema_version': 0, 'project_incarnation': VALID},
    {'schema_version': True, 'project_incarnation': VALID},
    {'schema_version': 1.0, 'project_incarnation': VALID},
    {'schema_version': 2, 'project_incarnation': VALID},
    {'schema_version': 1, 'project_incarnation': None},
    {'schema_version': 1, 'project_incarnation': 'bad-uuid'},
    {'schema_version': 1, 'project_incarnation': '11111111-1111-1111-8111-111111111111'},
    {'schema_version': 1, 'project_incarnation': VALID, 'unexpected': 'synthetic'},
    None, [],
])
@pytest.mark.parametrize('ordinary', [False, True])
def test_original_generation_owner_rejects_none_binding_for_all_marker_shapes(owner, document, ordinary):
    owner.marker.write_text(json.dumps(document), encoding='utf-8')
    before = owner.marker.read_bytes()
    item = {'novel_id': NID}
    if ordinary:
        item[FIELD] = {}
    with pytest.raises(GenerationProjectIdentityError):
        with owner.repository._graph_owner(item, {'project_incarnation': None}):
            pytest.fail('None is not an owner binding')
    assert owner.marker.read_bytes() == before


def test_no_expected_incarnation_keeps_legacy_unchecked_operation_semantics(owner):
    owner.marker.write_text('{invalid JSON', encoding='utf-8')
    before = owner.marker.read_bytes()
    # Explicitly characterize the old opt-out, not an owner-validated lease.
    with project_operation(owner.root, NID, expected_incarnation=None):
        pass
    assert owner.marker.read_bytes() == before


def test_director_public_binding_schema_rejects_none_before_owner_comparison(owner):
    binding = {'contract': 'CREATIVE_DIRECTOR_SOURCE_V1', 'source_kind': 'STORYBOARD',
               'project_id': NID, 'project_incarnation': None, 'actor_id': 'actor',
               'scope': SCOPE, 'source_document_id': 'doc', 'source_version': 1,
               'source_digest': 'a' * 64, 'reviewed_preview_digest': 'b' * 64}
    before = owner.marker.read_bytes()
    with owner.raw.transaction(NID, SCOPE):
        with pytest.raises(ValidationError):
            with _creative_director_owner_lease(SimpleNamespace(store=owner.creative), binding):
                pytest.fail('invalid binding must not enter owner')
    assert owner.marker.read_bytes() == before
