"""Original-owner persistence evidence for structured personal-brief editing."""
import copy
import json
import pytest
from test_r4_reader_sessions import env
from app.experimental.template_library import TemplateLibraryService, builtin_packages
from app.experimental.store import ExperimentalStore
from app.experimental.planning import digest
from app.services.v1_capability_service import CapabilityVersionConflict


def test_personal_brief_edit_reopen_history_and_revert(env, tmp_path):
    e = env
    service = TemplateLibraryService(e.store, e.novels, e.chapters)
    package = copy.deepcopy(next(p for p in builtin_packages() if p['manifest']['type'] == 'review'))
    package['manifest'].update(id='personal-copy-editing', author='Synthetic author', license='Personal declaration', provenance='PERSONAL_TEXT_PROJECTION:synthetic-sha256')
    raw = json.dumps(package)
    preview = service.preview(e.ctx, {'package': raw})
    service.install(e.ctx, {'package': raw, 'expected_version': preview['expected_version'], 'preview_digest': preview['preview_digest']})
    row = service.copy(e.ctx, {'package_id': package['manifest']['id'], 'package_digest': digest(package), 'request_id': 'copy-editing'})
    content = copy.deepcopy(row['content']); content['sections'][0]['text'] = '独立副本中的中文修改'
    saved = service.edit(e.ctx, row['id'], {'expected_version': row['version'], 'content': content})
    with pytest.raises(CapabilityVersionConflict):
        service.edit(e.ctx, row['id'], {'expected_version': row['version'], 'content': row['content']})
    # A new File store/service reads persisted bytes, not the previous service result.
    reopened_store = ExperimentalStore(tmp_path, e.store.backend, e.store.database_url)
    reopened = TemplateLibraryService(reopened_store, e.novels, e.chapters)
    reopened_row = reopened.instances(e.ctx)['items'][0]
    assert reopened_row['content'] == content
    assert reopened_row['manifest'] == row['manifest']
    assert reopened_row['version'] == saved['version']
    assert reopened.history(e.ctx, row['id'])['items'][0]['content'] == row['content']
    restored = reopened.revert(e.ctx, row['id'], {'expected_version': saved['version'], 'restore_version': row['version']})
    assert restored['content'] == row['content']
    assert restored['version'] > saved['version']
    assert len(reopened.history(e.ctx, row['id'])['items']) == 2
    assert restored['linked_target'] is None
