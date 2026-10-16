"""Dedicated Prompt authoring service (R3-W) over the existing asset owner.

This is a **thin adapter**. It creates no asset, version, review, task or database
system: every write goes through `AssetLibraryService.create` / `update_metadata`, and
the version chain is the owner's own immutable-asset chain.

What the owner already guarantees (verified, not assumed — see W1 in
`ROUND3W_DECISIONS.md`):

* `create(idempotency_key=...)` is **exactly-once**: a repeat returns the existing asset,
  and the same key used for **different content** raises `AssetIdempotencyConflict`.
  A deleted asset refuses the key rather than silently recreating it.
* `update_metadata(expected_version=...)` is compare-and-set, and is a **no-op when the
  value is unchanged**, so replaying the same payload does not bump a version.
* Asset bytes are immutable, so a body revision must be a new asset — old revisions
  cannot be overwritten even by accident.
* `owner_actor_id` keeps a new draft private to its author; reads require the actor.

What this service adds on top:

* a **family + revision** model (`family_id` stable across revisions);
* `expected_previous_asset_id` / `expected_revision` verification, so a stale editor
  cannot write the next revision;
* an explicit **request-id** ledger so a lost HTTP response is replayable and a reused
  request id with different content is refused;
* a deterministic **conflict rule** for two racers that both allocate the same revision.

The original asset project_scope now serializes allocation across processes through
its existing asset-library mutation lease. The historical conflict detector remains
for legacy conflicting rows. Deleted revisions stay in CAS and request accounting;
deleting a head never frees its revision or request identity for reuse.
"""
from __future__ import annotations

import base64
import json
from typing import Any
from uuid import uuid4

from ..experimental.common import now
from ..services.asset_library_service import AssetIdempotencyConflict
from ..services.v1_capability_service import CapabilityVersionConflict
from . import prompt_asset as prompt

#: Feature required for a studio-bound asset (the owner enforces the binding).
REQUIRED_FEATURES = ("narrative_production_v2",)

#: The **only** fields a prompt conflict may disclose. Deliberately excludes user text,
#: negative prompts, internal owner markers, project bindings, credentials and any other
#: family's asset ids.
CONFLICT_PUBLIC_FIELDS: tuple[str, ...] = (
    "code", "family_id", "revision", "expected_revision", "current_revision", "retryable",
)


class PromptAuthoringConflict(Exception):
    """A prompt-authoring conflict with a strictly whitelisted public body.

    The shared studio invoker deliberately reduces `CapabilityVersionConflict.current` to
    `{"version", "status"}` so a conflict cannot smuggle raw internal snapshots or denied
    parent ids. That is a safety property for every existing API and is **left untouched**.
    A prompt conflict therefore travels as its own exception and is rendered by the prompt
    routes from `CONFLICT_PUBLIC_FIELDS` alone, so the client can recognise the cause and
    reload without any new disclosure.
    """

    def __init__(self, code: str, **fields):
        allowed = set(CONFLICT_PUBLIC_FIELDS) - {"code"}
        self.code = code
        self.fields = {key: value for key, value in fields.items() if key in allowed}
        super().__init__(code)

    def public(self) -> dict:
        return {"code": self.code, **self.fields}


def _as_prompt_conflict(exc, code, **fields):
    """Convert an owner CAS failure without forwarding its internal `current` payload."""
    version = exc.current.get("version") if isinstance(exc.current, dict) else None
    merged = dict(fields)
    if isinstance(version, int):
        merged.setdefault("current_revision", None)
    return PromptAuthoringConflict(code, **merged)


class PromptAuthoringService:
    """Create and revise Prompt assets through the existing owner."""

    def __init__(self, workspace, bible=None):
        self.workspace, self.bible = workspace, bible

    # ------------------------------------------------------------- reads --
    def _prompt_rows(self, nid, scope, actor, branch_id):
        """Every prompt asset visible to this actor, under the owner's own lease."""
        return [row for row in self.workspace.assets.list(nid, branch_id=branch_id, actor_id=actor, include_deleted=True)
                if prompt._text(row.get("kind")) == prompt.PROMPT_KIND]

    @staticmethod
    def _request_digest(body) -> str:
        """Digest of the authored request content, excluding server-side allocation.

        Uses the same `CONTENT_KEYS` projection as `prompt.content_digest`, so a replay
        compares equal to the asset it produced — a mismatch here would make every
        legitimate retry look like a reused request id.
        """
        payload = {
            "purpose": body.purpose, "origin": body.origin,
            "negative_prompt": body.negative_prompt, "model_reference": body.model_reference,
            "parameters": body.parameters, "seed": body.seed,
            "reference_asset_ids": list(body.reference_asset_ids), "output_asset_ids": [],
            "character_ids": list(body.character_ids), "scene_ids": list(body.scene_ids),
            "shot_ids": list(body.shot_ids), "change_note": body.change_note,
            "change_reason": body.change_reason, "redacted": body.redacted,
        }
        basis = prompt.digest(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str))
        # Compare the payload projection only; the body is compared separately against the
        # stored bytes, so a different text can never compare equal.
        return basis

    @staticmethod
    def _receipt(asset, body, *, replay: bool, revision: int, previous: str | None) -> dict[str, Any]:
        return {
            "family_id": prompt.family_of(asset),
            "asset_id": prompt.asset_id_of(asset),
            "revision": revision,
            "asset_version": asset.get("version"),
            "text_digest": prompt.digest(body.text.encode("utf-8")),
            "idempotent_replay": replay,
            "previous_asset_id": previous,
            "payload_digest": prompt.content_digest(asset),
        }

    def _find_request(self, rows, request_id: str):
        """Find the asset a previous attempt with this request id produced.

        Matched on the owner's **own** recorded `idempotency_key` first, because that is
        the field the owner itself dedupes on, and a replay must agree with the owner
        rather than with our reading of the payload.
        """
        for row in rows:
            if row.get("idempotency_key") == request_id:
                return row
        for row in rows:
            if row.get("idempotency_key") is None and prompt.request_id_of(row) == request_id:
                return row
        return None

    # ------------------------------------------------------------ writes --
    def create(self, nid, scope, actor, body, guard=lambda: None):
        """Create revision 1 of a brand-new family."""
        return self._write(nid, scope, actor, body, family_id=None, guard=guard)

    def revise(self, nid, scope, actor, family_id, body, guard=lambda: None):
        """Save the next revision of an existing family."""
        if not isinstance(family_id, str) or not family_id.strip():
            raise ValueError("PROMPT_FAMILY_REQUIRED")
        return self._write(nid, scope, actor, body, family_id=family_id.strip(), guard=guard)

    def _write(self, nid, scope, actor, body, *, family_id, guard):
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("PROMPT_AUTHORING_ACTOR_REQUIRED")
        self.workspace.store.key(nid, scope)
        self.workspace.novels.get(nid)
        branch_id = scope.get("branch_id")
        wanted = self._request_digest(body)
        operation = "CREATE" if family_id is None else "REVISE"
        request_identity = prompt.digest(json.dumps({"actor": actor, "project": nid, "scope": scope,
            "operation": operation, "family_id": family_id,
            "expected_previous_asset_id": getattr(body, "expected_previous_asset_id", None),
            "expected_revision": getattr(body, "expected_revision", None),
            "content_digest": wanted, "text_digest": prompt.digest(body.text.encode("utf-8")),
            "request_id": body.request_id}, sort_keys=True, ensure_ascii=False))

        with self.workspace._asset_scope(nid, scope):
            rows = self._prompt_rows(nid, scope, actor, branch_id)

            # (1) Exactly-once. A repeated request id returns the revision it produced,
            #     so a lost HTTP response is safely retryable. Reusing the id for
            #     different content is a conflict, never a silent overwrite.
            resume_asset = None
            resume_origin = None
            replay = self._find_request(rows, body.request_id)
            if replay is not None:
                if replay.get("deleted_at"):
                    raise PromptAuthoringConflict("PROMPT_REQUEST_DELETED", retryable=False)
                origin = replay.get("_prompt_write_origin")
                if origin is not None and (not isinstance(origin, dict)
                        or origin.get("contract") != "studio-prompt-write-origin/1"
                        or origin.get("operation") != operation
                        or origin.get("request_digest") != request_identity):
                    raise PromptAuthoringConflict("PROMPT_REQUEST_ID_REUSED", retryable=False)
                if prompt.payload_is_readable(prompt.prompt_payload(replay)):
                    saved = prompt.prompt_payload(replay)
                    if family_id is None:
                        changed_target = prompt.revision_of(replay) != 1 or bool(saved.get("previous_asset_id"))
                    else:
                        changed_target = (prompt.family_of(replay) != family_id
                            or saved.get("previous_asset_id") != body.expected_previous_asset_id
                            or prompt.revision_of(replay) != body.expected_revision + 1)
                    if changed_target:
                        raise PromptAuthoringConflict("PROMPT_REQUEST_ID_REUSED", retryable=False)
                    # Compare against the **stored** body, not against the incoming text:
                    # folding the request's own text into both sides would make any
                    # content compare equal and silently accept a reused request id.
                    try:
                        stored = self.workspace.assets.content(
                            prompt.asset_id_of(replay), branch_id=branch_id, actor_id=actor)
                    except (FileNotFoundError, ValueError, PermissionError):
                        stored = None
                    stored_digest = prompt.digest(stored) if stored is not None else None
                    if (prompt.content_digest(replay) != wanted
                            or stored_digest != prompt.digest(body.text.encode("utf-8"))):
                        # The request identity has been spent on different content. Never
                        # rebind the stored body to new metadata.
                        raise PromptAuthoringConflict("PROMPT_REQUEST_ID_REUSED", retryable=False)
                    return self._receipt(replay, body, replay=True,
                                         revision=prompt.revision_of(replay),
                                         previous=prompt.prompt_payload(replay).get("previous_asset_id"))
                # The body asset exists but its payload write did not finish (W4.2). It is
                # resumed on the same asset — but only if its stored bytes are still this
                # request's bytes. Resuming onto different text would bind the OLD body to
                # NEW metadata, so that case is refused instead of completed.
                if (not isinstance(origin, dict) or not isinstance(origin.get("allocated_family_id"), str)
                        or not origin["allocated_family_id"]
                        or (family_id is not None and origin["allocated_family_id"] != family_id)):
                    raise PromptAuthoringConflict("PROMPT_REQUEST_ORIGIN_UNVERIFIED", retryable=False)
                try:
                    pending_bytes = self.workspace.assets.content(
                        prompt.asset_id_of(replay), branch_id=branch_id, actor_id=actor)
                except (FileNotFoundError, ValueError, PermissionError):
                    pending_bytes = None
                if pending_bytes is None or prompt.digest(pending_bytes) != prompt.digest(
                        body.text.encode("utf-8")):
                    raise PromptAuthoringConflict("PROMPT_REQUEST_ID_REUSED", retryable=False)
                resume_asset = replay
                resume_origin = origin

            groups = prompt.families(rows, include_deleted=True)
            if family_id is None:
                family_id = resume_origin["allocated_family_id"] if resume_origin else str(uuid4())
                revision, previous = 1, None
            else:
                versions = groups.get(family_id)
                if not versions or not any(not row.get("deleted_at") for row in versions):
                    raise FileNotFoundError(family_id)
                head = versions[-1]
                head_revision = prompt.revision_of(head)
                head_id = prompt.asset_id_of(head)
                # A stale editor must not write the next revision.
                if head_revision != body.expected_revision or head_id != body.expected_previous_asset_id:
                    raise PromptAuthoringConflict(
                        "PROMPT_REVISION_STALE", family_id=family_id,
                        expected_revision=body.expected_revision, current_revision=head_revision,
                        retryable=True)
                if head.get("deleted_at"):
                    raise PromptAuthoringConflict("PROMPT_REVISION_DELETED", family_id=family_id,
                                                  current_revision=head_revision, retryable=False)
                revision, previous = head_revision + 1, head_id

            payload = prompt.build_payload(
                family_id=family_id, revision=revision, purpose=body.purpose, origin=body.origin,
                negative_prompt=body.negative_prompt, model_reference=body.model_reference,
                parameters=body.parameters, seed=body.seed,
                reference_asset_ids=body.reference_asset_ids, output_asset_ids=(),
                character_ids=body.character_ids, scene_ids=body.scene_ids, shot_ids=body.shot_ids,
                change_note=body.change_note, change_reason=body.change_reason,
                previous_asset_id=previous, redacted=body.redacted,
                request_id=body.request_id, state=prompt.STATE_ACTIVE)

            # (2) Bytes first. `idempotency_key` makes this exactly-once at the owner too,
            #     and raises if the key was already used for different content. A resumed
            #     attempt already owns its asset, so it skips creation entirely.
            try:
                if resume_asset is not None:
                    asset = self.workspace.assets.update_metadata(
                        prompt.asset_id_of(resume_asset),
                        {"parameters": {prompt.PAYLOAD_KEY: payload}},
                        branch_id=branch_id, expected_version=resume_asset.get("version"),
                        actor_id=actor, guard=guard)
                else:
                    created = self.workspace.assets.create(
                        nid, f"prompt-{family_id[:8]}-r{revision}.txt",
                        base64.b64encode(body.text.encode("utf-8")).decode(),
                        media_type="text/plain", kind=prompt.PROMPT_KIND,
                        idempotency_key=body.request_id, branch_id=branch_id,
                        required_features=REQUIRED_FEATURES, owner_actor_id=actor, guard=guard,
                        _initial_prompt_write={"contract": "studio-prompt-write-origin/1", "operation": operation,
                            "allocated_family_id": family_id,
                            "expected_previous_asset_id": getattr(body, "expected_previous_asset_id", None),
                            "expected_revision": getattr(body, "expected_revision", None),
                            "request_digest": request_identity})

                    # (3) Then the payload. A replay of the same payload is a no-op at the
                    #     owner, so an interrupted run leaves no half-version behind.
                    asset = self.workspace.assets.update_metadata(
                        created["id"], {"parameters": {prompt.PAYLOAD_KEY: payload}},
                        branch_id=branch_id, expected_version=created.get("version"),
                        actor_id=actor, guard=guard)
            except CapabilityVersionConflict as exc:
                # The owner's own CAS lost. Surface the cause without forwarding its
                # internal `current` snapshot (which the shared wrapper would strip anyway).
                raise PromptAuthoringConflict(
                    "PROMPT_ASSET_VERSION_CONFLICT", family_id=family_id, revision=revision,
                    retryable=True) from None
            except AssetIdempotencyConflict:
                # The owner already spent this request id on different bytes.
                raise PromptAuthoringConflict(
                    "PROMPT_REQUEST_ID_REUSED", retryable=False) from None

            # (4) Deterministic conflict rule. Ordering by asset id is arbitrary but total,
            #     so both racers agree on the same winner without a shared lock.
            asset_id = prompt.asset_id_of(asset)
            rivals = [row for row in self._prompt_rows(nid, scope, actor, branch_id)
                      if prompt.asset_id_of(row) != asset_id
                      and prompt.family_of(row) == family_id
                      and prompt.revision_of(row) == revision
                      and prompt.authoring_state(row) == prompt.STATE_ACTIVE]
            if rivals and min(prompt.asset_id_of(row) for row in rivals) < asset_id:
                # We lost. Keep the content, mark it, and refuse to call it a revision.
                self.workspace.assets.update_metadata(
                    asset_id,
                    {"parameters": {prompt.PAYLOAD_KEY: {**payload, "state": prompt.STATE_CONFLICTED}}},
                    branch_id=branch_id, expected_version=asset.get("version"), actor_id=actor)
                raise PromptAuthoringConflict(
                    "PROMPT_REVISION_CONFLICT", family_id=family_id, revision=revision,
                    retryable=True)

            return self._receipt(asset, body, replay=False, revision=revision, previous=previous)

    # ------------------------------------------------------------ review --
    def approve(self, nid, scope, actor, family_id, asset_id, expected_version, guard=lambda: None):
        """Reuse the owner's review path. Never sets approval from client input."""
        if not isinstance(family_id, str) or not family_id.strip():
            raise ValueError("PROMPT_FAMILY_REQUIRED")
        self.workspace.store.key(nid, scope)
        self.workspace.novels.get(nid)
        branch_id = scope.get("branch_id")
        with self.workspace._asset_scope(nid, scope):
            rows = self._prompt_rows(nid, scope, actor, branch_id)
            target = next((row for row in rows if prompt.asset_id_of(row) == asset_id), None)
            if target is None or target.get("deleted_at") or prompt.family_of(target) != family_id:
                raise FileNotFoundError(asset_id)
            if prompt.authoring_state(target) != prompt.STATE_ACTIVE:
                raise ValueError("PROMPT_REVISION_NOT_REVIEWABLE")
            return self.workspace.assets.promote_owned(
                asset_id, actor_id=actor, branch_id=branch_id, expected_version=expected_version,
                provenance={"contract": "prompt-authoring/1", "family_id": family_id,
                            "revision": prompt.revision_of(target), "decided_at": now()},
                guard=guard)
