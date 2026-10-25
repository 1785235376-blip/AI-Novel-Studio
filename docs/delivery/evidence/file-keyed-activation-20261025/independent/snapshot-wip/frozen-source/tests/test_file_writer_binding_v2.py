"""Strict additive private writer source schema, without v1 migration."""
from copy import deepcopy
import pytest
from test_ordinary_project_binding import owner
from app.repositories.generation_repository import GenerationProjectIdentityError
from app.services.generation_project_binding import FIELD


def v2(item):
    item = deepcopy(item)
    item.update(base_chapter_version=1, base_chapter_digest='a'*64)
    item[FIELD].update(schema_version=2, base_chapter_version=1, base_chapter_digest='a'*64)
    return item


def test_v2_cold_repository_retains_private_source(owner):
    item = v2(owner.item)
    owner.repository.save(item)
    assert owner.repository.get(item['id']) == item


@pytest.mark.parametrize('change', [
    lambda row: row.__setitem__('base_chapter_version', True),
    lambda row: row.__setitem__('base_chapter_version', 1.0),
    lambda row: row.pop('base_chapter_digest'),
    lambda row: row.__setitem__('base_chapter_digest', 'b'*64),
    lambda row: row[FIELD].__setitem__('base_chapter_version', True),
    lambda row: row[FIELD].__setitem__('base_chapter_digest', 'A'*64),
    lambda row: row[FIELD].__setitem__('schema_version', 3),
    lambda row: row[FIELD].__setitem__('unknown', None),
])
def test_v2_strict_source_shape(owner, change):
    item = v2(owner.item)
    change(item)
    with pytest.raises(GenerationProjectIdentityError): owner.repository.save(item)
    assert not owner.repository._job_path(item['id']).exists()


@pytest.mark.parametrize('source,target', [(1,2), (2,1)])
def test_no_binding_version_upgrade_or_downgrade(owner, source, target):
    original = owner.item if source == 1 else v2(owner.item)
    changed = owner.item if target == 1 else v2(owner.item)
    owner.repository.save(original)
    with pytest.raises(GenerationProjectIdentityError): owner.repository.save(changed)
    assert owner.repository.get(original['id']) == original


def test_v2_source_cannot_be_rebased_in_both_projections(owner):
    item = v2(owner.item)
    owner.repository.save(item)
    changed = deepcopy(item)
    for projection in (changed, changed[FIELD]):
        projection.update(base_chapter_version=2, base_chapter_digest='b'*64)
    with pytest.raises(GenerationProjectIdentityError): owner.repository.save(changed)
    assert owner.repository.get(item['id']) == item
