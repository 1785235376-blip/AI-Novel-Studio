"""Read-only Prompt Library service over the existing asset owner.

Round 3 §3 forbids a second asset, version or review system. This service therefore
**creates nothing**: it reads prompt assets (`kind="prompt"`) out of the existing
asset owner, reads the Character/Scene Bible projection for binding resolution, and
returns one bounded projection.

Prompt assets are authored through the existing asset owner — `create` for the bytes
and `update_metadata` for the payload, with `annotate_lineage` for the version chain.
No route here writes anything, and the AI-behaviour rule of Round 3 §10 (never
overwrite a user's prompt, never auto-version, never delete history) is enforced by
this service having no write path at all.
"""
from __future__ import annotations

from ..experimental.common import now
from .prompt_asset import (
    PROMPT_LIBRARY_CONTRACT, is_prompt_asset, project_prompt_context,
    project_prompt_detail, project_prompt_library,
)

#: Bounded reads: prompt text is only fetched for a limited number of assets.
MAX_PROMPTS = 200
MAX_TEXT_BYTES = 64 * 1024


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

    def _read_prompts(self, nid, scope):
        """Full metadata **and** bytes for every prompt asset, in one asset lease.

        `asset_index` is deliberately a bounded projection that excludes
        `parameters`, so a prompt's payload cannot be read from it — the owner's own
        `list`/`content` reads are required. Both happen under the same
        `_asset_scope` lease the rest of the studio uses, so scope and binding are
        resolved by the owner rather than re-implemented here.
        """
        rows, texts = [], {}
        with self.workspace._asset_scope(nid, scope):
            for row in self.workspace.assets.list(nid, branch_id=scope.get("branch_id")):
                if not is_prompt_asset(row):
                    continue
                # A prompt asset's review is expressed by the owner's own marker; it
                # is reported as it is, never upgraded or invented.
                row = {**row, "review_status": "APPROVED" if row.get("approved_at") else "DRAFT"}
                rows.append(row)
                if len(rows) >= MAX_PROMPTS:
                    break
                try:
                    data = self.workspace.assets.content(str(row["id"]), branch_id=scope.get("branch_id"))
                except (FileNotFoundError, ValueError):
                    continue
                texts[str(row["id"])] = data[:MAX_TEXT_BYTES].decode("utf-8", errors="replace")
        return rows, texts

    def _bible_indices(self, nid, scope, prompt_rows):
        """Character/location/asset/shot ids that really exist in this project."""
        if self.bible is None:
            return None
        projection = self.bible.projection(nid, scope)
        return {
            "character_ids": [row["character_id"] for row in projection["character_bible"]["entries"]],
            "location_ids": [row["location_id"] for row in projection["scene_bible"]["entries"]],
            "asset_ids": [str(row.get("id")) for row in prompt_rows]
            + [str(row.get("id")) for row in self.workspace.asset_index(nid, scope)],
            "shot_ids": sorted({entry.get("shot_id") for row in projection["character_bible"]["entries"]
                                for entry in row.get("used_in", []) if entry.get("shot_id")}),
            "characters": projection["character_bible"]["entries"],
            "locations": projection["scene_bible"]["entries"],
        }

    def library(self, nid, scope):
        self.workspace.store.key(nid, scope)
        self.workspace.novels.get(nid)
        rows, texts = self._read_prompts(nid, scope)
        projected = project_prompt_library(
            rows, bible=self._bible_indices(nid, scope, rows), asset_text=texts)
        projected.update(project_id=nid, scope=self._scope_view(nid, scope), generated_at=now(),
                         asset_owner="AssetLibraryService", bible_owner="bible_projection")
        return projected

    def detail(self, nid, scope, family_id):
        self.workspace.store.key(nid, scope)
        self.workspace.novels.get(nid)
        rows, texts = self._read_prompts(nid, scope)
        projected = project_prompt_detail(
            family_id, rows, bible=self._bible_indices(nid, scope, rows), asset_text=texts)
        projected.update(project_id=nid, scope=self._scope_view(nid, scope), generated_at=now())
        return projected

    def context(self, nid, scope, character_ids=(), location_ids=(), document_id=None):
        """Round 3-D: assemble the *sources* a prompt could draw on. Never the text."""
        self.workspace.store.key(nid, scope)
        self.workspace.novels.get(nid)
        bible = self._bible_indices(nid, scope, [])
        shot_cards = []
        director_intent = None
        if document_id:
            from .director_intent import project_director_intent, project_shot_cards
            document = self.workspace.creative.get(nid, scope, document_id)
            director_intent = project_director_intent(document)
            shot_cards = project_shot_cards(document)
        projected = project_prompt_context(
            character_ids=character_ids, location_ids=location_ids,
            director_intent=director_intent, shot_cards=shot_cards, bible=bible)
        projected.update(project_id=nid, scope=self._scope_view(nid, scope), generated_at=now())
        return projected
