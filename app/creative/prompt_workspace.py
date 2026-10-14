"""Read-only Prompt Library service over the existing asset owner.

Round 3 §3 forbids a second asset, version or review system. This service therefore
**creates nothing**: it reads prompt assets (`kind="prompt"`) out of the existing asset
owner, reads the Character/Scene Bible projection for binding resolution, and returns
one bounded projection.

Prompt assets are authored through the existing asset owner — `create` for the bytes
and `update_metadata` for the payload, with `annotate_lineage` for the version chain.
No route here writes anything, and the AI-behaviour rule of Round 3 §10 (never
overwrite a user's prompt, never auto-version, never delete history) is enforced by
this service having no write path at all.

R3-R read-contract fixes (2026-10-15)
------------------------------------
* **R3-R-01** the body is now read for **every returned row**, before the cap is applied.
  A returned entry can no longer lose its text merely because it sat on the boundary.
  Truncation is reported (`truncated`/`has_more`/`total_known`) instead of a bounded
  read being presented as the whole library.
* **R3-R-02** detail scans **all** prompt assets (not the first page) so a family
  outside the library page is not a spurious 404, and `read_complete` is passed through
  so `history_complete` reflects real coverage rather than being a constant.
* **R3-R-03** bodies go through `read_prompt_body`, which never silently truncates or
  replaces invalid UTF-8 and always digests the original bytes.
* **R3-R-05** the shot index is built from the **real document/shot owner**, not from
  which characters happen to appear, and is scoped per document.
* **R3-R-06** reads carry the real `actor_id` the authorisation path resolved, so the
  asset owner's own private-owner filtering applies to the author too.
"""
from __future__ import annotations

from ..experimental.common import now
from .prompt_asset import (
    MAX_TEXT, PROMPT_KIND, PROMPT_LIBRARY_CONTRACT, is_prompt_asset, project_prompt_context,
    project_prompt_detail, project_prompt_library, read_prompt_body, shot_index,
)

#: Bounded metadata read for the library listing. Bodies are read for every returned
#: row, so this bounds work without ever silently dropping a returned entry's text.
MAX_PROMPTS = 200
#: A single body is read up to this many bytes; over it the state is `TRUNCATED` and the
#: caller is told how to fetch the whole body rather than being handed a silent cut.
MAX_TEXT_BYTES = 64 * 1024
#: Detail needs the whole family, which may sit beyond the library page. This is its own
#: (larger) bound, reported honestly through `read_complete`.
MAX_PROMPT_SCAN = 2000


def _clean(value) -> str:
    return str(value).strip() if value is not None else ""


class PromptWorkspaceService:
    """Project the existing asset owner as a Prompt Library."""

    CONTRACT = PROMPT_LIBRARY_CONTRACT

    def __init__(self, workspace, bible=None):
        self.workspace, self.bible = workspace, bible

    @staticmethod
    def _scope_view(nid, scope):
        view = {"mode": scope.get("mode", "local"), "novel_id": nid}
        for key in ("workspace_id", "project_id", "storyline_id", "branch_id"):
            if key in scope:
                view[key] = scope[key]
        return view

    def _read_prompts(self, nid, scope, actor=None, *, limit=None, include_deleted=False):
        """Full metadata **and** bodies for prompt assets, in one asset lease.

        `asset_index` is deliberately a bounded projection that excludes `parameters`, so
        a prompt's payload cannot be read from it — the owner's own `list`/`content`
        reads are required. Both happen under the same `_asset_scope` lease the rest of
        the studio uses, and both are passed the **resolved actor** so the asset owner's
        own private-owner filtering is applied rather than bypassed.

        Returns `(rows, bodies, coverage)`. A row that cannot be read is still returned,
        with an explicit `UNAVAILABLE` body — never silently dropped.
        """
        rows, bodies = [], {}
        seen = 0
        truncated = False
        branch_id = scope.get("branch_id")
        # Resolved at call time so the bound is a live policy, not a frozen default.
        limit = MAX_PROMPTS if limit is None else limit
        with self.workspace._asset_scope(nid, scope):
            listed = self.workspace.assets.list(nid, branch_id=branch_id, actor_id=actor,
                                                include_deleted=include_deleted)
            for row in listed:
                if _clean(row.get("kind")) != PROMPT_KIND:
                    continue
                deleted = bool(row.get("deleted_at"))
                # §3.3 fix: the library excludes deleted rows, but the detail path accepts
                # them as **metadata-only tombstones** so a removed revision is visible as
                # removed instead of silently shortening the family into a "complete"
                # history. A deleted body is never read or exposed.
                if deleted and not include_deleted:
                    continue
                if seen >= limit:
                    # There is more; say so instead of pretending this is everything.
                    truncated = True
                    break
                seen += 1
                # A prompt asset's review is expressed by the owner's own marker; it is
                # reported as it is, never upgraded or invented.
                row = {**row, "review_status": "APPROVED" if row.get("approved_at") else "DRAFT"}
                rows.append(row)
                asset_id = str(row["id"])
                if deleted:
                    bodies[asset_id] = {"state": "DELETED", "value": None, "digest": None,
                                        "digest_of": None, "truncated": False, "decodable": False,
                                        "body_validated": False, "tail_unverified": False,
                                        "original_length": None, "preview_length": 0,
                                        "limit": MAX_TEXT_BYTES, "fetch": "TOMBSTONE"}
                    continue
                try:
                    raw = self.workspace.assets.content(asset_id, branch_id=branch_id, actor_id=actor)
                except (FileNotFoundError, ValueError, PermissionError):
                    bodies[asset_id] = {"state": "UNAVAILABLE", "value": None, "digest": None,
                                        "digest_of": None, "truncated": False, "decodable": False,
                                        "body_validated": False, "tail_unverified": False,
                                        "original_length": None, "preview_length": 0,
                                        "limit": MAX_TEXT_BYTES, "fetch": "UNAVAILABLE"}
                    continue
                bodies[asset_id] = read_prompt_body(raw, limit=MAX_TEXT_BYTES)
        coverage = {
            "returned": len(rows),
            "limit": limit,
            "truncated": truncated,
            "has_more": truncated,
            # The owner's listing is bounded, so a total is never invented.
            "total_known": False,
        }
        return rows, bodies, coverage

    def _shot_index(self, nid, scope, actor=None):
        """Real, scope-aware shot identity from the shot/document owner.

        Built from found shots in this project's creative documents — **not** from which
        characters happen to appear, so an empty establishing shot is still bindable,
        and two documents' shot number 1 cannot collide.
        """
        documents = []
        try:
            for row in self.workspace.creative.list(nid, scope):
                from .director_intent import project_shot_cards
                cards = project_shot_cards(row)
                if cards:
                    documents.append({"document_id": str(row.get("id")), "cards": cards})
        except (FileNotFoundError, ValueError):
            return shot_index([])
        return shot_index(documents)

    def _bible_indices(self, nid, scope, prompt_rows, actor=None):
        """Character/location/asset/shot keys that really exist for this caller."""
        if self.bible is None:
            return None
        projection = self.bible.projection(nid, scope)
        shots = self._shot_index(nid, scope, actor)
        return {
            "character_ids": [row["character_id"] for row in projection["character_bible"]["entries"]],
            "location_ids": [row["location_id"] for row in projection["scene_bible"]["entries"]],
            "asset_ids": [str(row.get("id")) for row in prompt_rows]
            + [str(row.get("id")) for row in self.workspace.asset_index(nid, scope)],
            # Scope-aware keys, so a bare shot id never mixes two documents.
            "shot_keys": sorted(shots["entries"]),
            "characters": projection["character_bible"]["entries"],
            "locations": projection["scene_bible"]["entries"],
        }

    def library(self, nid, scope, actor=None):
        self.workspace.store.key(nid, scope)
        self.workspace.novels.get(nid)
        rows, bodies, coverage = self._read_prompts(nid, scope, actor)
        projected = project_prompt_library(
            rows, bible=self._bible_indices(nid, scope, rows, actor), asset_text=bodies,
            coverage=coverage)
        projected.update(project_id=nid, scope=self._scope_view(nid, scope), generated_at=now(),
                         asset_owner="AssetLibraryService", bible_owner="bible_projection")
        return projected

    def detail(self, nid, scope, family_id, actor=None):
        """One family, scanned across the whole bounded prompt set.

        Detail must not 404 merely because the family sat beyond the library page.
        """
        self.workspace.store.key(nid, scope)
        self.workspace.novels.get(nid)
        rows, bodies, coverage = self._read_prompts(nid, scope, actor, limit=MAX_PROMPT_SCAN,
                                                    include_deleted=True)
        projected = project_prompt_detail(
            family_id, rows, bible=self._bible_indices(nid, scope, rows, actor),
            asset_text=bodies, read_complete=not coverage["truncated"])
        projected.update(project_id=nid, scope=self._scope_view(nid, scope), generated_at=now(),
                         scan_truncated=coverage["truncated"])
        return projected

    def context(self, nid, scope, character_ids=(), location_ids=(), document_id=None, actor=None):
        """Round 3-D: assemble the *sources* a prompt could draw on. Never the text."""
        self.workspace.store.key(nid, scope)
        self.workspace.novels.get(nid)
        bible = self._bible_indices(nid, scope, [], actor)
        shot_cards = []
        director_intent = None
        if document_id:
            from .director_intent import project_director_intent, project_shot_cards
            document = self.workspace.creative.get(nid, scope, document_id)
            director_intent = project_director_intent(document)
            shot_cards = project_shot_cards(document)
        projected = project_prompt_context(
            character_ids=character_ids, location_ids=location_ids,
            director_intent=director_intent, shot_cards=shot_cards, bible=bible,
            document_id=document_id)
        projected.update(project_id=nid, scope=self._scope_view(nid, scope), generated_at=now())
        return projected
