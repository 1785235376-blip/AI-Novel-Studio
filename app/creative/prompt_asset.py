"""Prompt Intelligence: a Prompt Asset is an existing asset, projected as a library.

Why this module exists
----------------------
Round 3 turns prompts from scattered text into a reusable, versioned, bindable
asset. Round 3 §3 forbids a second asset, version or review system, and
`ROUND3_PROMPT_SOURCE_AUDIT.md` established exactly how to reuse the existing one
(read from `app/services/asset_library_service.py`, not assumed):

| Prompt Asset property | Existing owner field that carries it |
| --- | --- |
| identity | the asset id (existing asset owner) |
| prompt text | the asset's immutable bytes, `kind="prompt"` (`kind` is free-form) |
| negative prompt, model, parameters, seed, purpose, origin, change note/reason | `parameters` — an allow-listed dict field on `update_metadata` |
| character / scene binding | the **already allow-listed** `character_id` / `scene_id` metadata fields |
| reference assets | `source_asset_ids` (existing) |
| version | the existing asset `version` + `expected_version` CAS |
| version chain | `annotate_lineage` — the existing mechanism that retains a `history` |
| review | `promote_owned` (existing review owner) |
| history retention | assets are immutable and `delete` keeps bytes and identity |

So this module adds **no owner, no collection and no database**. It is a pure
projection plus a payload contract, and `AssetLibraryService` remains the only
writer.

Versioning model
----------------
An asset's bytes are immutable, so a revised prompt is a **new asset** in the same
*family*: the family id is stable, `revision` increments 1, 2, 3…, and the new
asset points at its predecessor through the existing lineage. Every old revision
therefore remains physically readable forever — history cannot be lost — and the
change note/reason recorded on each revision is what makes "v1 → v2" explainable.

Honesty rules
-------------
1. **A binding is shown only when the target really exists.** A character or scene
   that cannot be resolved in the supplied bible index is reported `UNKNOWN`, never
   silently dropped and never assumed present.
2. **Redaction is a first-class mode.** The project already stores only a
   negative-prompt *digest* in lineage, so a prompt may be authored with
   `redacted: true`, in which case only digests are projected.
3. **Nothing is inferred.** A field the author did not set is `UNKNOWN`.
"""
from __future__ import annotations

import hashlib
from typing import Any, Iterable, Mapping

PROMPT_LIBRARY_CONTRACT = "studio-prompt-library/1"
PROMPT_DETAIL_CONTRACT = "studio-prompt-detail/1"
PROMPT_CONTEXT_CONTRACT = "studio-prompt-context/1"
SCHEMA_VERSION = 1

#: The asset `kind` used for prompts. The existing asset owner accepts a free-form kind.
PROMPT_KIND = "prompt"
#: Where the structured payload lives inside the asset's allow-listed `parameters`.
PAYLOAD_KEY = "prompt"
#: Payload schema marker, so a future change is detectable rather than silently misread.
PAYLOAD_CONTRACT = "prompt-asset/1"

UNKNOWN = "UNKNOWN"
KNOWN = "KNOWN"

PURPOSES: tuple[str, ...] = ("IMAGE", "VIDEO", "AUDIO", "TEXT")
ORIGINS: tuple[str, ...] = ("MANUAL", "AI_GENERATED", "IMPORTED")
BINDING_KINDS: tuple[str, ...] = ("CHARACTER", "SCENE", "SHOT", "ASSET")

#: The prompt fields the library must be able to show.
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


def digest(value: Any) -> str:
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


def _identifiers(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


# ------------------------------------------------------------- the payload --

def prompt_payload(asset: Mapping[str, Any]) -> Mapping[str, Any]:
    """The structured prompt payload of one asset, or `{}` when there is none.

    A prompt asset is recognised by `kind == 'prompt'`, not by the payload being
    well formed — a malformed payload must be visible as a problem, not silently
    reclassified as a non-prompt asset.
    """
    return _mapping(_mapping(asset.get("parameters")).get(PAYLOAD_KEY))


def is_prompt_asset(asset: Mapping[str, Any]) -> bool:
    return _text(asset.get("kind")) == PROMPT_KIND and not asset.get("deleted_at")


def build_payload(*, family_id: str, revision: int, purpose: str, origin: str,
                  negative_prompt: str = "", model_reference: str = "", parameters: Any = None,
                  seed: int | None = None, reference_asset_ids: Any = (), output_asset_ids: Any = (),
                  character_ids: Any = (), scene_ids: Any = (), shot_ids: Any = (),
                  change_note: str = "", change_reason: str = "", previous_asset_id: str | None = None,
                  redacted: bool = False, source: Any = None) -> dict[str, Any]:
    """Build the payload stored under `parameters.prompt`.

    This is a pure builder: the asset owner performs the write, the CAS and the
    lineage annotation. Values are validated by shape here so a caller cannot
    store something the projection would then have to guess about.
    """
    if purpose not in PURPOSES:
        raise ValueError("PROMPT_PURPOSE_INVALID")
    if origin not in ORIGINS:
        raise ValueError("PROMPT_ORIGIN_INVALID")
    if type(revision) is not int or revision < 1:
        raise ValueError("PROMPT_REVISION_INVALID")
    if not _text(family_id):
        raise ValueError("PROMPT_FAMILY_REQUIRED")
    if seed is not None and (type(seed) is not int or seed < 0):
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
    if isinstance(source, Mapping) and source:
        payload["adopted_from"] = {
            "owner": _text(source.get("owner")), "field": _text(source.get("field")),
            "digest": _text(source.get("digest")),
        }
    return payload


def payload_is_readable(payload: Mapping[str, Any]) -> bool:
    if _text(payload.get("contract")) != PAYLOAD_CONTRACT:
        return False
    if _text(payload.get("purpose")) not in PURPOSES or _text(payload.get("origin")) not in ORIGINS:
        return False
    revision = payload.get("revision")
    return type(revision) is int and revision >= 1 and bool(_text(payload.get("family_id")))


# ------------------------------------------------------------- the family --

def _revision_of(asset: Mapping[str, Any]) -> int:
    revision = prompt_payload(asset).get("revision")
    return revision if type(revision) is int and revision >= 1 else 0


def _family_of(asset: Mapping[str, Any]) -> str:
    payload = prompt_payload(asset)
    family = _text(payload.get("family_id"))
    # An asset that predates a family id is its own family: never merged by guesswork.
    return family or _text(asset.get("id"))


def families(assets: Iterable[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    """Group prompt assets into version chains, oldest revision first."""
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for asset in _rows(assets):
        if not is_prompt_asset(asset):
            continue
        grouped.setdefault(_family_of(asset), []).append(asset)
    for rows in grouped.values():
        rows.sort(key=lambda row: (_revision_of(row), _text(row.get("id"))))
    return grouped


# ---------------------------------------------------------------- bindings --

def _resolve_bindings(payload: Mapping[str, Any],
                      bible: Mapping[str, Any] | None) -> dict[str, Any]:
    """Resolve every declared binding against the real bible / asset index.

    A declared target that cannot be found is `UNKNOWN` with the reason stated. It
    is never dropped from the list and never assumed to exist — Round 3 requires
    "真实存在才显示；不存在 UNKNOWN".
    """
    character_index = set(_identifiers(bible.get("character_ids"))) if bible is not None else set()
    scene_index = set(_identifiers(bible.get("location_ids"))) if bible is not None else set()
    asset_index = set(_identifiers(bible.get("asset_ids"))) if bible is not None else set()
    shot_index = set(_identifiers(bible.get("shot_ids"))) if bible is not None else set()

    def resolve(kind: str, declared: list[str], index: set[str]) -> list[dict[str, Any]]:
        return [{"kind": kind, "id": identifier,
                 "resolution": KNOWN if identifier in index else UNKNOWN,
                 "verification": "INDEX_SUPPLIED" if bible is not None else "NO_INDEX_SUPPLIED"}
                for identifier in declared]

    return {
        "characters": resolve("CHARACTER", _identifiers(payload.get("character_ids")), character_index),
        "scenes": resolve("SCENE", _identifiers(payload.get("scene_ids")), scene_index),
        "shots": resolve("SHOT", _identifiers(payload.get("shot_ids")), shot_index),
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


def _entry_for(family_id: str, versions: list[Mapping[str, Any]],
               bible: Mapping[str, Any] | None,
               asset_text: Mapping[str, str]) -> dict[str, Any]:
    head = versions[-1]
    payload = prompt_payload(head)
    redacted = bool(payload.get("redacted"))
    text = asset_text.get(_text(head.get("id")), "")
    text_value = digest(text) if redacted else text
    bindings = _resolve_bindings(payload, bible)
    reference_ids = _identifiers(payload.get("reference_asset_ids"))
    output_ids = _identifiers(payload.get("output_asset_ids"))
    unresolved = [row["id"] for group in bindings.values() if isinstance(group, list)
                  for row in group if row["resolution"] == UNKNOWN]
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
        "bindings": bindings,
        "unresolved_bindings": unresolved,
        "reference_asset_ids": reference_ids,
        "output_asset_ids": output_ids,
        "versions": [{
            "asset_id": _text(row.get("id")),
            "revision": _revision_of(row),
            "asset_version": row.get("version"),
            "change_note": _text(prompt_payload(row).get("change_note")),
            "change_reason": _text(prompt_payload(row).get("change_reason")),
            "previous_asset_id": _text(prompt_payload(row).get("previous_asset_id")) or None,
            "redacted": bool(prompt_payload(row).get("redacted")),
        } for row in versions],
        "fields": [
            _field("text", text_value),
            _field("negative_prompt", digest(_text(payload.get("negative_prompt")))
                   if redacted and _text(payload.get("negative_prompt")) else _text(payload.get("negative_prompt"))),
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
    }


def project_prompt_library(assets: Iterable[Mapping[str, Any]] | None = None, *,
                           bible: Mapping[str, Any] | None = None,
                           asset_text: Mapping[str, str] | None = None,
                           used_by: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """The Prompt Library projection: one entry per prompt family, newest revision first."""
    grouped = families(assets)
    text_index = dict(asset_text or {})
    usage = dict(used_by or {})
    entries = []
    malformed = []
    for family_id, versions in grouped.items():
        if not payload_is_readable(prompt_payload(versions[-1])):
            # A prompt-kind asset with an unreadable payload is reported, never guessed at.
            malformed.append({"asset_id": _text(versions[-1].get("id")), "family_id": family_id,
                              "reason": "PROMPT_PAYLOAD_UNREADABLE"})
            continue
        entry = _entry_for(family_id, versions, bible, text_index)
        entry["used_by"] = list(usage.get(family_id, []))
        entries.append(entry)
    entries.sort(key=lambda row: (-row["revision"], row["family_id"]))
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
        "prompt_count": len(entries),
        "revision_count": sum(len(rows) for rows in grouped.values()),
        "malformed": malformed,
        "unknown_is_explicit": True,
        "bible_index_supplied": bible is not None,
    }


def project_prompt_detail(family_id: str, assets: Iterable[Mapping[str, Any]] | None = None, *,
                          bible: Mapping[str, Any] | None = None,
                          asset_text: Mapping[str, str] | None = None,
                          used_by: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """One prompt family with its full version history — every revision retained."""
    grouped = families(assets)
    versions = grouped.get(family_id)
    if not versions:
        raise FileNotFoundError(family_id)
    entry = _entry_for(family_id, versions, bible, dict(asset_text or {}))
    entry["contract"] = PROMPT_DETAIL_CONTRACT
    entry["schema_version"] = SCHEMA_VERSION
    entry["advisory_only"] = True
    entry["execution_authority"] = False
    entry["auto_modify"] = False
    entry["used_by"] = list((used_by or {}).get(family_id, []))
    entry["history_complete"] = True
    return entry


# -------------------------------------------------------- context assembly --

def project_prompt_context(*, character_ids: Iterable[str] = (), location_ids: Iterable[str] = (),
                           director_intent: Mapping[str, Any] | None = None,
                           shot_cards: Iterable[Mapping[str, Any]] | None = None,
                           bible: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Round 3-D: show **where a prompt's context would come from** — and stop there.

    This deliberately does **not** compose a final prompt. It reports the sources,
    what each one contributes, and what is still unauthored, so the user confirms
    before anything is generated. Composing the text automatically is exactly the
    "AI overwrites the user's prompt" behaviour Round 3 §10 forbids.
    """
    character_index = {}
    for row in _rows((bible or {}).get("characters")):
        character_index[_text(row.get("character_id"))] = row
    location_index = {}
    for row in _rows((bible or {}).get("locations")):
        location_index[_text(row.get("location_id"))] = row

    def dimensions_of(entry: Mapping[str, Any] | None) -> list[dict[str, Any]]:
        if entry is None:
            return []
        return [{"field": _text(item.get("field")), "value": _text(item.get("value")),
                 "authored": bool(item.get("authored")), "state": _text(item.get("state")),
                 "source": _text(item.get("source"))}
                for item in _rows(entry.get("dimensions"))]

    sources: list[dict[str, Any]] = []
    for character_id in _identifiers(list(character_ids)):
        entry = character_index.get(character_id)
        sources.append({"kind": "CHARACTER_BIBLE", "id": character_id,
                        "resolution": KNOWN if entry is not None else UNKNOWN,
                        "dimensions": dimensions_of(entry)})
    for location_id in _identifiers(list(location_ids)):
        entry = location_index.get(location_id)
        sources.append({"kind": "SCENE_BIBLE", "id": location_id,
                        "resolution": KNOWN if entry is not None else UNKNOWN,
                        "dimensions": dimensions_of(entry)})
    if director_intent is not None:
        sources.append({"kind": "DIRECTOR_INTENT",
                        "resolution": KNOWN,
                        "dimensions": [{"field": _text(item.get("field")), "value": _text(item.get("value")),
                                        "authored": bool(item.get("authored")),
                                        "state": _text(item.get("state")), "source": _text(item.get("source"))}
                                       for item in _rows(director_intent.get("fields"))]})
    for card in _rows(shot_cards):
        sources.append({"kind": "SHOT_CARD", "id": _text(card.get("shot_id")), "resolution": KNOWN,
                        "dimensions": [{"field": _text(item.get("field")), "value": _text(item.get("value")),
                                        "authored": bool(item.get("authored")),
                                        "state": _text(item.get("state")), "source": _text(item.get("source"))}
                                       for item in _rows(card.get("dimensions"))]})

    unauthored = [{"kind": source["kind"], "id": source.get("id"), "field": dimension["field"]}
                  for source in sources for dimension in source["dimensions"]
                  if not dimension["authored"]]
    return {
        "contract": PROMPT_CONTEXT_CONTRACT,
        "schema_version": SCHEMA_VERSION,
        "advisory_only": True,
        "execution_authority": False,
        "auto_modify": False,
        # The point of the panel: it assembles *sources*, never a finished prompt.
        "composes_prompt_text": False,
        "requires_user_confirmation": True,
        "sources": sources,
        "unauthored": unauthored,
        "unknown_is_explicit": True,
    }
