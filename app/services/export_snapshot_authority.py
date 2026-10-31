"""Evidence required to expose retained exports under branch-only grants."""
from ..repositories.branch_manuscript import OWNER, document_digest, is_branch_chapter_id


def branch_snapshot_owned(snapshot, scope):
    if not isinstance(snapshot, dict): return False
    if snapshot.get('manuscript_authority') != OWNER or snapshot.get('manuscript_scope') != scope:
        return False
    if snapshot.get('novel_id') != scope['novel_id'] or snapshot.get('branch_id') != scope['branch_id']:
        return False
    source = snapshot.get('source')
    if not isinstance(source, dict) or not isinstance(source.get('chapters'), list): return False
    # Project datasets/outline have no branch manuscript owner, even if a
    # historical record happens to carry a branch label.
    if not isinstance(source.get('datasets'), dict) or any(source['datasets'].values()): return False
    for chapter in source['chapters']:
        if (not isinstance(chapter, dict) or chapter.get('authority') != OWNER or chapter.get('scope') != scope
                or chapter.get('novel_id') != scope['novel_id'] or chapter.get('branch_id') != scope['branch_id']
                or not is_branch_chapter_id(scope['novel_id'], chapter.get('id'))
                or chapter.get('is_archived') or chapter.get('deleted')
                or type(chapter.get('version')) is not int or chapter['version'] < 1
                or not isinstance(chapter.get('document'), dict)
                or chapter.get('document_digest') != document_digest(chapter['document'])):
            return False
    screenplays = source.get('screenplays')
    if not isinstance(screenplays, list) or any(not isinstance(row, dict) or row.get('branch_id') != scope['branch_id'] for row in screenplays):
        return False
    return True
