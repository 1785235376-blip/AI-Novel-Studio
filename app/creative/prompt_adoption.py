"""R3-I — Pinned Prompt Revision Adoption into a Storyboard Shot.

A user picks **one explicit Prompt revision** and adopts it into one shot of an existing
STORYBOARD document. The adopted text is written to that shot's `frame_prompt`, a new
immutable document revision is committed through the existing `CreativeService.update` CAS
path, and the server records the verified provenance alongside it.

Scope by design, and deliberately narrow:

* only STORYBOARD documents, and only the `frame_prompt` field of a named shot. There is no
  generic `{owner}` write API: a route that accepted every owner type would be a second,
  unaudited write surface over owners that already have their own rules.
* the adopted revision is re-read **server-side, under the caller's own actor**, so the
  prompt owner's private-owner filtering applies. A client-supplied digest is treated as a
  claim to check, never as proof.
* adoption is **not** approval of the shot and **not** authorisation to render. It starts no
  job, calls no model and spends nothing.
* drift is pinned: the record holds the exact asset id, revision and digest. A newer revision
  in the family is reported as `newer_revision_available` and never rebinds automatically.
"""
from __future__ import annotations

from uuid import uuid4

from ..experimental.common import now
from . import prompt_asset as prompt

#: `models.py` declares `frame_prompt: str = Field(default="", max_length=16000, strict=True)`.
#: Enforced here too, and over-limit input is REFUSED rather than truncated into a partial
#: adoption that would look complete.
FRAME_PROMPT_MAX = 16000

#: The contract of one adoption proof, stored on the target document revision.
PROOF_CONTRACT = "prompt-adoption/1"
PROOF_KEYS = ("contract", "shot_id", "field", "family_id", "asset_id", "revision", "digest",
              "digest_of", "adopted_by", "adopted_at", "request_id", "target_version",
              "target_digest", "request_digest", "source_snapshot")


class PromptAdoptionService:
    """Adopt a verified Prompt revision into one storyboard shot."""

    def __init__(self, workspace, prompts):
        self.workspace, self.prompts = workspace, prompts

    # ------------------------------------------------------------- reads --
    @staticmethod
    def _proofs(row) -> list:
        value = row.get("prompt_adoptions")
        return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []

    @staticmethod
    def _shot(row, shot_id: str):
        content = row.get("content")
        if not isinstance(content, dict):
            return None
        shots = content.get("shots")
        if not isinstance(shots, list):
            return None
        return next((item for item in shots
                     if isinstance(item, dict) and item.get("id") == shot_id), None)

    def _document(self, nid, scope, actor, document_id):
        """The caller's own STORYBOARD document, or a refusal."""
        row = self.workspace.creative.get(nid, scope, document_id)
        if row.get("mode") != "STORYBOARD":
            # Only storyboard documents are adoptable in this slice.
            raise ValueError("PROMPT_ADOPTION_TARGET_NOT_STORYBOARD")
        if prompt._text(row.get("status")) == "ARCHIVED":
            raise FileNotFoundError(document_id)
        return row

    def read(self, nid, scope, document_id, actor=None):
        """The pinned adoptions currently recorded on the document, plus drift notices."""
        self.workspace.store.key(nid, scope)
        self.workspace.novels.get(nid)
        row = self._document(nid, scope, actor, document_id)
        entries = []
        for proof in self._proofs(row):
            entry = dict(proof)
            entry["newer_revision_available"] = False
            entry["source_readable"] = True
            try:
                # Re-read the family under the caller's actor: a deleted, redacted or
                # now-unreadable source keeps its historical proof but cannot be re-shown
                # or re-adopted.
                detail = self.prompts.detail(nid, scope, proof["family_id"], actor)
                entry["newer_revision_available"] = detail["revision"] > proof["revision"]
                body = self.prompts.revision_body(nid, scope, proof["family_id"],
                                                  proof["asset_id"], actor)
                entry["source_readable"] = body["state"] == prompt.BODY_COMPLETE and bool(body["verified"])
            except (FileNotFoundError, ValueError, PermissionError, KeyError):
                entry["source_readable"] = False
            entries.append(entry)
        return {"contract": PROOF_CONTRACT, "document_id": document_id,
                "version": row.get("version"), "digest": self.workspace.creative.document_digest(row),
                "adoptions": entries, "generated_at": now()}

    # ------------------------------------------------------------ writes --
    def adopt(self, nid, scope, actor, document_id, shot_id, body, guard=lambda: None):
        """Adopt `body.family_id`/`body.asset_id` (revision `body.revision`) into `shot_id`."""
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("PROMPT_ADOPTION_ACTOR_REQUIRED")
        self.workspace.store.key(nid, scope)
        self.workspace.novels.get(nid)
        row = self._document(nid, scope, actor, document_id)
        shot = self._shot(row, shot_id)
        if shot is None:
            raise FileNotFoundError(shot_id)

        # ---- exactly-once by request identity, decided from the SERVER's stored proof ----
        want = self._request_digest(body, shot_id)
        for proof in self._proofs(row):
            if proof.get("request_id") != body.request_id:
                continue
            if proof.get("request_digest") != want:
                raise ValueError("PROMPT_ADOPTION_REQUEST_REUSED")
            # Same request, same verified input: this is a replay. Return the existing
            # document instead of producing a second revision.
            return {"replayed": True, "document_id": document_id, "shot_id": shot_id,
                    "version": row.get("version"),
                    "digest": self.workspace.creative.document_digest(row),
                    "adoption": proof}

        # ---- verify the Prompt revision server-side, under the caller's actor ----
        detail = self.prompts.detail(nid, scope, body.family_id, actor)
        if detail["head_asset_id"] != body.asset_id or detail["revision"] != body.revision:
            # Only the family's current head revision is adoptable in this slice.
            raise ValueError("PROMPT_ADOPTION_REVISION_NOT_HEAD")
        if not detail.get("approved"):
            raise ValueError("PROMPT_ADOPTION_NOT_APPROVED")
        if detail.get("redacted"):
            raise ValueError("PROMPT_ADOPTION_SOURCE_REDACTED")
        if not detail.get("history_complete") or not detail.get("read_complete"):
            raise ValueError("PROMPT_ADOPTION_SOURCE_INCOMPLETE")

        body_read = self.prompts.revision_body(nid, scope, body.family_id, body.asset_id, actor)
        if body_read["state"] != prompt.BODY_COMPLETE:
            raise ValueError(f"PROMPT_ADOPTION_SOURCE_{body_read['state']}")
        if not body_read["verified"] or body_read["digest_of"] != prompt.DIGEST_OF_ORIGINAL:
            raise ValueError("PROMPT_ADOPTION_SOURCE_UNVERIFIED")
        text = body_read["value"]
        if not isinstance(text, str):
            raise ValueError("PROMPT_ADOPTION_SOURCE_UNREADABLE")
        # The client's claimed digest is a claim to CHECK, never proof.
        if body.expected_digest != body_read["digest"]:
            raise ValueError("PROMPT_ADOPTION_DIGEST_MISMATCH")
        if len(text) > FRAME_PROMPT_MAX:
            # Refuse; never truncate into something that would look like a complete adoption.
            raise ValueError("PROMPT_ADOPTION_TOO_LONG")

        # ---- build the new document content: one field of one shot, nothing else ----
        content = dict(row.get("content") or {})
        shots = [dict(item) if isinstance(item, dict) else item for item in content.get("shots", [])]
        for item in shots:
            if isinstance(item, dict) and item.get("id") == shot_id:
                item["frame_prompt"] = text
        content["shots"] = shots

        target_digest = self.workspace.creative.document_digest(row)
        proof = {
            "contract": PROOF_CONTRACT, "shot_id": shot_id, "field": "frame_prompt",
            "family_id": body.family_id, "asset_id": body.asset_id, "revision": body.revision,
            "digest": body_read["digest"], "digest_of": body_read["digest_of"],
            "adopted_by": actor, "adopted_at": now(), "request_id": body.request_id,
            "target_version": row.get("version"), "target_digest": target_digest,
            "request_digest": want,
            "source_snapshot": self._source_snapshot(detail),
        }
        updated = self.workspace.creative.update(
            nid, scope, actor, document_id, body.expected_version, content,
            reauthorize=guard, expected_digest=body.expected_digest_target, server_proof=proof)
        stored = next((item for item in self._proofs(updated)
                       if item.get("shot_id") == shot_id), proof)
        return {"replayed": False, "document_id": document_id, "shot_id": shot_id,
                "version": updated.get("version"),
                "digest": self.workspace.creative.document_digest(updated),
                "adoption": stored}

    # ------------------------------------------------------------ helpers --
    @staticmethod
    def _source_snapshot(detail) -> list:
        """The binding targets the adopted revision declared, as the server resolved them.

        These are recorded for traceability only. `INDEX_SUPPLIED` means the index contained
        the target; it is not an approval and not a write-time verification.
        """
        rows = []
        for kind, group in (detail.get("bindings") or {}).items():
            if not isinstance(group, list):
                continue
            for item in group:
                if isinstance(item, dict) and item.get("id"):
                    rows.append({"kind": kind, "id": item["id"],
                                 "resolution": item.get("resolution"),
                                 "verification": item.get("verification")})
        return rows

    @staticmethod
    def _request_digest(body, shot_id: str) -> str:
        """Identity of the verified request: same inputs -> same digest -> replay."""
        return prompt.digest("|".join([shot_id, body.family_id, body.asset_id,
                                       str(body.revision), body.expected_digest,
                                       str(body.expected_version),
                                       body.expected_digest_target, body.request_id]))


def new_request_id() -> str:
    return str(uuid4())
