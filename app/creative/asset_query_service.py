"""Query adapter: derived candidates always pass the original Asset owner."""
from ..services.asset_query_budget import asset_query_budget
from ..services.asset_query_index import AssetQueryUnavailable


def list_assets(service, nid, scope, *, include_deleted, query):
    keyword = (query.q or "").strip().casefold()
    paging = query.limit is not None or query.offset is not None
    limit, offset = query.limit if query.limit is not None else 50, query.offset or 0
    with service._asset_scope(nid, scope), asset_query_budget() as budget:
        index = service.query_index
        snapshot = index.snapshot(service.assets._load, deadline=budget.deadline)
        binding = service.assets._scope.binding
        selected, total = [], 0
        for row in index.iter_candidates(snapshot, nid, binding, keyword=keyword,
                                         kind=query.kind, deadline=budget.deadline):
            if (not service.assets._in_scope(row, scope.get("branch_id"))
                    or (row.get("deleted_at") and not include_deleted)):
                continue
            service._validate_asset_row(nid, scope, row)
            if not isinstance(row.get("created_at", ""), str):
                raise AssetQueryUnavailable()
            if not paging or offset <= total < offset + limit:
                selected.append(row["id"])
            total += 1
        items = []
        for aid in selected:
            budget.check()
            try:
                row = service._row(nid, scope, aid, deleted=include_deleted)
            except FileNotFoundError:
                index.verify(snapshot, deadline=budget.deadline)
                raise AssetQueryUnavailable() from None
            items.append(service._view(nid, scope, row))
        index.verify(snapshot, deadline=budget.deadline)
        result = {"items": items}
        if paging:
            result.update(total=total, limit=limit, offset=offset, has_more=offset + len(items) < total)
        return result
