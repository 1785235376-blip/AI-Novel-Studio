"""Prompt Intelligence: a Prompt Asset is an existing asset, projected as a library.

Why this module exists
----------------------
Round 3 turns prompts from scattered text into a reusable, versioned, bindable
asset. Round 3 §3 forbids a second asset, version or review system, and
`ROUND3_PROMPT_SOURCE_AUDIT.md` established how to reuse the existing one by reading
`app/services/asset_library_service.py` rather than assuming:

| Prompt Asset property | Existing owner field that carries it |
| --- | --- |
| identity | the asset id |
| prompt text | the asset's immutable bytes, `kind="prompt"` |
| negative prompt, model, parameters, seed, purpose, origin | `parameters` (allow-listed dict) |
| character / scene binding | the already allow-listed `character_id` / `scene_id` |
| reference / output assets | `source_asset_ids` (references, never copies) |
| version | the asset `version` + `expected_version` CAS |
| version chain | `annotate_lineage` history |
| review | `promote_owned` |

This module adds no owner, no collection and no database. It is a pure projection
plus payload/body contracts.

R3-R read-contract fixes (2026-10-15)
------------------------------------
* `read_prompt_body` separates **full value / short preview / redacted digest**, and
  reports `COMPLETE` / `TRUNCATED` / `UNDECODABLE` explicitly. The digest always
  describes the **original bytes**, never a truncated preview.
* `validate_payload` is a full strict schema check (exact keys; exact `bool`; exact
  `int` — `True` is not a business integer and `'false'` is not `False`).
* `history_complete` is derived from **actual coverage** plus chain anomalies, never a
  constant. Duplicate revisions, broken/cross-family predecessors and unavailable
  revisions are reported instead of being sorted into a fake linear history.
* `shot_index` builds shot identity from real shot/document structures, **independent
  of whether a character appears in the shot**, scoped per document so two documents'
  shot number 1 cannot be confused.
* `project_prompt_context` adapts the **real** `project_shot_cards()` output (which
  returns top-level fields, not a `dimensions` list) and carries document/shot
  identity, preserving `DOCUMENT_AUTHORED` vs `PER_SHOT_MEASURED`.
* Redaction covers change note and reason as well as text, and grants no permission.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping

PROMPT_LIBRARY_CONTRACT = "studio-prompt-library/1"
PROMPT_DETAIL_CONTRACT = "studio-prompt-detail/1"
PROMPT_CONTEXT_CONTRACT = "studio-prompt-context/1"
SCHEMA_VERSION = 1

PROMPT_KIND = "prompt"
PAYLOAD_KEY = "prompt"
PAYLOAD_CONTRACT = "prompt-asset/1"

UNKNOWN = "UNKNOWN"
KNOWN = "KNOWN"

PURPOSES: tuple[str, ...] = ("IMAGE", "VIDEO", "AUDIO", "TEXT")
ORIGINS: tuple[str, ...] = ("MANUAL", "AI_GENERATED", "IMPORTED")
BINDING_KINDS: tuple[str, ...] = ("CHARACTER", "SCENE", "SHOT", "ASSET")

PROMPT_FIELDS: tuple[str, ...] = (
    "text", "negative_prompt", "model_reference", "parameters", "seed",
    "reference_assets", "output_assets", "purpose", "origin", "binding", "version",
)

PROMPT_FIELD_LABELS: dict[str, str] = {
    "text": "提示词", "negative_prompt": "负向提示词", "model_reference": "模型引用",
    "parameters": "参数", "seed": "种子", "reference_assets": "参考素材",
    "output_assets": "产出素材", "purpose": "用途", "origin": "来源",
    "binding": "绑定", "version": "版本",
}

BINDING_LABELS: dict[str, str] = {
    "CHARACTER": "角色", "SCENE": "场景", "SHOT": "镜头", "ASSET": "素材",
}

#: The payload's exact key set. Anything else is a contract violation, not a hint.
PAYLOAD_REQUIRED_KEYS: tuple[str, ...] = (
    "contract", "family_id", "revision", "purpose", "origin", "negative_prompt",
    "model_reference", "parameters", "seed", "reference_asset_ids", "output_asset_ids",
    "character_ids", "scene_ids", "shot_ids", "change_note", "change_reason", "redacted",
)
PAYLOAD_OPTIONAL_KEYS: tuple[str, ...] = ("previous_asset_id", "adopted_from", "request_id", "state")

#: Authoring states. A revision that lost a concurrent race is `CONFLICTED`: its content
#: is preserved and reported, but it is never presented as a valid revision.
STATE_ACTIVE = "ACTIVE"
STATE_CONFLICTED = "CONFLICTED"

MAX_TEXT = 20000
MAX_IDENTIFIER = 240
MAX_IDS = 100

#: Body read states. `COMPLETE` is the only one that may be presented as the whole text.
BODY_COMPLETE = "COMPLETE"
BODY_TRUNCATED = "TRUNCATED"
BODY_UNDECODABLE = "UNDECODABLE"

#: The digest always describes the original bytes, never a preview.
DIGEST_OF_ORIGINAL = "ORIGINAL_BYTES"

#: Anomalies that make a family's history provably incomplete.
BLOCKING_ANOMALIES = frozenset({
    "DUPLICATE_REVISION", "BROKEN_PREDECESSOR", "CROSS_FAMILY_LINK",
    "REVISION_UNAVAILABLE", "REVISION_GAP",
})


def digest(value: Any) -> str:
    """SHA-256 of a text or bytes value. Bytes are hashed as-is."""
    if isinstance(value, (bytes, bytearray)):
        return hashlib.sha256(bytes(value)).hexdigest()
    text = value if isinstance(value, str) else str(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _rows(value: Iterable[Any] | None) -> list[Mapping[str, Any]]:
    if value is None:
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return str(value).strip()


def _clean(value: Any) -> str:
    """Public alias of `_text`, for callers outside this module."""
    return _text(value)


def _identifiers(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _is_exact_bool(value: Any) -> bool:
    return type(value) is bool


def _is_business_int(value: Any) -> bool:
    """`True`/`False` are `int` in Python; a business integer must not be a bool."""
    return type(value) is int


# ------------------------------------------------------- body read contract --

def _decode_chunk(chunk: bytes, *, allow_partial_tail: bool) -> tuple[str | None, bool]:
    """Decode a byte chunk strictly; optionally tolerate one unfinished trailing codepoint.

    §3.1 fix: the previous version tolerated *any* short trailing ``UnicodeDecodeError``
    regardless of whether the read was truncated, so a genuinely invalid body such as
    ``b"OK\\xff"`` decoded to ``"OK"`` and was reported ``COMPLETE``. Only a real preview
    boundary may drop bytes, and only when the error is an unfinished codepoint
    (``unexpected end of data``) rather than invalid start/continuation bytes.
    """
    try:
        return chunk.decode("utf-8"), True
    except UnicodeDecodeError as exc:
        if (allow_partial_tail and exc.reason == "unexpected end of data"
                and exc.end == len(chunk) and len(chunk) - exc.start < 4):
            try:
                return chunk[:exc.start].decode("utf-8"), True
            except UnicodeDecodeError:
                return None, False
        return None, False


def read_prompt_body(raw: Any, *, limit: int) -> dict[str, Any]:
    """Read a prompt body within a safe cap, stating exactly what was obtained.

    Returns:
      state              `COMPLETE` | `TRUNCATED` | `UNDECODABLE`
      value              exact text (`COMPLETE`), a valid-UTF-8 preview (`TRUNCATED`),
                         or `None` (`UNDECODABLE`)
      truncated          bool
      decodable          bool — the returned `value` is valid UTF-8
      **body_validated** bool — the **whole original body** was decoded and validated.
                         Only `COMPLETE` can claim this; a truncated read must not
                         promise that its unread tail is valid UTF-8.
      **tail_unverified** bool — bytes exist that were neither returned nor validated.
      original_length    byte length of the original body
      digest             SHA-256 of the **original bytes**
      digest_of          `ORIGINAL_BYTES`
      fetch              how to obtain the whole body
    """
    if not isinstance(raw, (bytes, bytearray)):
        raise ValueError("PROMPT_BODY_INVALID")
    if not _is_business_int(limit) or limit < 0:
        raise ValueError("PROMPT_BODY_LIMIT_INVALID")
    data = bytes(raw)
    total = len(data)
    truncated = total > limit
    # Only a truncated read may have its unfinished trailing codepoint dropped.
    text, decodable = _decode_chunk(data if not truncated else data[:limit],
                                    allow_partial_tail=truncated)
    if not decodable:
        state, value = BODY_UNDECODABLE, None
    elif truncated:
        state, value = BODY_TRUNCATED, text
    else:
        state, value = BODY_COMPLETE, text
    return {
        "state": state,
        "value": value,
        "truncated": truncated,
        "decodable": decodable,
        "body_validated": state == BODY_COMPLETE,
        "tail_unverified": truncated,
        "original_length": total,
        "preview_length": 0 if value is None else len(value.encode("utf-8")),
        "limit": limit,
        "digest": digest(data),
        "digest_of": DIGEST_OF_ORIGINAL,
        "fetch": "ASSET_BYTES" if state != BODY_COMPLETE else "INCLUDED",
    }


# ------------------------------------------------------------- the payload --

def validate_payload(payload: Any) -> dict[str, Any]:
    """Strict schema validation of one `parameters.prompt` payload.

    Nothing here is a truthiness check: `'false'` is not `False`, and `True` is not a
    business integer. Unknown keys are rejected rather than ignored.
    """
    def bad(reason: str) -> dict[str, Any]:
        return {"ok": False, "reason": reason}

    if not isinstance(payload, Mapping):
        return bad("PROMPT_PAYLOAD_NOT_OBJECT")
    # Contract first: it is the most informative reason for an artefact that is not a
    # prompt payload at all, and it is what a caller can act on.
    if payload.get("contract") != PAYLOAD_CONTRACT:
        return bad("PROMPT_PAYLOAD_CONTRACT_INVALID")
    keys = set(payload)
    if not set(PAYLOAD_REQUIRED_KEYS) <= keys:
        return bad("PROMPT_PAYLOAD_FIELD_MISSING")
    if keys - set(PAYLOAD_REQUIRED_KEYS) - set(PAYLOAD_OPTIONAL_KEYS):
        return bad("PROMPT_PAYLOAD_UNKNOWN_KEY")
    family = payload.get("family_id")
    if not isinstance(family, str) or not family.strip() or len(family) > MAX_IDENTIFIER:
        return bad("PROMPT_PAYLOAD_FAMILY_INVALID")
    if not _is_business_int(payload.get("revision")) or payload["revision"] < 1:
        return bad("PROMPT_PAYLOAD_REVISION_INVALID")
    if payload.get("purpose") not in PURPOSES:
        return bad("PROMPT_PAYLOAD_PURPOSE_INVALID")
    if payload.get("origin") not in ORIGINS:
        return bad("PROMPT_PAYLOAD_ORIGIN_INVALID")
    for field in ("negative_prompt", "model_reference", "change_note", "change_reason"):
        value = payload.get(field)
        if not isinstance(value, str) or len(value) > MAX_TEXT:
            return bad("PROMPT_PAYLOAD_TYPE_INVALID")
    if not isinstance(payload.get("parameters"), Mapping):
        return bad("PROMPT_PAYLOAD_TYPE_INVALID")
    seed = payload.get("seed")
    if seed is not None and (not _is_business_int(seed) or seed < 0):
        return bad("PROMPT_PAYLOAD_SEED_INVALID")
    for field in ("reference_asset_ids", "output_asset_ids", "character_ids", "scene_ids", "shot_ids"):
        value = payload.get(field)
        if not isinstance(value, list) or len(value) > MAX_IDS:
            return bad("PROMPT_PAYLOAD_TYPE_INVALID")
        if any(not isinstance(item, str) or not item.strip() or len(item) > MAX_IDENTIFIER for item in value):
            return bad("PROMPT_PAYLOAD_ID_INVALID")
    if not _is_exact_bool(payload.get("redacted")):
        return bad("PROMPT_PAYLOAD_TYPE_INVALID")
    if "previous_asset_id" in payload:
        previous = payload["previous_asset_id"]
        if not isinstance(previous, str) or not previous.strip() or len(previous) > MAX_IDENTIFIER:
            return bad("PROMPT_PAYLOAD_ID_INVALID")
    if "adopted_from" in payload:
        adopted = payload["adopted_from"]
        if not isinstance(adopted, Mapping) or set(adopted) != {"owner", "field", "digest"}:
            return bad("PROMPT_PAYLOAD_ADOPTION_INVALID")
        if any(not isinstance(value, str) for value in adopted.values()):
            return bad("PROMPT_PAYLOAD_ADOPTION_INVALID")
    for optional in ("request_id", "state"):
        if optional in payload and (not isinstance(payload[optional], str) or not payload[optional].strip()):
            return bad("PROMPT_PAYLOAD_TYPE_INVALID")
    if payload.get("state") not in (None, STATE_ACTIVE, STATE_CONFLICTED):
        return bad("PROMPT_PAYLOAD_TYPE_INVALID")
    return {"ok": True, "reason": None}


def payload_is_readable(payload: Mapping[str, Any]) -> bool:
    return validate_payload(payload)["ok"] is True


def prompt_payload(asset: Mapping[str, Any]) -> Mapping[str, Any]:
    """The structured payload of one asset, or `{}` when there is none.

    A prompt asset is recognised by `kind == 'prompt'`, not by a well-formed payload —
    a malformed payload must be visible as a problem, not silently reclassified.
    """
    return _mapping(_mapping(asset.get("parameters")).get(PAYLOAD_KEY))


def is_prompt_asset(asset: Mapping[str, Any]) -> bool:
    return _text(asset.get("kind")) == PROMPT_KIND and not asset.get("deleted_at")


def authoring_state(asset: Mapping[str, Any]) -> str:
    """`ACTIVE` unless the revision lost a concurrent race.

    A `CONFLICTED` revision keeps its content (nothing a user wrote is discarded) but is
    excluded from the version chain and reported separately, so it can never be read as
    the family's current revision.
    """
    return _text(prompt_payload(asset).get("state")) or STATE_ACTIVE


def request_id_of(asset: Mapping[str, Any]) -> str:
    """The authoring request that produced this asset, for exactly-once replay."""
    return _text(prompt_payload(asset).get("request_id"))


#: The authored content that identifies a request. Allocation fields (`family_id`,
#: `revision`, `previous_asset_id`, `request_id`, `state`) are deliberately excluded, so
#: the same request compares equal whatever the server allocated.
CONTENT_KEYS: tuple[str, ...] = (
    "purpose", "origin", "negative_prompt", "model_reference", "parameters", "seed",
    "reference_asset_ids", "output_asset_ids", "character_ids", "scene_ids", "shot_ids",
    "change_note", "change_reason", "redacted",
)


def content_digest(asset: Mapping[str, Any], text: str | None = None) -> str:
    """Digest of the authored request content.

    Built from `CONTENT_KEYS` only, so a client-side request digest and an asset-side
    payload digest are directly comparable. Passing `text` folds the body bytes in.
    """
    payload = prompt_payload(asset)
    basis = {key: payload.get(key) for key in CONTENT_KEYS}
    digest_value = digest(json.dumps(basis, sort_keys=True, ensure_ascii=False, default=str))
    return digest(f"{digest_value}:{digest(text)}") if text is not None else digest_value


def build_payload(*, family_id: str, revision: int, purpose: str, origin: str,
                  negative_prompt: str = "", model_reference: str = "", parameters: Any = None,
                  seed: int | None = None, reference_asset_ids: Any = (), output_asset_ids: Any = (),
                  character_ids: Any = (), scene_ids: Any = (), shot_ids: Any = (),
                  change_note: str = "", change_reason: str = "", previous_asset_id: str | None = None,
                  redacted: bool = False, source: Any = None,
                  request_id: str | None = None, state: str = STATE_ACTIVE) -> dict[str, Any]:
    """Build the payload stored under `parameters.prompt`.

    A pure builder: the asset owner performs the write, the CAS and the lineage
    annotation. Values are validated by shape here so a caller cannot store something
    the projection would then have to guess about.
    """
    if purpose not in PURPOSES:
        raise ValueError("PROMPT_PURPOSE_INVALID")
    if origin not in ORIGINS:
        raise ValueError("PROMPT_ORIGIN_INVALID")
    if not _is_business_int(revision) or revision < 1:
        raise ValueError("PROMPT_REVISION_INVALID")
    if not _text(family_id):
        raise ValueError("PROMPT_FAMILY_REQUIRED")
    if seed is not None and (not _is_business_int(seed) or seed < 0):
        raise ValueError("PROMPT_SEED_INVALID")
    payload: dict[str, Any] = {
        "contract": PAYLOAD_CONTRACT,
        "family_id": _text(family_id),
        "revision": revision,
        "purpose": purpose,
        "origin": origin,
        "negative_prompt": _text(negative_prompt),
        "model_reference": _text(model_reference),
        "parameters": dict(parameters) if isinstance(parameters, Mapping) else {},
        "seed": seed,
        "reference_asset_ids": _identifiers(reference_asset_ids),
        "output_asset_ids": _identifiers(output_asset_ids),
        "character_ids": _identifiers(character_ids),
        "scene_ids": _identifiers(scene_ids),
        "shot_ids": _identifiers(shot_ids),
        "change_note": _text(change_note),
        "change_reason": _text(change_reason),
        "redacted": bool(redacted),
    }
    if previous_asset_id:
        payload["previous_asset_id"] = _text(previous_asset_id)
    if request_id:
        payload["request_id"] = _text(request_id)
    payload["state"] = state
    if isinstance(source, Mapping) and source:
        payload["adopted_from"] = {
            "owner": _text(source.get("owner")), "field": _text(source.get("field")),
            "digest": _text(source.get("digest")),
        }
    return payload


# ------------------------------------------------------------- the family --

def _revision_of(asset: Mapping[str, Any]) -> int:
    revision = prompt_payload(asset).get("revision")
    return revision if _is_business_int(revision) and revision >= 1 else 0


def revision_of(asset: Mapping[str, Any]) -> int:
    """Public revision accessor, so callers need not reach into a private helper."""
    return _revision_of(asset)


def family_of(asset: Mapping[str, Any]) -> str:
    """Public family accessor (see `_family_of`)."""
    return _family_of(asset)


def asset_id_of(asset: Mapping[str, Any]) -> str:
    return _text(asset.get("id"))


def _family_of(asset: Mapping[str, Any]) -> str:
    family = _text(prompt_payload(asset).get("family_id"))
    # An asset that predates a family id is its own family: never merged by guesswork.
    return family or _text(asset.get("id"))


def families(assets: Iterable[Mapping[str, Any]], *, include_deleted: bool = False
             ) -> dict[str, list[Mapping[str, Any]]]:
    """Group prompt assets into version chains, oldest revision first.

    `include_deleted` lets a detail view notice that a revision exists but is no longer
    readable, instead of silently reporting a shorter, "complete" history.
    """
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for asset in _rows(assets):
        if _text(asset.get("kind")) != PROMPT_KIND:
            continue
        if not include_deleted and asset.get("deleted_at"):
            continue
        # A revision that lost a concurrent race is not part of the chain.
        if authoring_state(asset) == STATE_CONFLICTED:
            continue
        grouped.setdefault(_family_of(asset), []).append(asset)
    for rows in grouped.values():
        rows.sort(key=lambda row: (_revision_of(row), _text(row.get("id"))))
    return grouped


def _anomalies(versions: list[Mapping[str, Any]], known: Mapping[str, Mapping[str, Any]],
               family_id: str) -> list[dict[str, Any]]:
    """Structural problems in one family's chain, reported rather than smoothed over."""
    found: list[dict[str, Any]] = []
    seen: dict[int, str] = {}
    for row in versions:
        asset_id = _text(row.get("id"))
        if row.get("deleted_at"):
            found.append({"kind": "REVISION_UNAVAILABLE", "asset_id": asset_id,
                          "detail": "asset is deleted or no longer readable"})
        revision = _revision_of(row)
        if revision in seen:
            found.append({"kind": "DUPLICATE_REVISION", "asset_id": asset_id,
                          "detail": f"revision {revision} also used by {seen[revision]}"})
        else:
            seen[revision] = asset_id
        previous = _text(prompt_payload(row).get("previous_asset_id"))
        if previous:
            if previous not in known:
                found.append({"kind": "BROKEN_PREDECESSOR", "asset_id": asset_id,
                              "detail": f"predecessor {previous} is not present"})
            elif _family_of(known[previous]) != family_id:
                found.append({"kind": "CROSS_FAMILY_LINK", "asset_id": asset_id,
                              "detail": f"predecessor {previous} belongs to another family"})
    revisions = sorted(seen)
    if revisions and revisions != list(range(1, len(revisions) + 1)):
        found.append({"kind": "REVISION_GAP", "asset_id": None,
                      "detail": f"revisions present: {revisions}"})
    return found


# ---------------------------------------------------------------- bindings --

def _version_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """One revision's history entry.

    §3.4 fix: redaction is resolved **per revision**. The previous version used the
    head's flag for every row, so promoting an unmasked revision silently revealed a
    historical note that its own revision had designated for masking (and the reverse
    hid a note that revision had not masked). Each revision's presentation choice now
    remains accurate on its own.
    """
    payload = prompt_payload(row)
    masked = payload.get("redacted") is True
    note, reason = _text(payload.get("change_note")), _text(payload.get("change_reason"))
    return {
        "asset_id": _text(row.get("id")),
        "revision": _revision_of(row),
        "asset_version": row.get("version"),
        "change_note": digest(note) if (masked and note) else note,
        "change_reason": digest(reason) if (masked and reason) else reason,
        "previous_asset_id": _text(payload.get("previous_asset_id")) or None,
        "redacted": masked,
        "available": not bool(row.get("deleted_at")),
    }


def _resolve_bindings(payload: Mapping[str, Any], bible: Mapping[str, Any] | None) -> dict[str, Any]:
    """Resolve every declared binding against the real index.

    An unresolvable target is `UNKNOWN` with the reason stated — never dropped and never
    assumed present (Round 3 §7). This is not a permission check: it says whether the
    target exists in the index the caller supplied.
    """
    character_index = set(_identifiers(bible.get("character_ids"))) if bible is not None else set()
    scene_index = set(_identifiers(bible.get("location_ids"))) if bible is not None else set()
    asset_index = set(_identifiers(bible.get("asset_ids"))) if bible is not None else set()
    shot_keys = set(_identifiers(bible.get("shot_keys"))) if bible is not None else set()

    def resolve(kind: str, declared: list[str], index: set[str], *, scoped: bool = False) -> list[dict[str, Any]]:
        rows = []
        document_id = _text(payload.get("shot_scope")) if scoped else ""
        for identifier in declared:
            known = identifier in index or (scoped and document_id and f"{document_id}:{identifier}" in index)
            rows.append({"kind": kind, "id": identifier,
                         "resolution": KNOWN if known else UNKNOWN,
                         "verification": "INDEX_SUPPLIED" if bible is not None else "NO_INDEX_SUPPLIED"})
        return rows

    return {
        "characters": resolve("CHARACTER", _identifiers(payload.get("character_ids")), character_index),
        "scenes": resolve("SCENE", _identifiers(payload.get("scene_ids")), scene_index),
        "shots": resolve("SHOT", _identifiers(payload.get("shot_ids")), shot_keys, scoped=True),
        "assets": resolve("ASSET",
                          _identifiers(payload.get("reference_asset_ids"))
                          + _identifiers(payload.get("output_asset_ids")), asset_index),
        "verification": "INDEX_SUPPLIED" if bible is not None else "NO_INDEX_SUPPLIED",
    }


# ----------------------------------------------------------------- fields --

def _field(field: str, value: Any, *, authored: bool | None = None) -> dict[str, Any]:
    present = bool(value) if authored is None else authored
    return {
        "field": field,
        "label": PROMPT_FIELD_LABELS.get(field, field),
        "value": value if present else UNKNOWN,
        "authored": present,
        "state": KNOWN if present else UNKNOWN,
    }


def _body_of(asset_id: str, asset_body: Mapping[str, Any]) -> dict[str, Any]:
    """Accept the rich body contract, or a plain string from an older caller."""
    value = asset_body.get(asset_id)
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        return read_prompt_body(value.encode("utf-8"), limit=MAX_TEXT)
    return {"state": BODY_UNDECODABLE, "value": None, "digest": None, "digest_of": None,
            "truncated": False, "decodable": False, "original_length": None,
            "preview_length": 0, "limit": None, "fetch": "UNAVAILABLE"}


def _entry_for(family_id: str, versions: list[Mapping[str, Any]],
               bible: Mapping[str, Any] | None, asset_body: Mapping[str, Any],
               *, read_complete: bool = True,
               known: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    head = versions[-1]
    payload = prompt_payload(head)
    redacted = payload.get("redacted") is True
    body = _body_of(_text(head.get("id")), asset_body)
    if redacted:
        # The digest IS the projection of the body — it is not digested again, so the
        # caller can verify it against the original bytes. The body itself is withheld.
        text_value = body.get("digest") or UNKNOWN
        negative_value = (digest(_text(payload.get("negative_prompt")))
                          if _text(payload.get("negative_prompt")) else "")
        text_authored = bool(body.get("digest"))
        body = {**body, "value": None, "state": "REDACTED", "fetch": "REDACTED"}
    else:
        # A preview is surfaced as a preview; an undecodable body is not "authored".
        text_value = body.get("value") if body.get("value") is not None else UNKNOWN
        text_authored = body.get("value") is not None
        negative_value = _text(payload.get("negative_prompt"))
    bindings = _resolve_bindings(payload, bible)
    reference_ids = _identifiers(payload.get("reference_asset_ids"))
    output_ids = _identifiers(payload.get("output_asset_ids"))
    unresolved = [row["id"] for group in bindings.values() if isinstance(group, list)
                  for row in group if row["resolution"] == UNKNOWN]
    anomalies = _anomalies(versions, known or {}, family_id)
    return {
        "contract": PROMPT_LIBRARY_CONTRACT,
        "family_id": family_id,
        "head_asset_id": _text(head.get("id")),
        "revision": _revision_of(head),
        "asset_version": head.get("version"),
        "purpose": _text(payload.get("purpose")) or UNKNOWN,
        "origin": _text(payload.get("origin")) or UNKNOWN,
        "review_status": _text(head.get("review_status") or "DRAFT") or "DRAFT",
        "approved": bool(head.get("approved_at")),
        "redacted": redacted,
        # The body contract travels with the entry: a preview is never presented as the
        # whole text, and an undecodable body is never presented as authored.
        "body": body,
        "bindings": bindings,
        "unresolved_bindings": unresolved,
        "reference_asset_ids": reference_ids,
        "output_asset_ids": output_ids,
        "anomalies": anomalies,
        "versions": [_version_row(row) for row in versions],
        "fields": [
            _field("text", text_value, authored=text_authored),
            _field("negative_prompt", negative_value),
            _field("model_reference", _text(payload.get("model_reference"))),
            _field("parameters", dict(_mapping(payload.get("parameters")))),
            _field("seed", payload.get("seed"), authored=payload.get("seed") is not None),
            _field("reference_assets", reference_ids),
            _field("output_assets", output_ids),
            _field("purpose", _text(payload.get("purpose"))),
            _field("origin", _text(payload.get("origin"))),
            _field("binding", unresolved, authored=bool(bindings["characters"] or bindings["scenes"]
                                                        or bindings["shots"] or bindings["assets"])),
            _field("version", _revision_of(head)),
        ],
        "read_complete": read_complete,
        "history_complete": read_complete and not any(
            row["kind"] in BLOCKING_ANOMALIES for row in anomalies),
    }


def project_prompt_library(assets: Iterable[Mapping[str, Any]] | None = None, *,
                           bible: Mapping[str, Any] | None = None,
                           asset_text: Mapping[str, Any] | None = None,
                           used_by: Mapping[str, Any] | None = None,
                           coverage: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """The Prompt Library projection: one entry per prompt family.

    `coverage` states honestly whether the read was bounded: a truncated read must not be
    presented as the whole library, and an unknown total is never invented.
    """
    rows = _rows(assets)
    grouped = families(rows)
    known = {_text(row.get("id")): row for row in rows if _text(row.get("id"))}
    bodies = dict(asset_text or {})
    usage = dict(used_by or {})
    cover = dict(coverage or {})
    # §3.2 fix: the outer read completeness must reach every family entry. Previously
    # `_entry_for` kept its `read_complete=True` default, so a truncated list could still
    # advertise a family's latest revision and history as authoritative.
    read_complete = not bool(cover.get("truncated", False))
    entries, malformed = [], []
    for family_id, versions in grouped.items():
        validation = validate_payload(prompt_payload(versions[-1]))
        if not validation["ok"]:
            malformed.append({"asset_id": _text(versions[-1].get("id")), "family_id": family_id,
                              "reason": validation["reason"]})
            continue
        entry = _entry_for(family_id, versions, bible, bodies,
                           read_complete=read_complete, known=known)
        entry["used_by"] = list(usage.get(family_id, []))
        entries.append(entry)
    entries.sort(key=lambda row: (row["family_id"],))
    return {
        "contract": PROMPT_LIBRARY_CONTRACT,
        "schema_version": SCHEMA_VERSION,
        "advisory_only": True,
        "execution_authority": False,
        "auto_modify": False,
        "required_fields": list(PROMPT_FIELDS),
        "purposes": list(PURPOSES),
        "origins": list(ORIGINS),
        "binding_kinds": list(BINDING_KINDS),
        "entries": entries,
        # `prompt_count`/`revision_count` count VALID families and revisions only;
        # malformed artefacts are counted separately so the two can never disagree.
        "prompt_count": len(entries),
        "revision_count": sum(len(versions) for family_id, versions in grouped.items()
                              if validate_payload(prompt_payload(versions[-1]))["ok"]),
        "malformed": malformed,
        "malformed_count": len(malformed),
        # Revisions that lost a concurrent race: preserved, reported, never presented as
        # a valid revision of the family.
        "conflicted": [{"asset_id": _text(row.get("id")), "family_id": _family_of(row),
                        "revision": _revision_of(row), "request_id": request_id_of(row)}
                       for row in rows if authoring_state(row) == STATE_CONFLICTED],
        "conflicted_count": sum(1 for row in rows if authoring_state(row) == STATE_CONFLICTED),
        # Scanned assets and projected families are different quantities and are labelled
        # as such, so neither can be mistaken for the other or for a total.
        "scanned_assets": cover.get("returned", len(entries)),
        "projected_families": len(entries),
        "returned": cover.get("returned", len(entries)),
        "limit": cover.get("limit"),
        "truncated": bool(cover.get("truncated", False)),
        "has_more": bool(cover.get("has_more", False)),
        # The owner's list is bounded; a total is never invented.
        "total_known": bool(cover.get("total_known", False)),
        "read_complete": not bool(cover.get("truncated", False)),
        "unknown_is_explicit": True,
        "bible_index_supplied": bible is not None,
    }


def project_prompt_detail(family_id: str, assets: Iterable[Mapping[str, Any]] | None = None, *,
                          bible: Mapping[str, Any] | None = None,
                          asset_text: Mapping[str, Any] | None = None,
                          used_by: Mapping[str, Any] | None = None,
                          read_complete: bool = True) -> dict[str, Any]:
    """One prompt family with its version history and any structural anomalies.

    `history_complete` is derived from actual coverage and chain integrity — never a
    constant. A family whose revisions could not all be read reports the gap instead of
    presenting a shorter history as complete.
    """
    rows = _rows(assets)
    grouped = families(rows, include_deleted=True)
    versions = grouped.get(family_id)
    if not versions or not validate_payload(prompt_payload(versions[-1]))["ok"]:
        # Detail must not bypass the library's validity gate.
        raise FileNotFoundError(family_id)
    known = {_text(row.get("id")): row for row in rows if _text(row.get("id"))}
    entry = _entry_for(family_id, versions, bible, dict(asset_text or {}),
                       read_complete=read_complete, known=known)
    entry["contract"] = PROMPT_DETAIL_CONTRACT
    entry["schema_version"] = SCHEMA_VERSION
    entry["advisory_only"] = True
    entry["execution_authority"] = False
    entry["auto_modify"] = False
    entry["used_by"] = list((used_by or {}).get(family_id, []))
    return entry


# ---------------------------------------------------------- shot identity --

def shot_index(documents: Iterable[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """A bounded, **scope-aware** shot index built from real shot structures.

    Shot identity is `document_id:number`, so two documents' shot number 1 can never be
    confused. Crucially this does **not** depend on a character appearing in the shot:
    an empty establishing shot is still a valid binding target.
    """
    entries: dict[str, Any] = {}
    for document in _rows(documents):
        document_id = _text(document.get("document_id"))
        if not document_id:
            continue
        for card in _rows(document.get("cards")):
            number = card.get("number")
            key = f"{document_id}:{number}"
            character = _mapping(card.get("character"))
            entries[key] = {
                "key": key,
                "document_id": document_id,
                "shot_id": _text(card.get("shot_id")),
                "number": number,
                "characters": list(_identifiers(character.get("values"))),
            }
    return {"entries": entries, "scope_aware": True, "count": len(entries)}


# -------------------------------------------------------- context assembly --

#: How a shot card's own authored fields map onto context dimensions.
_SHOT_FIELD_SOURCES: tuple[tuple[str, str], ...] = (
    ("lighting", "ShotCard.lighting"), ("action", "ShotCard.action"), ("emotion", "ShotCard.emotion"),
    ("lens", "ShotCard.lens"), ("movement", "ShotCard.camera_motion"),
    ("composition", "ShotCard.composition"), ("character", "ShotCard.characters"),
    ("audio", "ShotCard.sound/sound_effect/dialogue"), ("duration", "ShotCard.duration_seconds"),
)


def shot_card_dimensions(card: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Adapt a **real** `project_shot_cards()` entry into context dimensions.

    `project_shot_cards()` returns top-level structured fields (`lighting`, `action`,
    `audio`, `character`, …) — *not* a `dimensions` list. Reading `card['dimensions']`
    therefore produced an empty context for every real shot; this adapter is the fix.
    Every dimension here is `PER_SHOT_MEASURED`: it describes one shot, not a
    document-level director decision.
    """
    def dimension(field: str, value: Any, authored: Any, source: str) -> dict[str, Any]:
        present = bool(authored) and value not in (None, "")
        return {"field": field, "value": value if present else UNKNOWN,
                "authored": present, "state": KNOWN if present else UNKNOWN,
                "source": source, "kind": "PER_SHOT_MEASURED"}

    out: list[dict[str, Any]] = []
    for field, source in _SHOT_FIELD_SOURCES:
        raw = card.get(field)
        if field == "duration":
            entry = _mapping(raw)
            seconds = entry.get("seconds")
            out.append(dimension(field, "" if seconds is None else str(seconds),
                                 entry.get("authored"), source))
        elif field == "character":
            entry = _mapping(raw)
            out.append(dimension(field, ", ".join(_identifiers(entry.get("values"))),
                                 entry.get("authored"), source))
        elif field == "audio":
            audio = _mapping(raw)
            parts = [part for part in (_text(audio.get("sound")), _text(audio.get("sound_effect"))) if part]
            if audio.get("dialogue"):
                parts.append(f"dialogue:{len(audio['dialogue'])}")
            out.append(dimension(field, ", ".join(parts), audio.get("authored"), source))
        else:
            entry = _mapping(raw)
            out.append(dimension(field, _text(entry.get("value")), entry.get("authored"),
                                 _text(entry.get("source")) or source))
    camera = _mapping(card.get("camera"))
    classification = _mapping(card.get("camera_classification"))
    out.append(dimension("shot_size", _text(camera.get("shot_size")),
                         classification.get("shot_size") in ("CANONICAL", "LEGACY_PASSTHROUGH"),
                         "ShotCard.shot_size"))
    return out


def project_prompt_context(*, character_ids: Iterable[str] = (), location_ids: Iterable[str] = (),
                           director_intent: Mapping[str, Any] | None = None,
                           shot_cards: Iterable[Mapping[str, Any]] | None = None,
                           bible: Mapping[str, Any] | None = None,
                           document_id: str | None = None) -> dict[str, Any]:
    """Round 3-D: show **where a prompt's context would come from** — and stop there.

    Deliberately does **not** compose a final prompt: it reports sources, what each
    contributes, and what is still unauthored, so the user confirms before anything is
    generated. `DOCUMENT_AUTHORED` and `PER_SHOT_MEASURED` are preserved and never
    merged, so a per-shot measurement is never presented as a global director decision.
    """
    character_index = {_text(row.get("character_id")): row
                       for row in _rows((bible or {}).get("characters"))}
    location_index = {_text(row.get("location_id")): row
                      for row in _rows((bible or {}).get("locations"))}

    def bible_dimensions(entry: Mapping[str, Any] | None, kind: str) -> list[dict[str, Any]]:
        if entry is None:
            return []
        return [{"field": _text(item.get("field")), "value": _text(item.get("value")),
                 "authored": bool(item.get("authored")), "state": _text(item.get("state")),
                 "source": _text(item.get("source")), "kind": kind}
                for item in _rows(entry.get("dimensions"))]

    sources: list[dict[str, Any]] = []
    for character_id in _identifiers(list(character_ids)):
        entry = character_index.get(character_id)
        sources.append({"kind": "CHARACTER_BIBLE", "id": character_id,
                        "resolution": KNOWN if entry is not None else UNKNOWN,
                        "dimensions": bible_dimensions(entry, "ENTITY_AUTHORED")})
    for location_id in _identifiers(list(location_ids)):
        entry = location_index.get(location_id)
        sources.append({"kind": "SCENE_BIBLE", "id": location_id,
                        "resolution": KNOWN if entry is not None else UNKNOWN,
                        "dimensions": bible_dimensions(entry, "ENTITY_AUTHORED")})
    if director_intent is not None:
        sources.append({"kind": "DIRECTOR_INTENT", "id": None, "resolution": KNOWN,
                        "document_id": document_id,
                        # The director's own `kind` passes through unchanged, so a
                        # measured aggregate is never relabelled as a document decision.
                        "dimensions": [{"field": _text(item.get("field")), "value": _text(item.get("value")),
                                        "authored": bool(item.get("authored")),
                                        "state": _text(item.get("state")),
                                        "source": _text(item.get("source")),
                                        "kind": _text(item.get("kind")) or "DOCUMENT_AUTHORED"}
                                       for item in _rows(director_intent.get("fields"))]})
    for card in _rows(shot_cards):
        # A real shot card has top-level fields; a pre-adapted one may already carry
        # `dimensions`. Both are accepted, and never confused for one another.
        dimensions = ([{"field": _text(item.get("field")), "value": _text(item.get("value")),
                        "authored": bool(item.get("authored")), "state": _text(item.get("state")),
                        "source": _text(item.get("source")),
                        "kind": _text(item.get("kind")) or "PER_SHOT_MEASURED"}
                       for item in _rows(card.get("dimensions"))]
                      if "dimensions" in card else shot_card_dimensions(card))
        # Identity always resolves to something traceable: the owner's shot id when the
        # document supplies one, otherwise the document-scoped key.
        shot_identity = (_text(card.get("shot_id")) or _text(card.get("id"))
                         or (f"{document_id}:{card.get('number')}" if document_id else ""))
        sources.append({"kind": "SHOT_CARD",
                        "id": shot_identity,
                        "resolution": KNOWN, "document_id": document_id,
                        "number": card.get("number"), "dimensions": dimensions})

    unauthored = [{"kind": source["kind"], "id": source.get("id"), "field": dimension["field"]}
                  for source in sources for dimension in source["dimensions"]
                  if not dimension["authored"]]
    return {
        "contract": PROMPT_CONTEXT_CONTRACT,
        "schema_version": SCHEMA_VERSION,
        "advisory_only": True,
        "execution_authority": False,
        "auto_modify": False,
        "composes_prompt_text": False,
        "requires_user_confirmation": True,
        "document_id": document_id,
        "sources": sources,
        "unauthored": unauthored,
        "unknown_is_explicit": True,
    }
