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
from ..experimental.store import canonical
from . import prompt_asset as prompt
from .bible_workspace import BibleWorkspaceService
from .director_intent import project_shot_cards
from .prompt_workspace import MAX_PROMPT_SCAN
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

    def __init__(self, workspace, prompts, phase_inputs=None):
        self.workspace, self.prompts = workspace, prompts
        # Injected when the host already owns the project's cross-module transaction
        # mechanism (ProductionExecutionService.timeline_inputs); otherwise built lazily
        # over the same workspace, never as a second transaction owner.
        self._inputs = phase_inputs

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
        value = self.workspace.creative.get(nid, scope, document_id)
        # `document` is the CreativeDocument for the WHOLE function. The per-revision mask
        # lookup below must never bind this name.
        document = self._document(nid, scope, actor, document_id)
        current = {item.get("id"): item for item in self._shots(document) if isinstance(item, dict)}
        version = document.get("version")
        entries = []
        for proof in self._proofs(document):
            entry = dict(proof)
            entry["newer_revision_available"] = False
            entry["source_readable"] = True
            # A proof is CURRENT for its shot only while the document is still exactly the
            # revision the adoption produced. Content equality alone is not enough: a user can
            # edit the shot and type the same text back, which advances the document version
            # and must NOT restore a claim that the shot still carries that adoption.
            shot = current.get(proof.get("shot_id")) or {}
            held = shot.get("frame_prompt")
            entry["still_applied"] = bool(
                proof.get("result_version") is not None
                and version == proof.get("result_version")
                and isinstance(held, str)
                and prompt.digest(held.encode("utf-8")) == proof.get("digest"))
            # The proof records a digest, never the body: no plaintext is handed back here.
            entry.pop("adopted_text", None)
            try:
                detail = self.prompts.detail(nid, scope, proof["family_id"], actor)
                entry["newer_revision_available"] = detail["revision"] > proof["revision"]
                body = self.prompts.revision_body(nid, scope, proof["family_id"],
                                                  proof["asset_id"], actor)
                # The mask is PER REVISION and lives in the family projection's `versions[]`
                # rows (`redacted`, `available`, per asset_id). It is NOT in the revision-body
                # contract, which carries only state/available/verified/read_complete — reading
                # it from the body silently yielded None and let every masked revision look
                # displayable.
                version_row = next((item for item in (detail.get("versions") or [])
                                    if isinstance(item, dict)
                                    and item.get("asset_id") == proof.get("asset_id")), None)
                if version_row is None or version_row.get("revision") != proof.get("revision"):
                    # This revision's state cannot be confirmed: fail closed rather than
                    # assume it is displayable.
                    entry["source_state"] = "UNKNOWN"
                    entry["source_readable"] = False
                else:
                    entry["source_state"] = "KNOWN"
                    entry["source_redacted"] = version_row.get("redacted") is True
                    entry["source_available"] = version_row.get("available") is not False
                    entry["source_readable"] = bool(
                        version_row.get("redacted") is not True
                        and version_row.get("available") is not False
                        and body["state"] == prompt.BODY_COMPLETE and body["verified"]
                        and detail.get("history_complete") and detail.get("read_complete"))
            except (FileNotFoundError, ValueError, PermissionError, KeyError):
                entry["source_state"] = "UNKNOWN"
                entry["source_readable"] = False
            entries.append(entry)
        return {"contract": PROOF_CONTRACT, "document_id": document_id,
                "version": version,
                # Definitely the DOCUMENT's digest: `document`, never a version row.
                "digest": self.workspace.creative.document_digest(document),
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
        # `detail` describes the head, and only the head is adoptable, so this is the same
        # revision; kept explicit so the check cannot silently start describing another one.

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
            # The digest IS the record. The body is deliberately NOT stored again: keeping a
            # second permanent copy of the prompt text inside the creative document would
            # duplicate private content into another owner's history and would defeat the
            # source's own redaction and deletion semantics.
            "adopted_by": actor, "adopted_at": now(), "request_id": body.request_id,
            "target_version": row.get("version"),
            # The revision this adoption produced. `still_applied` compares the document's
            # current version against it, so an edit-and-revert cannot resurrect the claim.
            "result_version": row.get("version") + 1,
            "target_digest": self.workspace.creative.document_digest(row),
            "request_digest": want,
            "source_snapshot": self._source_snapshot(detail),
        }
        # `sink` is filled by the OWNER, inside the commit transaction, with the exact proof
        # it stored. Searching the returned row afterwards could fail only AFTER the write had
        # committed, which would report failure for a version that really exists — and could
        # report a proof that does not describe this operation. The owner's return value makes
        # proof and commit consistent by construction, so there is no post-commit search.
        sink: dict = {}
        updated = self.workspace.creative.update(
            nid, scope, actor, document_id, body.expected_version, value,
            reauthorize=guard, expected_digest=body.expected_digest_target, server_proof=proof,
            proof_sink=sink)
        stored = sink.get("proof")
        if stored is None:
            # Only reachable if the owner committed no proof at all: no version was created
            # carrying this request, so refusing is accurate rather than a false failure.
            raise ValueError("PROMPT_ADOPTION_PROOF_NOT_COMMITTED")
        return {"replayed": False, "document_id": document_id, "shot_id": shot_id,
                "version": updated.get("version"),
                "digest": self.workspace.creative.document_digest(updated),
                "adoption": {k: v for k, v in stored.items() if k != "adopted_text"}}

    # ------------------------------------------------------------- atomic --
    def _phase_inputs(self):
        """The project's OWN cross-module transaction mechanism, not a new one.

        `GraphAssetInputs.phase(writable=True)` already acquires, in the established order,
        the project-owner transaction and then the asset lease, and commits with
        `raw.clear(); raw.update(state)` while both are still held. `ProductionExecutionService`
        builds one as `timeline_inputs`; the host object here supplies the same three
        attributes that `phase()` actually uses.
        """
        if self._inputs is None:
            from .graph_asset_inputs import GraphAssetInputs
            creative = self.workspace.creative

            class _PhaseHost:
                pass

            host = _PhaseHost()
            host.workspace = self.workspace
            host.store = self.workspace.store
            host._capacity = staticmethod(creative.assert_capacity)
            self._inputs = GraphAssetInputs(host)
        return self._inputs

    def adopt_atomic(self, nid, scope, actor, document_id, shot_id, body, guard=lambda: None):
        """Adopt into one shot inside the cross-module atomic boundary.

        Everything the unverified path did OUTSIDE a transaction now happens inside one: the
        permission and project identity, the source asset read (under the lease the phase
        already holds, so `lease=False` — `project_scope` refuses to nest), the target document
        and shot, the idempotency record, the version and digest CAS, the write itself, and the
        incarnation re-check. Success is reported only after the phase has exited normally and
        the raw owner has committed.
        """
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("PROMPT_ADOPTION_ACTOR_REQUIRED")
        if getattr(body, "shot_id", shot_id) != shot_id:
            raise ValueError("PROMPT_ADOPTION_SHOT_ID_MISMATCH")
        self.workspace.store.key(nid, scope)
        self.workspace.novels.get(nid)
        creative = self.workspace.creative
        want = self._request_digest(body, document_id, shot_id, actor, scope)
        settled = {}

        with self._phase_inputs().phase(nid, scope, actor, guard, writable=True) as state:
            collection = state["collections"].get(creative.COLLECTION, {})
            row = collection.get(document_id)
            if row is None or prompt._text(row.get("status")) == "ARCHIVED":
                raise FileNotFoundError(document_id)
            if prompt._text(row.get("mode")) != "STORYBOARD":
                raise ValueError("PROMPT_ADOPTION_TARGET_NOT_STORYBOARD")
            if self._shot(row, shot_id) is None:
                raise FileNotFoundError(shot_id)

            # Idempotency is decided from the CURRENT transaction state, not a pre-transaction
            # snapshot, so two concurrent requests cannot both see "not settled yet".
            for proof in self._proofs(row):
                if proof.get("request_id") != body.request_id:
                    continue
                if (proof.get("request_digest") != want
                        or proof.get("document_id") != document_id
                        or proof.get("shot_id") != shot_id):
                    raise ValueError("PROMPT_ADOPTION_REQUEST_REUSED")
                settled = {"replayed": True, "document_id": document_id, "shot_id": shot_id,
                           "version": row.get("version"),
                           "digest": creative.document_digest(row), "adoption": proof}
                break
            if not settled:
                # Source verification shares the ordinary read rules EXACTLY: same methods,
                # same actor, same checks — only the lease acquisition is skipped because the
                # phase already holds it. No payload read happens outside the owner's lease.
                # Read the source under the lease the phase ALREADY holds. No aggregate
                # bible projection is entered: it would re-acquire the asset scope and
                # raise ASSET_PROJECT_SCOPE_NESTED. Binding owners are read below without
                # opening another lease. The same PURE projection the real
                # `detail()` uses is applied to the same rows, so head identity, approval and
                # history completeness are decided by the owner's own functions rather than a
                # reimplementation.
                rows, bodies, coverage = self.prompts._read_prompts(
                    nid, scope, actor, limit=MAX_PROMPT_SCAN, include_deleted=True, lease=False)
                detail = prompt.project_prompt_detail(
                    body.family_id, rows, bible=None, asset_text=bodies,
                    read_complete=not coverage.get("truncated", False))

                target = next((item for item in rows if str(item.get("id")) == body.asset_id), None)
                if target is None:
                    raise FileNotFoundError(body.asset_id)
                if prompt.family_of(target) != body.family_id:
                    raise ValueError("PROMPT_ADOPTION_FAMILY_MISMATCH")
                if prompt.revision_of(target) != body.revision:
                    raise ValueError("PROMPT_ADOPTION_REVISION_MISMATCH")
                if target.get("deleted_at"):
                    raise ValueError("PROMPT_ADOPTION_SOURCE_DELETED")
                if prompt._text(target.get("kind")) != prompt.PROMPT_KIND:
                    raise ValueError("PROMPT_ADOPTION_SOURCE_NOT_PROMPT")
                if prompt.authoring_state(target) != "ACTIVE":
                    raise ValueError("PROMPT_ADOPTION_SOURCE_NOT_ACTIVE")

                # The mask lives in the ASSET PAYLOAD. `validate_payload` returns ONLY
                # {"ok", "reason"} -- it does not echo the payload -- so asking it for
                # `redacted` always yielded None and this check never rejected anything. The
                # two steps are now separate: validate the payload strictly, then read the
                # flag from the PAYLOAD itself. A payload that fails validation is refused
                # rather than treated as unmasked.
                payload = prompt.prompt_payload(target)
                validation = prompt.validate_payload(payload)
                if validation.get("ok") is not True:
                    raise ValueError("PROMPT_ADOPTION_SOURCE_METADATA_"
                                     + str(validation.get("reason") or "INVALID"))
                if payload.get("redacted") is True:
                    raise ValueError("PROMPT_ADOPTION_SOURCE_REDACTED")

                # Approval comes from the owner's own recorded marker, never the caller.
                if not target.get("approved_at"):
                    raise ValueError("PROMPT_ADOPTION_NOT_APPROVED")
                if detail["head_asset_id"] != body.asset_id or detail["revision"] != body.revision:
                    raise ValueError("PROMPT_ADOPTION_REVISION_NOT_HEAD")
                if not detail.get("history_complete"):
                    raise ValueError("PROMPT_ADOPTION_SOURCE_INCOMPLETE")
                if not detail.get("read_complete") or coverage.get("truncated", False):
                    # A truncated scan is not a complete history.
                    raise ValueError("PROMPT_ADOPTION_SOURCE_INCOMPLETE")

                body_read = dict(bodies.get(body.asset_id) or {})
                if body_read.get("state") != prompt.BODY_COMPLETE:
                    raise ValueError(f"PROMPT_ADOPTION_SOURCE_{body_read.get('state', 'UNAVAILABLE')}")
                if not body_read.get("decodable") or not body_read.get("body_validated"):
                    raise ValueError("PROMPT_ADOPTION_SOURCE_UNREADABLE")
                if body_read.get("truncated"):
                    raise ValueError("PROMPT_ADOPTION_SOURCE_TRUNCATED")
                # Re-verify the ORIGINAL bytes against the digest the owner recorded, exactly
                # as the revision-body reader does.
                recorded = prompt._text(target.get("sha256"))
                if (not recorded or body_read.get("digest") != recorded
                        or body_read.get("digest_of") != prompt.DIGEST_OF_ORIGINAL):
                    raise ValueError("PROMPT_ADOPTION_SOURCE_UNVERIFIED")
                text = body_read.get("value")
                if not isinstance(text, str):
                    raise ValueError("PROMPT_ADOPTION_SOURCE_UNREADABLE")
                if body.expected_digest != body_read["digest"]:
                    raise ValueError("PROMPT_ADOPTION_DIGEST_MISMATCH")
                if len(text) > FRAME_PROMPT_MAX:
                    # Refuse; never truncate into something that looks like a full adoption.
                    raise ValueError("PROMPT_ADOPTION_TOO_LONG")

                bindings = self._write_time_bindings(nid, scope, actor, row, payload, guard)
                shot = self._shot(row, shot_id)
                value = {key: copy.deepcopy(row[key]) for key in _DOCUMENT_FIELDS if key in row}
                shots = [copy.deepcopy(item) for item in self._shots(row)]
                for item in shots:
                    if isinstance(item, dict) and item.get("id") == shot_id:
                        item["frame_prompt"] = text
                value["shots"] = shots
                value.pop("prompt_adoptions", None)
                proof = {
                    "contract": PROOF_CONTRACT, "document_id": document_id, "shot_id": shot_id,
                    "field": "frame_prompt", "family_id": body.family_id,
                    "asset_id": body.asset_id, "revision": body.revision,
                    "digest": body_read["digest"], "digest_of": body_read["digest_of"],
                    "adopted_by": actor, "adopted_at": now(), "request_id": body.request_id,
                    "target_version": row.get("version"), "target_digest": creative.document_digest(row),
                    # The revision this adoption produces. The read projection needs it to
                    # decide `still_applied`, so it must be the REAL committed version.
                    "result_version": row.get("version") + 1,
                    "request_digest": want,
                    # These are observations at this commit, not review markers or render
                    # authority. Historical/replayed proofs never claim targets are current.
                    "source_snapshot": bindings,
                    "source_binding_contract": "prompt-adoption-bindings/1",
                    "source_bindings_verified": True,
                }
                updated, committed = creative.revise_in_state(
                    nid, scope, actor, state, document_id, body.expected_version, value,
                    reauthorize=guard, expected_digest=body.expected_digest_target,
                    server_proof=proof)
                if committed is None:
                    raise ValueError("PROMPT_ADOPTION_PROOF_NOT_COMMITTED")
                if committed.get("result_version") != updated.get("version"):
                    # The proof must describe the version actually committed.
                    raise ValueError("PROMPT_ADOPTION_RESULT_VERSION_MISMATCH")
                result = {"replayed": False, "document_id": document_id, "shot_id": shot_id,
                          "version": updated.get("version"),
                          "digest": creative.document_digest(updated),
                          "adoption": {k: v for k, v in committed.items()
                                       if k != "adopted_text"}}
            else:
                result = settled
                shot = self._shot(row, shot_id)

        # The phase has exited normally, so the incarnations matched and the raw owner has
        # committed. Only NOW is success reported.
        result["committed"] = True
        result["generated_at"] = now()
        return result

    # ------------------------------------------------------------ helpers --
    def _write_time_bindings(self, nid, scope, actor, document, payload, guard):
        """Resolve declared bindings through their owners inside the held phase.

        The phase holds scope -> assets -> project through commit. File story-record
        writes use that project's lifecycle lock; PostgreSQL story-record writers take
        the same novel FOR UPDATE, conflicting with the held owner KEY SHARE. No bible
        aggregate, second transaction, asset scope, or replacement owner is entered.

        Canonical shot bindings use the existing document_id:number projection.
        Raw shot IDs remain compatible only within this explicit target document.
        Existence here is neither approval nor permission to execute a model.
        """
        if not self._phase_inputs().in_phase(nid, scope, actor):
            raise ValueError("PROMPT_ADOPTION_BINDING_PHASE_REQUIRED")
        identity = self.workspace.store.incarnation(nid)
        snapshots = []

        def snapshot(kind, identifier, owner, value, **extra):
            snapshots.append({"kind": kind, "id": identifier, "owner": owner,
                "resolution": prompt.KNOWN, "verification": "WRITE_TIME_OWNER_LEASE",
                "project_incarnation": identity, "digest": prompt.digest(canonical(value)), **extra})

        def unavailable():
            # Do not disclose which private/foreign target failed or echo its content.
            raise ValueError("PROMPT_ADOPTION_BINDING_UNAVAILABLE")

        for field, dataset, kind in (("character_ids", "characters", "CHARACTER"),
                                     ("scene_ids", "locations", "SCENE")):
            declared = payload[field]
            if not declared:
                continue
            guard()
            rows = BibleWorkspaceService._scoped(self.workspace.novels.data_set(nid, dataset), scope)
            for identifier in declared:
                matches = [item for item in rows if item.get("id") == identifier]
                if len(matches) != 1:
                    unavailable()
                value = matches[0]
                if (value.get("deleted_at") or value.get("is_archived") is True
                        or value.get("status") in {"ARCHIVED", "DELETED"}):
                    unavailable()
                snapshot(kind, identifier, "NovelService." + dataset, value)
            guard()

        cards = project_shot_cards(document) if payload["shot_ids"] else []
        shot_index = prompt.shot_index([{"document_id": document["id"], "cards": cards}])["entries"]
        for identifier in payload["shot_ids"]:
            guard()
            entry = shot_index.get(identifier)
            actual_id = entry["shot_id"] if entry is not None else identifier
            matches = [item for item in self._shots(document)
                       if isinstance(item, dict) and item.get("id") == actual_id]
            if len(matches) != 1:
                unavailable()
            shot = matches[0]
            key = f"{document['id']}:{shot.get('number')}"
            # shot_index is the established pure projection, but its dict cannot
            # represent duplicate numbers. Refuse an ambiguous source rather than
            # trusting whichever card happened to overwrite the same key last.
            if (type(shot.get("number")) is not int or shot["number"] < 1
                    or sum(f"{document['id']}:{card.get('number')}" == key for card in cards) != 1
                    or any(item.get("id") == identifier and item.get("id") != actual_id
                           for item in self._shots(document) if isinstance(item, dict))):
                unavailable()
            snapshot("SHOT", identifier, "CreativeService", matches[0],
                     document_id=document["id"], version=document["version"],
                     document_digest=self.workspace.creative.document_digest(document),
                     shot_key=key, shot_id=actual_id)

        # Preserve each declaration's role even when an asset is both reference/output.
        for field in ("reference_asset_ids", "output_asset_ids"):
            for identifier in payload[field]:
                guard()
                try:
                    value = self.workspace.assets.get(identifier, branch_id=scope.get("branch_id"),
                                                      actor_id=actor)
                    if (value.get("novel_id") != nid or value.get("branch_id") != scope.get("branch_id")
                            or type(value.get("version")) is not int or not 1 <= value["version"] <= 2**53 - 1
                            or not isinstance(value.get("kind"), str) or not value["kind"]):
                        unavailable()
                    # The original owner's read verifies the original bytes as well as
                    # actor, branch and incarnation; a metadata-only hit is insufficient.
                    self.workspace.assets.content(identifier, branch_id=scope.get("branch_id"),
                                                  actor_id=actor)
                except (FileNotFoundError, PermissionError, ValueError):
                    unavailable()
                snapshot("ASSET", identifier, "AssetLibraryService", {
                    "id": value["id"], "version": value["version"], "sha256": value["sha256"],
                    "kind": value["kind"]}, role=field, version=value["version"],
                    asset_digest=value["sha256"], asset_kind=value["kind"])
                guard()
        guard()
        return snapshots

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
