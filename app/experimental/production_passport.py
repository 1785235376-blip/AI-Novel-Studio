"""Read-only unsigned sidecar projection over original production/asset owners.

No record is written, no adapter is resolved or dispatched, no signature is
claimed. Free text is represented by digests, never a best-effort secret scrub.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import zipfile

from .common import StaleSourceError, check_version
from .media import digest
from ..media_files import inspect_image

MAX_NODES = 100
MAX_DEPTH = 16
MAX_OUTPUT = 25 * 1024 * 1024
LIMITS = [
    "UNSIGNED_SIDECAR_NO_C2PA_CREDENTIAL",
    "HASH_EQUALITY_IS_NOT_AUTHOR_AUTHENTICATION",
    "REPLACING_BOTH_OUTPUT_AND_REPORT_IS_NOT_DETECTABLE_BY_THIS_UNSIGNED_BUNDLE",
    "TRACEABILITY_IS_NOT_LEGAL_COPYRIGHT_CERTIFICATION",
    "APPROVED_ORIGINAL_MEDIA_IMAGE_ONLY_NOT_FINISHED_FILM_OR_COMIC_CHAIN",
    "FULL_DIF12_NOT_ACCEPTED",
    "FREE_TEXT_IDENTITIES_LICENSE_TEXT_AND_PATHS_REDACTED_TO_DIGESTS",
    "CURRENT_AUTHORIZED_OWNER_SNAPSHOT_NOT_INDEPENDENT_ATTESTATION",
    "REVALIDATED_MULTI_READ_SNAPSHOT_NOT_ATOMIC_CROSS_OWNER_TRANSACTION",
    "AUTHORITY_CHECKED_BEFORE_RESPONSE_NO_PERSISTENT_ACCESS_GRANT",
]
_METADATA = {"id", "novel_id", "scope", "version", "created_by", "updated_by", "created_at", "updated_at", "history", "privacy_level", "manifest_digest"}
_ORIGINS = {"ORIGINAL_INPUT", "GENERATED_RESULT", "DERIVED_PROCESSING", "EXTERNAL_IMPORT", "MANUAL_EDIT"}


class _AuthorityChanged(ValueError):
    """Must never be downgraded to missing optional ancestor evidence."""


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise ValueError("PASSPORT_INVALID_DIGEST")
    return value


def _version(value):
    if type(value) is not int or not 1 <= value <= 2**53 - 1:
        raise ValueError("PASSPORT_INVALID_VERSION")
    return value


def _redacted(value):
    return {"state": "REDACTED", "digest": digest(value)} if value not in (None, "", {}) else {"state": "MISSING"}


def snapshot(service, nid, scope, rid, pid, version, guard):
    guard()
    manifest = service.get(nid, scope, service.MANIFESTS, rid)
    check_version(manifest, version)
    if digest({k: v for k, v in manifest.items() if k not in _METADATA}) != manifest.get("manifest_digest"):
        raise ValueError("PASSPORT_MANIFEST_INTEGRITY_FAILED")
    outputs = [o for o in manifest["outputs"] if o.get("proposal_id") == pid]
    if len(outputs) != 1:
        raise ValueError("PASSPORT_OUTPUT_NOT_IN_MANIFEST")
    output = outputs[0]
    task = service._task(nid, scope, manifest["task_id"])
    proposal = service.media.get(nid, scope, service.media.PROPOSALS, pid)
    if (task.get("status") != "SUCCEEDED" or task.get("version") != manifest["task_version"]
            or task.get("source_digest") != manifest["input_digest"] or pid not in task.get("proposal_ids", [])
            or proposal.get("task_id") != task["id"] or proposal.get("candidate_index") != output["candidate_index"]
            or proposal.get("source_digest") != manifest["input_digest"]
            or task.get("sources") != manifest["sources"] or proposal.get("sources") != manifest["sources"]
            or task.get("brief_snapshot", {}).get("asset_sources", {}) != manifest["asset_sources"]):
        raise StaleSourceError("PASSPORT_ORIGINAL_LINK_CHANGED")
    if (proposal.get("status") != "APPROVED" or not proposal.get("approved_by")
            or not proposal.get("approved_at") or not proposal.get("asset_id")):
        raise ValueError("PASSPORT_APPROVED_OUTPUT_REQUIRED")
    root = service._asset(nid, scope, proposal["asset_id"])
    legacy = root.get("parameters", {}).get("experimental_media_lineage", {})
    if (root.get("hidden") or root.get("secret") or root.get("_owner_actor_id")
            or root.get("source_job_id") != task["id"] or legacy.get("proposal_id") != pid
            or legacy.get("source_digest") != manifest["input_digest"]
            or root.get("approved_at") != proposal["approved_at"]
            or proposal.get("promotion_asset_id") != root["id"]):
        raise ValueError("PASSPORT_APPROVAL_ASSET_LINK_INVALID")
    encoded = proposal.get("content_base64")
    if not isinstance(encoded, str) or len(encoded) > 4 * ((MAX_OUTPUT + 2) // 3):
        raise ValueError("PASSPORT_OUTPUT_LIMIT")
    # Decode exactly the authorized snapshot whose encoded length was bounded.
    # media.preview() would reread and could decode a different, larger record.
    content = base64.b64decode(encoded, validate=True)
    if hashlib.sha256(content).hexdigest() != proposal.get("content_sha256"):
        raise ValueError("PASSPORT_PROPOSAL_INTEGRITY_FAILED")
    media_type = proposal.get("media", {}).get("media_type")
    if len(content) > MAX_OUTPUT:
        raise ValueError("PASSPORT_OUTPUT_LIMIT")
    actual = service.assets.content(root["id"], branch_id=scope.get("branch_id"), max_bytes=MAX_OUTPUT, guard=guard)
    measured = inspect_image(actual)
    checksum = hashlib.sha256(actual).hexdigest()
    if (actual != content or checksum != output["digest"] or checksum != root["sha256"]
            or checksum != proposal.get("promotion_asset_digest") or media_type != measured["media_type"]
            or output.get("media_type") != media_type):
        raise ValueError("PASSPORT_OUTPUT_INTEGRITY_FAILED")
    # Current source gates are checked without resolving an adapter or invoking
    # replay preflight (which may create a broker preview).
    service.media._current_brief(nid, scope, task)
    if service._privacy(nid, scope, task) != manifest["privacy_at_capture"]:
        raise StaleSourceError("PASSPORT_PRIVACY_CHANGED")
    seen, active, pins, nodes = {}, set(), [], []
    chapter_pins = {}
    incomplete = False

    def visit(aid, depth):
        nonlocal incomplete
        if depth > MAX_DEPTH or len(seen) >= MAX_NODES and aid not in seen:
            raise ValueError("PASSPORT_LINEAGE_LIMIT")
        if aid in active:
            raise ValueError("PASSPORT_LINEAGE_CYCLE")
        if aid in seen:
            return seen[aid]
        try:
            row = service._asset(nid, scope, aid)
            if row.get("hidden") or row.get("secret") or row.get("_owner_actor_id"):
                raise FileNotFoundError()
        except (FileNotFoundError, ValueError):
            incomplete = True
            return None  # No denied ID, digest, title, alias or historical hint.
        alias = f"asset-{len(seen) + 1}"
        seen[aid] = alias
        active.add(aid)
        pins.append(row)
        evidence = row.get("parameters", {}).get("asset_lineage_v2", {})
        if not isinstance(evidence, dict): evidence = {}
        parents = []
        for parent in row.get("source_asset_ids", []):
            ref = visit(parent, depth + 1)
            if ref:
                binding = evidence.get("parents", {}).get(parent)
                parents.append({"ref": ref, "recorded_binding": {"version": _version(binding["version"]), "sha256": _hash(binding["digest"])} if isinstance(binding, dict) else None})
        active.remove(aid)
        declaration = evidence.get("license")
        chapter_links = []
        for cid, binding in evidence.get("sources", {}).items():
            try: current = service._chapters(nid, scope, [cid])[cid]
            except (FileNotFoundError, ValueError):
                incomplete = True
                continue
            chapter_pins[cid] = current
            chapter_links.append({"version": _version(binding["version"]), "sha256": _hash(binding["digest"]),
                                  "state": "CURRENT" if current == binding else "STALE"})
        try:
            parent_bytes = service.assets.content(aid, branch_id=scope.get("branch_id"), max_bytes=MAX_OUTPUT, guard=guard)
            if hashlib.sha256(parent_bytes).hexdigest() != row["sha256"] or len(parent_bytes) != row["size"]:
                raise ValueError("PASSPORT_PARENT_CHANGED")
            integrity = "CONTENT_VERIFIED"
        except _AuthorityChanged:
            raise
        except (FileNotFoundError, ValueError):
            integrity = "CONTENT_UNAVAILABLE"
            incomplete = True
        nodes.append({"ref": alias, "version": _version(row["version"]), "sha256": _hash(row["sha256"]),
            "origin": evidence.get("origin") if evidence.get("origin") in _ORIGINS else "UNDECLARED",
            "operation": _redacted(evidence.get("operation")), "parents": parents,
            "chapter_bindings": chapter_links, "integrity": integrity,
            "license_declaration": _redacted(declaration), "license_verification": "AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION",
            "declaration_history_versions": [_version(h["asset_version"]) for h in evidence.get("history", []) if isinstance(h, dict) and "asset_version" in h]})
        return alias

    visit(root["id"], 0)
    chapters = []
    for cid, binding in manifest["sources"].items():
        try: current = service._chapters(nid, scope, [cid])[cid]
        except (FileNotFoundError, ValueError):
            incomplete = True
            continue
        chapter_pins[cid] = current
        chapters.append({"ref": f"chapter-{len(chapters) + 1}", "version": _version(binding["version"]),
                         "sha256": _hash(binding["digest"]), "state": "CURRENT" if current == binding else "STALE"})
    report = {"schema": "production-passport-unsigned-v1", "profile": "REDACTED_APPROVED_MEDIA_IMAGE",
        "project": {"ref": "project-1", "identity": "WITHHELD"},
        "manifest_digest": _hash(manifest["manifest_digest"]), "input_digest": _hash(manifest["input_digest"]),
        "output": {"path": "output." + measured["extension"], "sha256": checksum, "size": len(actual),
                   "media_type": measured["media_type"], "asset_ref": "asset-1", "asset_version": _version(root["version"])},
        "provider": _redacted(root.get("provider_id")), "model": _redacted(root.get("model_id")),
        "model_operation": _redacted(manifest.get("operation")),
        "approval": {"state": "APPROVED", "proposal_version": _version(proposal["version"]),
                     "actor": _redacted(proposal["approved_by"]), "approved_at": _redacted(proposal["approved_at"])},
        "lineage": {"assets": nodes, "chapters": chapters, "coverage": "INCOMPLETE" if incomplete else "RECORDED_AUTHORIZED_LINKS_ONLY"},
        "credential": {"state": "UNSIGNED_SIDECAR", "c2pa": False, "signature": None},
        "limitations": LIMITS}
    # Fingerprint stays internal; it includes full original versions and catches
    # concurrent declaration/review edits even if redacted fields look unchanged.
    fingerprint = digest([manifest, task, proposal, pins, chapters, nodes])
    guard()
    def assert_current():
        # Match original export download patterns: re-read owner identity after
        # materializing bytes, rather than treating a copied snapshot as a lease.
        # No new lock order or write transaction is introduced for this GET.
        guard()
        if (service.get(nid, scope, service.MANIFESTS, rid) != manifest
                or service._task(nid, scope, task["id"]) != task):
            raise StaleSourceError("PASSPORT_EVIDENCE_CHANGED")
        for pinned in pins:
            if service._asset(nid, scope, pinned["id"]) != pinned:
                raise StaleSourceError("PASSPORT_EVIDENCE_CHANGED")
        for cid, binding in chapter_pins.items():
            if service._chapters(nid, scope, [cid])[cid] != binding:
                raise StaleSourceError("PASSPORT_EVIDENCE_CHANGED")
        service.media._current_brief(nid, scope, task)
        if service._privacy(nid, scope, task) != manifest["privacy_at_capture"]:
            raise StaleSourceError("PASSPORT_PRIVACY_CHANGED")
        # Eligibility owners are checked LAST, after all content and ancestry
        # reads. Reject revoked approval, hidden/private root, and new versions.
        if (service.media.get(nid, scope, service.media.PROPOSALS, pid) != proposal
                or service._asset(nid, scope, root["id"]) != root):
            raise StaleSourceError("PASSPORT_EVIDENCE_CHANGED")
        guard()
    return report, actual, fingerprint, assert_current


def serialize(report, content):
    encoded = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    if len(encoded) > 1024 * 1024:
        raise ValueError("PASSPORT_REPORT_LIMIT")
    human = ("Production Passport | UNSIGNED SIDECAR\n\n"
        "This is an unsigned local evidence report, not a C2PA credential.\n"
        "SHA-256 verifies output equality only, not authorship or report authenticity.\n"
        "Replacing both the report and output is outside this check.\n"
        "Traceability is not legal copyright certification. Full DIF-12 is not accepted.\n"
        "Free text is withheld; REDACTED and MISSING are not proof of license rights.\n\n"
        "Machine report (identical evidence fields):\n" + encoded.decode("utf-8") + "\n").encode("utf-8")
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in ((report["output"]["path"], content), ("passport.json", encoded), ("passport.txt", human)):
            archive.writestr(zipfile.ZipInfo(name), data)
    return target.getvalue()


def export_passport(service, nid, scope, rid, pid, expected_version, guard):
    original_guard = guard
    def guard():
        try:
            original_guard()
        except (ValueError, FileNotFoundError) as exc:
            raise _AuthorityChanged("PASSPORT_AUTHORITY_CHANGED") from exc
    first, content, pin, _ = snapshot(service, nid, scope, rid, pid, expected_version, guard)
    archive = serialize(first, content)
    second, current, current_pin, assert_current = snapshot(service, nid, scope, rid, pid, expected_version, guard)
    if pin != current_pin or first != second or content != current:
        raise StaleSourceError("PASSPORT_EVIDENCE_CHANGED")
    assert_current()
    guard()
    return archive
