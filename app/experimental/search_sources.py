"""Read-only source manifests for the optional deterministic workspace search.

File freshness uses inode, size, mtime_ns and ctime_ns under the existing project
lifecycle guard. Atomic repository saves, archive/delete and normal external
edits invalidate it. Nonparticipating writers that defeat *all* filesystem
metadata are unsupported; explicit rebuild rereads every source. PostgreSQL
uses the original chapter version/hash/updated_at columns, never manuscript
JSON in warm manifests. Authorization is intentionally NOT cached here.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from ..document import markdown_to_document, document_to_markdown
from ..file_project_lifecycle import project_operation
from ..repository import read_json
from ..repositories.file.chapter import FileChapterRepository
from ..repositories.postgres.chapter import PostgresChapterRepository
from .planning import digest


@dataclass(frozen=True)
class SearchSource:
    key: str
    stamp: str
    read: Callable[[], dict]


def repository(service):
    return getattr(service.chapters, 'repository', service.chapters)


def project_ids(service):
    """IDs only. Avoid NovelService.list's full-library word-count scan."""
    repo = repository(service)
    if isinstance(repo, FileChapterRepository):
        return sorted(p.name for p in repo.backend.novels.iterdir()
                      if p.is_dir() and (p / 'novel.json').is_file() and not p.name.startswith('.'))
    if isinstance(repo, PostgresChapterRepository):
        from sqlalchemy import select
        from ..repositories.postgres.models import NovelModel
        with repo.database.session() as session:
            return list(session.scalars(select(NovelModel.slug).order_by(NovelModel.slug)))
    return []


def create_search_candidates(scope_repository):
    def candidates(ctx, service):
        if ctx.scope.get('mode') == 'local':
            return [(nid, None) for nid in project_ids(service)]
        # Enumeration is not permission evidence. Route reauthorizes every pair.
        rows = scope_repository.list('branches', workspace_id=ctx.scope.get('workspace_id'))
        return sorted({(str(row['project_id']), str(row['id'])) for row in rows
                       if row.get('project_id') and row.get('id')})
    return candidates


def _stat(path):
    try:
        value = path.stat()
        return [value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns]
    except FileNotFoundError:
        return None


def chapter_manifest(service, ctx, check):
    """Return None for an unknown/branch authority so callers stay fail-closed."""
    repo = repository(service)
    if ctx.scope.get('mode') != 'local' or service.chapter_reader is not None:
        return None
    if isinstance(repo, FileChapterRepository):
        backend = repo.backend
        with project_operation(backend.data, ctx.novel_id):
            root = backend.novels / ctx.novel_id
            state = read_json(root / 'chapter_state.json', {})
            result = []
            for path in sorted((root / 'chapters').glob('chapter-*.md')):
                check()
                number = int(path.stem.split('-')[-1]); cid = f'{ctx.novel_id}:{number}'
                if state.get(cid, False): continue
                package_path = root / 'documents' / f'chapter-{number:04d}.json'
                stamp = digest([_stat(path), _stat(package_path)])
                def read(path=path, package_path=package_path, cid=cid):
                    with project_operation(backend.data, ctx.novel_id):
                        if read_json(root / 'chapter_state.json', {}).get(cid, False):
                            raise FileNotFoundError(cid)
                        package = read_json(package_path, None)
                        if package is None:
                            content = path.read_text(encoding='utf-8')
                            document = markdown_to_document(content); version = 1
                            updated = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
                        else:
                            if (not isinstance(package, dict) or package.get('chapter_id') != cid
                                or type(package.get('version')) is not int or package['version'] < 1
                                or not isinstance(package.get('document'), dict)):
                                raise ValueError('invalid source chapter package')
                            document, version = package['document'], package['version']
                            updated = package.get('updated_at', '')
                        # Match the original File authority's first Markdown line,
                        # including paragraphs after an author removes the heading.
                        markdown = document_to_markdown(document)
                        title = markdown.splitlines()[0].lstrip('# ') if markdown else '章节'
                        return {'id': cid, 'novel_id': ctx.novel_id, 'version': version,
                                'title': title, 'document': document, 'updated_at': updated}
                result.append(SearchSource('chapter:' + cid, stamp, read))
            return result
    if isinstance(repo, PostgresChapterRepository):
        from sqlalchemy import select
        from ..repositories.postgres.models import ChapterModel, NovelModel
        with repo.database.session() as session:
            rows = session.execute(select(ChapterModel.chapter_number, ChapterModel.version,
                ChapterModel.content_hash, ChapterModel.updated_at, ChapterModel.title)
                .join(NovelModel, ChapterModel.novel_id == NovelModel.id)
                .where(NovelModel.slug == ctx.novel_id, ChapterModel.is_archived.is_(False))
                .order_by(ChapterModel.chapter_number)).all()
        result = []
        for number, version, content_hash, updated, title in rows:
            check(); cid = f'{ctx.novel_id}:{number}'
            result.append(SearchSource('chapter:' + cid, digest([version, content_hash, str(updated), title]),
                                       lambda cid=cid: repo.get(cid)))
        return result
    return None


def create_extended_search_readers(legacy, world, graph, authorize, require_flag):
    """Original-world/graph/asset/workflow projections, without a second index owner."""
    from fastapi import HTTPException
    from .. import workflow_api

    def checked(ctx, feature=None, permission='domain.read'):
        require_flag('workspace_tools_v2')
        if feature: require_flag(feature)
        if authorize(ctx.novel_id, ctx.token, ctx.branch, permission) != (ctx.actor, ctx.scope):
            raise HTTPException(403, {'code': 'WORKSPACE_AUTHORITY_CHANGED'})

    def shaped(ctx, row, feature, owner, *, title=None, rid=None):
        if row.get('novel_id', ctx.novel_id) != ctx.novel_id or row.get('scope', ctx.scope) != ctx.scope:
            raise FileNotFoundError('source scope')
        if row.get('branch_id') and row['branch_id'] != ctx.branch: raise FileNotFoundError('source branch')
        return {**row, 'id': rid or row['id'], 'title': title or row.get('title') or row.get('name') or str(row['id']),
                'novel_id': ctx.novel_id, 'branch_id': ctx.branch, 'feature': feature,
                'source_navigation': {'kind': 'feature', 'id': row['id'], 'feature': feature, 'task_authority': owner}}

    def semantic(ctx, kind):
        checked(ctx, 'world_character_engines_v2')
        result = [shaped(ctx, row, 'world_character_engines_v2', 'world_record')
                  for row in world.records(ctx.novel_id, ctx.scope) if row['kind'] == kind]
        checked(ctx, 'world_character_engines_v2')
        return result

    def rules(ctx):
        result = []
        try: result.extend(semantic(ctx, 'ABILITY'))
        except HTTPException as exc:
            if exc.status_code not in {401, 403, 404}: raise
        checked(ctx)
        if ctx.scope.get('mode') == 'local':
            for row in legacy.list_world_rules(nid=ctx.novel_id, status=None)['items']:
                # The original public rule text is its searchable title; evidence,
                # payload, hidden data and arbitrary logs are never indexed.
                payload = row.get('payload') or {}
                title = payload.get('statement') or payload.get('rule') or payload.get('title') or '世界规则'
                result.append(shaped(ctx, row, 'story', 'world_rule', title=title, rid='legacy:' + row['id']))
        checked(ctx)
        return result

    def story_graph(ctx):
        # Match the existing author-only Graph /records route, not a weaker read.
        checked(ctx, 'temporal_story_graph_v2', 'domain.write')
        result = []
        for row in graph.records(ctx.novel_id, ctx.scope):
            if row['kind'] == 'KNOWLEDGE_EVENT':
                try: require_flag('character_mind_v2')
                except HTTPException as exc:
                    if exc.status_code == 404: continue
                    raise
            result.append(shaped(ctx, row, 'temporal_story_graph_v2', 'graph_record'))
        checked(ctx, 'temporal_story_graph_v2', 'domain.write')
        return result

    def assets(ctx):
        checked(ctx)
        rows = legacy.list_assets(nid=ctx.novel_id, kind=None, character_id=None, scene_id=None,
                                 x_session_token=ctx.token, x_branch_id=ctx.branch)
        if isinstance(rows, dict): rows = rows.get('items', [])
        result = [shaped(ctx, row, 'assets', 'asset_record', title=row.get('title') or row.get('filename') or row.get('kind')) for row in rows]
        checked(ctx)
        return result

    def workflows(ctx):
        checked(ctx)
        rows = workflow_api.workflows(novel_id=ctx.novel_id, x_session_token=ctx.token)['items']
        result = [shaped(ctx, row, 'workflow', 'workflow_definition') for row in rows if row.get('branch_id') == ctx.branch]
        checked(ctx)
        return result

    return {'organization': lambda ctx: semantic(ctx, 'CIVILIZATION'), 'rule': rules,
            'story_graph': story_graph, 'asset': assets, 'workflow': workflows}
