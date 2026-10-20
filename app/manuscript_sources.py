"""Explicit source routing; a missing branch adapter never selects mainline."""
from __future__ import annotations


def scoped_chapters(chapters, scope):
    if not scope or scope.get('mode') == 'local': return chapters
    resolver = getattr(chapters, 'branch_authority', None)
    if callable(resolver):
        from .experimental.flags import require_flag
        require_flag('branch_manuscript_v1')
        return resolver(scope)
    return FencedBranchView(chapters, scope)


def reader_available(reader, ctx):
    if ctx.scope.get('mode') == 'local': return True
    if reader is None: return False
    available = getattr(reader, 'available', None)
    return bool(available(ctx)) if callable(available) else True


def mainline_reader(reader):
    return reader is None or bool(getattr(reader, 'mainline_passthrough', False))


class FencedBranchView:
    """Read-only injected adapter; prove each row belongs to this exact branch.

    Unscoped/mainline adapters yield no rows and cannot resolve an ID. We never
    synthesize branch metadata, and never expose an unchecked history.
    """
    def __init__(self, chapters, scope): self.chapters, self.scope = chapters, dict(scope)
    def _owned(self, row):
        return (self.scope.get('mode') == 'collaboration' and bool(self.scope.get('branch_id'))
                and row.get('novel_id') == self.scope.get('novel_id')
                and row.get('branch_id') == self.scope['branch_id']
                and (row.get('scope') is None or row['scope'] == self.scope))
    def get(self, cid):
        row = self.chapters.get(cid)
        if not self._owned(row): raise FileNotFoundError(cid)
        return row
    def list(self, nid):
        if nid != self.scope.get('novel_id'): raise FileNotFoundError(nid)
        return [row for row in self.chapters.list(nid) if self._owned(row)]
    def history(self, cid):
        self.get(cid)
        return self.chapters.history(cid)
