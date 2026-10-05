"""Pure projections of existing chapter authorities, never legacy materialization.

The File repository's ordinary get/list lazily persists document packages. For
reading/preflight we use the same project guard and existing metadata, deriving
the identical markdown document in memory when a legacy package is absent.
No new source store, IDs, writes, migrations or branch fallback are introduced.
"""
from ..document import markdown_to_document, document_to_markdown
from ..file_project_lifecycle import project_operation
from ..repository import read_json
from ..repositories.file.chapter import FileChapterRepository


def authorized_chapter_rows(ctx, sources, chapters):
    sources.novels.get(ctx.novel_id)
    repo = getattr(chapters, 'repository', None)
    if ctx.scope.get('mode') == 'local' and sources.chapter_reader is None and isinstance(repo, FileChapterRepository):
        backend = repo.backend
        with project_operation(backend.data, ctx.novel_id):
            rows = []
            for row in backend.list_chapters(ctx.novel_id):
                if row.get('is_archived'): continue
                path = backend.novels / ctx.novel_id / 'documents' / f"chapter-{row['number']:04d}.json"
                package = read_json(path, None)
                if package is None:
                    document, version, updated = markdown_to_document(row['content']), 1, None
                else:
                    if not isinstance(package, dict) or package.get('chapter_id') != row['id'] or type(package.get('version')) is not int or package['version'] < 1 or not isinstance(package.get('document'), dict):
                        raise ValueError('chapter document package invalid; recover through the original editor')
                    document, version, updated = package['document'], package['version'], package.get('updated_at')
                rows.append({**row, 'document': document, 'content': document_to_markdown(document), 'version': version, 'updated_at': updated})
    else:
        # PostgreSQL already has a read-only document projection. Collaborating
        # branches must provide their own authorized reader; never base data.
        rows = sources._source_rows(ctx, 'chapter')
    return [r for r in rows if r.get('novel_id') == ctx.novel_id and not r.get('is_archived')
            and not r.get('hidden') and not r.get('secret') and str(r.get('visibility', '')).upper() not in {'PRIVATE', 'SECRET', 'DENIED'}
            and (ctx.scope['mode'] == 'local' and not r.get('branch_id') or ctx.scope['mode'] == 'collaboration' and r.get('branch_id') == ctx.scope.get('branch_id'))]


def chapter_revision(row):
    """Stable content fence, including rich document and version, not lazy timestamps."""
    from .planning import digest
    from .ux import chapter_text
    return digest({'id': row['id'], 'version': row['version'], 'branch_id': row.get('branch_id'),
                   'document': row.get('document'), 'text': chapter_text(row)})


def authorized_chapter(ctx, sources, chapters, cid, *, include_archived=False):
    """Pure original chapter projection, including explicit tombstone reads.

    An injected branch reader is the only possible branch authority. Never use a
    base repository to fill a missing branch result. IDs are fenced before I/O.
    """
    import re
    if (ctx.scope.get('novel_id') != ctx.novel_id or ctx.scope.get('mode') not in {'local', 'collaboration'}
            or ctx.scope.get('mode') == 'collaboration' and not ctx.scope.get('branch_id')
            or not isinstance(cid, str) or not re.fullmatch(re.escape(ctx.novel_id) + r':[1-9][0-9]{0,6}', cid)):
        raise FileNotFoundError('chapter unavailable')
    sources.novels.get(ctx.novel_id)
    repo = getattr(chapters, 'repository', None)
    if sources.chapter_reader is not None:
        row = next((r for r in sources.chapter_reader(ctx) if r.get('id') == cid), None)
        if row is None: raise FileNotFoundError('chapter unavailable')
    elif ctx.scope.get('mode') == 'local' and not ctx.branch and isinstance(repo, FileChapterRepository):
        with project_operation(repo.backend.data, ctx.novel_id):
            row = repo.backend.chapter(cid)
            package = read_json(repo._paths(cid)[2], None)
            if package is None:
                document, version, updated = markdown_to_document(row['content']), 1, None
            else:
                if not isinstance(package, dict) or package.get('chapter_id') != cid or type(package.get('version')) is not int or package['version'] < 1 or not isinstance(package.get('document'), dict):
                    raise ValueError('chapter document package invalid; recover through the original editor')
                document, version, updated = package['document'], package['version'], package.get('updated_at')
            row = {**row, 'document': document, 'content': document_to_markdown(document), 'version': version, 'updated_at': updated}
    elif ctx.scope.get('mode') == 'local' and not ctx.branch:
        # The original PostgreSQL repository get is already a pure projection.
        row = chapters.get(cid)
    else:
        raise FileNotFoundError('chapter unavailable')
    if (row.get('id') != cid or row.get('novel_id') != ctx.novel_id
            or not include_archived and (row.get('is_archived') or row.get('status') == 'ARCHIVED')
            or row.get('hidden') or row.get('secret') or str(row.get('visibility', '')).upper() in {'PRIVATE', 'SECRET', 'DENIED'}
            or ctx.scope.get('mode') == 'local' and (ctx.branch or row.get('branch_id'))
            or ctx.scope.get('mode') == 'collaboration' and row.get('branch_id') != ctx.scope.get('branch_id')):
        raise FileNotFoundError('chapter unavailable')
    return row
