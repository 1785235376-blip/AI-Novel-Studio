"""R3-I — Pinned Prompt Revision Adoption into a Storyboard Shot.

A user picks **one explicit Prompt revision** and adopts it into one shot of an existing
STORYBOARD document. The adopted text is written to that shot's `frame_prompt`, a new
immutable document revision is committed through the existing `CreativeService.update` CAS
path, and the server records the verified provenance alongside it.

Structure note (a correction to the first draft of this module): a CreativeDocument keeps
`scenes`, `shots` and `director_notes` at the **document top level**, not inside a `content`
dict, and `CreativeProductionDocumentIn` is the DTO that `prepare_content` validates. So the
update value is built from the document's own DTO fields, and the target shot is located in
`row["shots"]`.

Scope by design, and deliberately narrow:

* only STORYBOARD documents, and only the `frame_prompt` field of one named shot. There is no
  generic `{owner}` write API: a route accepting every owner type would be a second,
  unaudited write surface over owners that already have their own rules.
* the adopted revision is re-read **server-side, under the caller's own actor**, so the prompt
  owner's private-owner filtering applies. A client-supplied digest is a claim to check,
  never proof.
* adoption is **not** approval of the shot and **not** authorisation to render. It starts no
  job, calls no model and spends nothing.
* drift is pinned: the record holds the exact asset id, revision and digest. A newer revision
  in the family is reported as `newer_revision_available` and never rebinds automatically.
"""
from __future__ import annotations

import copy

from ..experimental.common import now
from . import prompt_asset as prompt
from .models import CreativeProductionDocumentIn

#: `models.py` declares `frame_prompt: str = Field(default="", max_length=16000, strict=True)`.
#: Enforced here too, and over-limit input is REFUSED rather than truncated into a partial
#: adoption that would look complete.
FRAME_PROMPT_MAX = 16000

#: The contract of one adoption proof, stored on the target document revision.
PROOF_CONTRACT = "prompt-adoption/1"

#: The only document fields an adoption may carry into `update`. Everything else on the stored
#: row (version, history, source_evidence, project_incarnation, server proofs) is server-owned
#: and is not user-submittable DTO surface.
_DOCUMENT_FIELDS = frozenset(CreativeProductionDocumentIn.model_fields)


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
    def _shots(row) -> list:
        """Top-level `shots` — NOT row["content"]["shots"]."""
        value = row.get("shots")
        return value if isinstance(value, list) else []

    @classmethod
    def _shot(cls, row, shot_id: str):
        return next((item for item in cls._shots(row)
                     if isinstance(item, dict) and item.get("id") == shot_id), None)

    def _document(self, nid, scope, actor, document_id):
        """The caller's own STORYBOARD document, or a refusal."""
        row = self.workspace.creative.get(nid, scope, document_id)
        if prompt._text(row.get("mode")) != "STORYBOARD":
            # Only derived storyboard documents are adoptable in this slice.
            raise ValueError("PROMPT_ADOPTION_TARGET_NOT_STORYBOARD")
        if prompt._text(row.get("status")) == "ARCHIVED":
            raise FileNotFoundError(document_id)
        return row

    def read(self, nid, scope, document_id, actor=None):
        """The pinned adoptions recorded on the document, plus drift and readability."""
        self.workspace.store.key(nid, scope)
        self.workspace.novels.get(nid)
        row = self._document(nid, scope, actor, document_id)
        current = {item.get("id"): item for item in self._shots(row) if isinstance(item, dict)}
        entries = []
        for proof in self._proofs(row):
            entry = dict(proof)
            entry["newer_revision_available"] = False
            entry["source_readable"] = True
            # A proof is only CURRENT for this shot if the shot's text still is the adopted
            # text. An ordinary edit afterwards keeps the proof in history but must not keep
            # claiming the shot still uses the original Prompt body.
            shot = current.get(proof.get("shot_id")) or {}
            entry["still_applied"] = shot.get("frame_prompt") == proof.get("adopted_text")
            entry.pop("adopted_text", None)
            try:
                detail = self.prompts.detail(nid, scope, proof["family_id"], actor)
                entry["newer_revision_available"] = detail["revision"] > proof["revision"]
                body = self.prompts.revision_body(nid, scope, proof["family_id"],
                                                  proof["asset_id"], actor)
                # A masked, deleted or unreadable source keeps its historical proof but must
                # not have its plaintext re-exposed through this projection.
                entry["source_readable"] = (body["state"] == prompt.BODY_COMPLETE
                                            and bool(body["verified"]))
            except (FileNotFoundError, ValueError, PermissionError, KeyError):
                entry["source_readable"] = False
            entries.append(entry)
        return {"contract": PROOF_CONTRACT, "document_id": document_id,
                "version": row.get("version"),
                "digest": self.workspace.creative.document_digest(row),
                "adoptions": entries, "generated_at": now()}

    # ------------------------------------------------------------ writes --
    def adopt(self, nid, scope, actor, document_id, shot_id, body, guard=lambda: None):
        """Adopt the revision named by `body` into `shot_id` (path and body must agree)."""
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("PROMPT_ADOPTION_ACTOR_REQUIRED")
        if getattr(body, "shot_id", shot_id) != shot_id:
            # The path and the body must name the same shot: mixing two ids would let a
            # request be recorded against a shot it did not target.
            raise ValueError("PROMPT_ADOPTION_SHOT_ID_MISMATCH")
        self.workspace.store.key(nid, scope)
        self.workspace.novels.get(nid)
        row = self._document(nid, scope, actor, document_id)
        if self._shot(row, shot_id) is None:
            raise FileNotFoundError(shot_id)

        # ---- exactly-once, decided from the SERVER's stored history ----
        want = self._request_digest(body, document_id, shot_id, actor, scope)
        for proof in self._proofs(row):
            if proof.get("request_id") != body.request_id:
                continue
            if (proof.get("request_digest") != want or proof.get("document_id") != document_id
                    or proof.get("shot_id") != shot_id):
                raise ValueError("PROMPT_ADOPTION_REQUEST_REUSED")
            return {"replayed": True, "document_id": document_id, "shot_id": shot_id,
                    "version": row.get("version"),
                    "digest": self.workspace.creative.document_digest(row),
                    "adoption": proof}

        # ---- verify the Prompt revision server-side, under the caller's own actor ----
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

        # ---- build the update value from the document's OWN DTO fields ----
        value = {key: copy.deepcopy(row[key]) for key in _DOCUMENT_FIELDS if key in row}
        shots = [copy.deepcopy(item) for item in self._shots(row)]
        for item in shots:
            if isinstance(item, dict) and item.get("id") == shot_id:
                item["frame_prompt"] = text
        value["shots"] = shots
        # `update()` runs this through prepare_content; a client-supplied proof must never
        # ride along, and `update` itself strips it regardless.
        value.pop("prompt_adoptions", None)

        proof = {
            "contract": PROOF_CONTRACT, "document_id": document_id, "shot_id": shot_id,
            "field": "frame_prompt",
            "family_id": body.family_id, "asset_id": body.asset_id, "revision": body.revision,
            "digest": body_read["digest"], "digest_of": body_read["digest_of"],
            "adopted_text": text,
            "adopted_by": actor, "adopted_at": now(), "request_id": body.request_id,
            "target_version": row.get("version"),
            "target_digest": self.workspace.creative.document_digest(row),
            "request_digest": want,
            "source_snapshot": self._source_snapshot(detail),
        }
        updated = self.workspace.creative.update(
            nid, scope, actor, document_id, body.expected_version, value,
            reauthorize=guard, expected_digest=body.expected_digest_target, server_proof=proof)
        stored = next((item for item in self._proofs(updated)
                       if item.get("shot_id") == shot_id), proof)
        return {"replayed": False, "document_id": document_id, "shot_id": shot_id,
                "version": updated.get("version"),
                "digest": self.workspace.creative.document_digest(updated),
                "adoption": {k: v for k, v in stored.items() if k != "adopted_text"}}

    # ------------------------------------------------------------ helpers --
    @staticmethod
    def _source_snapshot(detail) -> list:
        """Binding targets the adopted revision declared, as the server resolved them.

        Recorded for traceability only. `INDEX_SUPPLIED` means the index contained the
        target; it is not an approval and not a write-time verification.
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
    def _request_digest(body, document_id, shot_id, actor, scope) -> str:
        """Request identity, bound to the actual actor, target, scope and request id."""
        return prompt.digest("|".join([
            str(actor), str(document_id), str(shot_id),
            prompt.digest(repr(sorted((scope or {}).items()))),
            body.family_id, body.asset_id, str(body.revision), body.expected_digest,
            str(body.expected_version), body.expected_digest_target, body.request_id]))
