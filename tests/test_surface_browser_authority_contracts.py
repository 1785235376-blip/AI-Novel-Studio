"""Real source/compare authority used by the two-browser manuscript journey."""
from uuid import uuid4

from app.authorization import AuthorizationScope, DomainRole, DomainRoleAssignment, ModalityDomain, ScopeKind
from test_r3_mounted_contracts import mounted, prefix, scoped, checked
from test_surface_branch_manuscript_mounted import branch_env, create


def test_mainline_integrity_is_verified_through_authorized_source_and_compare(branch_env):
    e = branch_env
    assert e.branch_client.get(e.branch_base + '/sources', headers=e.headers).status_code == 403
    role = DomainRoleAssignment('project-proof-' + uuid4().hex, e.lead, DomainRole.DOMAIN_LEAD,
        ModalityDomain.NOVEL, AuthorizationScope(ScopeKind.PROJECT, e.workspace, e.nid), e.lead)
    e.authorization.assign_role(role)
    created = create(e)
    sources = checked(e.branch_client.get(e.branch_base + '/sources', headers=e.headers))['items']
    assert len(sources) == 1 and sources[0]['id'] == e.chapter['id']
    preview = checked(e.branch_client.post(e.branch_base + '/forks/preview', headers=e.headers,
        json={'chapter_ids': [sources[0]['id']]}))
    applied = checked(e.branch_client.post(e.branch_base + '/forks/' + preview['id'] + '/apply',
        headers=e.headers, json={'expected_version': preview['version'], 'preview_digest': preview['preview_digest'], 'confirmed': True}))
    fork_id = applied['id_map'][e.chapter['id']]
    comparison = checked(e.branch_client.post(e.branch_base + '/compare', headers=e.headers,
        json={'chapter_id': fork_id, 'target_chapter_id': e.chapter['id']}))
    assert comparison['target']['branch_id'] is None
    assert comparison['target']['version'] == e.chapter['version']
    assert comparison['checkpoint'] == e.chapter['document']
    assert comparison['conflicts'] == []
    assert e.owner.read(e.ctx, created['id'])['content'] != e.chapter['content']
    assert e.chapters.get(e.chapter['id']) == e.chapter
    e.authorization.revoke_role(role.id, e.lead)
    assert e.branch_client.post(e.branch_base + '/compare', headers=e.headers,
        json={'chapter_id': fork_id, 'target_chapter_id': e.chapter['id']}).status_code == 403
