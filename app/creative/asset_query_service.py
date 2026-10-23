"""Query adapter: derived candidates always pass the original Asset owner."""
import hashlib
import json

from ..experimental.flags import enabled_flags
from ..services.asset_query_budget import asset_query_budget
from ..services.asset_query_index import AssetQueryChanged, AssetQueryUnavailable
from .asset_query_cursor import AssetQueryCursorCodec, load_signing_key

METADATA_FIELDS = ("id", "filename", "kind", "media_type", "size", "sha256", "version",
                   "created_at", "updated_at", "deleted_at")
PROJECTION = "asset-metadata/1"


def metadata_projection(row):
    # The original permissive File loader is not a wire schema. Never copy a
    # corrupted nested object into this deliberately scalar-only projection.
    required = ("id", "filename", "kind", "media_type", "sha256", "created_at")
    optional = ("updated_at", "deleted_at")
    if (any(not isinstance(row.get(field), str) for field in required)
            or any(row.get(field) is not None and not isinstance(row[field], str) for field in optional)):
        raise AssetQueryUnavailable()
    return {field: row.get(field) for field in METADATA_FIELDS}


def cursor_binding(nid, scope, binding, actor_id, query, include_deleted, flags):
    payload = {"project": nid, "scope": scope, "owner_binding": binding, "actor": actor_id,
               "q": (query.q or "").strip().casefold(), "kind": query.kind,
               "include_deleted": include_deleted, "limit": query.limit or 50,
               "flags": flags, "sort": "created_at,id:asc/1", "projection": PROJECTION}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode("ascii")).hexdigest()


def list_assets(service, nid, scope, *, include_deleted, query, actor_id=None):
    keyword = (query.q or "").strip().casefold()
    cursor_mode = query.page_mode == "cursor"
    paging = query.limit is not None or query.offset is not None
    limit, offset = query.limit if query.limit is not None else 50, query.offset or 0
    with service._asset_scope(nid, scope), asset_query_budget() as budget:
        index = service.query_index
        snapshot = index.snapshot(service.assets._load, deadline=budget.deadline)
        binding = service.assets._scope.binding
        flags = sorted(enabled_flags())
        position, codec, token_binding = None, None, None
        if cursor_mode:
            token_binding = cursor_binding(nid, scope, binding, actor_id, query, include_deleted, flags)
            codec = AssetQueryCursorCodec(load_signing_key(index.directory))
            if query.cursor is not None:
                position = codec.decode(query.cursor, token_binding, snapshot.revision)
        selected, total, remaining = [], 0, 0
        for row in index.iter_candidates(snapshot, nid, binding, keyword=keyword,
                                         kind=query.kind, deadline=budget.deadline):
            if (not service.assets._in_scope(row, scope.get("branch_id"))
                    or (row.get("deleted_at") and not include_deleted)):
                continue
            service._validate_asset_row(nid, scope, row)
            if not isinstance(row.get("created_at", ""), str):
                raise AssetQueryUnavailable()
            order = (row.get("created_at", ""), row["id"])
            if cursor_mode and (len(order[0]) > 80 or any(ord(c) < 32 or ord(c) == 127 for c in order[0])):
                raise AssetQueryUnavailable()
            if cursor_mode:
                if position is None or order > position.after:
                    remaining += 1
                    if len(selected) < limit:
                        selected.append(row["id"])
            elif not paging or offset <= total < offset + limit:
                selected.append(row["id"])
            total += 1
        items, last_order = [], None
        for aid in selected:
            budget.check()
            try:
                row = service._row(nid, scope, aid, deleted=include_deleted)
            except FileNotFoundError:
                index.verify(snapshot, deadline=budget.deadline)
                raise AssetQueryUnavailable() from None
            last_order = (row.get("created_at", ""), row["id"])
            items.append(metadata_projection(row) if cursor_mode
                         else service._view(nid, scope, row))
        index.verify(snapshot, deadline=budget.deadline)
        if cursor_mode:
            if flags != sorted(enabled_flags()):
                raise AssetQueryChanged()
            if position is not None:
                # Check the fixed TTL again even on the last page, which does
                # not mint a successor token and therefore never calls encode.
                codec.decode(query.cursor, token_binding, snapshot.revision)
            has_more = remaining > len(items)
            next_cursor = codec.encode(token_binding, snapshot.revision, last_order, position) if has_more else None
            return {"items": items, "total": total, "limit": limit, "has_more": has_more,
                    "next_cursor": next_cursor, "projection": PROJECTION}
        result = {"items": items}
        if paging:
            result.update(total=total, limit=limit, offset=offset, has_more=offset + len(items) < total)
        return result
