"""Durable File chapter allocation, independent of display order.

All callers hold the existing project lifecycle lock. Historical bytes are never
removed here. Legacy evidence reserves identities; contradictory generations
are quarantined rather than assigned to a guessed owner.
"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from .storage import atomic_write

LEDGER_NAME = "chapter_identity.json"


class ChapterIdentityConflict(FileNotFoundError):
    """The source exists, but its historical identity cannot be resolved safely."""


def _read(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_ledger(root: Path, ledger: dict) -> None:
    atomic_write(root / LEDGER_NAME, json.dumps(ledger, ensure_ascii=False, indent=2))


def empty_ledger() -> dict:
    return {"schema_version": 1, "high_water": 0, "allocations": {},
            "legacy_provenance": "ALLOCATED"}


def _reference_numbers(value, novel_id, *, numeric=False):
    if isinstance(value, str):
        match = re.fullmatch(re.escape(novel_id) + r":([1-9][0-9]*)(?::v[0-9]+)?", value)
        if match:
            yield int(match[1])
    elif isinstance(value, list):
        for item in value:
            yield from _reference_numbers(item, novel_id, numeric=numeric)
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _reference_numbers(key, novel_id, numeric=numeric)
            if numeric and key in {"chapter", "chapter_number"} and type(item) is int and item > 0:
                yield item
            yield from _reference_numbers(item, novel_id, numeric=numeric)


def load_ledger(root: Path) -> dict:
    path = root / LEDGER_NAME
    ledger = _read(path, None)
    if ledger is not None:
        # A broken ledger must never silently reset allocation to one.
        if (not isinstance(ledger, dict) or ledger.get("schema_version") != 1
                or type(ledger.get("high_water")) is not int or ledger["high_water"] < 0
                or not isinstance(ledger.get("allocations"), dict)):
            raise ChapterIdentityConflict("CHAPTER_IDENTITY_LEDGER_INVALID")
        tokens = set()
        for number, entry in ledger["allocations"].items():
            if (not re.fullmatch(r"[1-9][0-9]*", number)
                    or int(number) > ledger["high_water"] or not isinstance(entry, dict)
                    or entry.get("state") not in {"active", "deleted", "reserved", "ambiguous"}):
                raise ChapterIdentityConflict("CHAPTER_IDENTITY_LEDGER_INVALID")
            token = entry.get("public_token", number)
            try:
                canonical_token(token)
            except FileNotFoundError as exc:
                raise ChapterIdentityConflict("CHAPTER_IDENTITY_LEDGER_INVALID") from exc
            if token in tokens or (not token.startswith("~") and token != number):
                raise ChapterIdentityConflict("CHAPTER_IDENTITY_LEDGER_INVALID")
            tokens.add(token)
        return ledger

    ledger = empty_ledger()
    ledger["legacy_provenance"] = "UNKNOWN_NO_HISTORICAL_ALLOCATION_LOG"
    evidence = set()
    active = set()
    for directory in ("chapters", "documents", "history", "summaries"):
        for entry in (root / directory).glob("chapter-*"):
            match = re.fullmatch(r"chapter-([0-9]+)(?:\.md|\.json)?", entry.name)
            if match and int(match[1]) > 0:
                number = int(match[1]); evidence.add(number)
                if directory == "chapters" and entry.suffix == ".md":
                    active.add(number)
    # Include retained references, summaries, archive/order, caches and jobs.
    # Do not infer identity from prose digits. Malformed metadata fails closed.
    for entry in root.rglob("*.json"):
        evidence.update(_reference_numbers(_read(entry, {}), root.name, numeric=entry.is_relative_to(root / "summaries")))
    for directory in ("runtime/jobs", "experimental_v1", "v1_capabilities"):
        for entry in (root.parent.parent / directory).glob("*.json"):
            payload = _read(entry, {})
            if isinstance(payload, dict):
                # Cross-project exact aliases reserve only their named owner.
                # Bare numbers may be future planning/navigation positions;
                # only summary-owner files above supply numeric reservations.
                evidence.update(_reference_numbers(payload, root.name, numeric=False))
    for number in sorted(evidence):
        state = "active" if number in active else "deleted"
        reasons = []
        legacy_history_versions = []
        if number in active:
            package = _read(root / "documents" / f"chapter-{number:04d}.json", {})
            current_version = package.get("version", 1)
            if package.get("chapter_id", f"{root.name}:{number}") != f"{root.name}:{number}":
                reasons.append("DOCUMENT_ID_MISMATCH")
            for history in (root / "history" / f"chapter-{number:04d}").glob("v*.json"):
                item = _read(history, {})
                legacy_history_versions.append(item.get("version"))
                if type(item.get("version")) is not int or type(current_version) is not int or item["version"] >= current_version:
                    reasons.append("HISTORY_NOT_OLDER_THAN_LIVE_GENERATION")
            if reasons:
                state = "ambiguous"
        ledger["allocations"][str(number)] = {"state": state, "origin": "legacy", "reasons": sorted(set(reasons)), "legacy_history_versions": legacy_history_versions}
    ledger["high_water"] = max(evidence, default=0)
    write_ledger(root, ledger)
    return ledger


def require_active(root: Path, number: int) -> None:
    ledger = load_ledger(root)
    entry = ledger["allocations"].get(str(number))
    if entry is None:
        # Files introduced outside the repository after ledger initialization
        # are not silently adopted into an already allocated namespace.
        raise ChapterIdentityConflict(f"CHAPTER_IDENTITY_UNREGISTERED: {root.name}:{number}")
    if entry["state"] == "ambiguous":
        raise ChapterIdentityConflict(f"CHAPTER_IDENTITY_AMBIGUOUS: {root.name}:{number}")
    if entry["state"] != "active":
        raise FileNotFoundError(f"{root.name}:{number}")


def next_number(root: Path, requested=None) -> int:
    ledger = load_ledger(root)
    number = ledger["high_water"] + 1 if requested is None else requested
    if type(number) is not int or number <= 0:
        raise ValueError("chapter number must be a positive integer")
    if str(number) in ledger["allocations"]:
        raise FileExistsError(f"{root.name}:{number}")
    owned_paths = (root/"chapters"/f"chapter-{number:04d}.md",
                   root/"documents"/f"chapter-{number:04d}.json",
                   root/"history"/f"chapter-{number:04d}",
                   root/"summaries"/f"chapter-{number:04d}.json")
    if any(path.exists() for path in owned_paths):
        # A separately restored file is not permission to replace its owner.
        raise FileExistsError(f"{root.name}:{number}")
    return number


def reserve(root: Path, number: int, public_token: str | None = None) -> None:
    ledger = load_ledger(root)
    if str(number) in ledger["allocations"]:
        raise FileExistsError(f"{root.name}:{number}")
    token=canonical_token(public_token or str(number))
    if any(entry.get("public_token", existing) == token for existing,entry in ledger["allocations"].items()):
        raise FileExistsError(f"{root.name}:{token}")
    ledger["high_water"] = max(ledger["high_water"], number)
    ledger["allocations"][str(number)] = {"state": "reserved", "origin": "allocated", "public_token": token}
    write_ledger(root, ledger)


def transition(root: Path, number: int, state: str) -> None:
    ledger = load_ledger(root)
    ledger["allocations"][str(number)]["state"] = state
    write_ledger(root, ledger)


def current_summaries(root: Path, items: list) -> list:
    ledger = load_ledger(root)
    result = []
    for item in items:
        entry = ledger["allocations"].get(str(item.get("chapter")), {})
        if entry.get("state", "active") != "active":
            continue
        token = entry.get("public_token", str(item.get("chapter")))
        if token.startswith("~") and item.get("chapter_id") != f"{root.name}:{token}":
            continue
        result.append(item)
    return result


def require_history_owned(root: Path, number: int) -> None:
    require_active(root, number)
    entry = load_ledger(root)["allocations"][str(number)]
    # Old files identify revisions only by number, not by generation. Keep
    # their bytes, but do not attach unverifiable revisions to the live owner.
    if entry.get("legacy_history_versions"):
        raise ChapterIdentityConflict(f"CHAPTER_HISTORY_IDENTITY_UNVERIFIED: {root.name}:{number}")


def canonical_token(token: str) -> str:
    """Only disjoint canonical numeric and typed UUID ID syntax is accepted."""
    if isinstance(token, str) and re.fullmatch(r"[1-9][0-9]*", token):
        return token
    if isinstance(token, str) and token.startswith("~"):
        try:
            if str(uuid.UUID(token[1:])) == token[1:]:
                return token
        except (ValueError, AttributeError):
            pass
    raise FileNotFoundError("invalid chapter identity")


def resolve(root: Path, token: str) -> int:
    token = canonical_token(token)
    # Typed IDs are only issued with a durable ledger. A miss must not adopt
    # or create metadata in another project while looking up a foreign token.
    if token.startswith("~") and not (root / LEDGER_NAME).is_file():
        raise FileNotFoundError(f"{root.name}:{token}")
    ledger = load_ledger(root)
    if token.startswith("~"):
        matches = [int(number) for number, entry in ledger["allocations"].items()
                   if entry.get("public_token") == token]
        if len(matches) != 1:
            raise FileNotFoundError(f"{root.name}:{token}")
        number = matches[0]
    else:
        number = int(token)
        entry = ledger["allocations"].get(token, {})
        if entry.get("public_token", token) != token:
            # A former client only knows the old numeric alias. New legacy
            # generations deliberately have no numeric alias at all.
            raise FileNotFoundError(f"{root.name}:{token}")
    require_active(root, number)
    return number


def public_id(root: Path, number: int, ledger: dict | None = None) -> str:
    ledger = load_ledger(root) if ledger is None else ledger
    entry = ledger["allocations"].get(str(number), {})
    return f"{root.name}:{entry.get('public_token', str(number))}"


def allocation_token(root: Path, number: int) -> str:
    ledger=load_ledger(root)
    token=str(number) if ledger.get("legacy_provenance") == "ALLOCATED" else "~" + str(uuid.uuid4())
    if any(entry.get("public_token", existing) == token for existing,entry in ledger["allocations"].items()):
        raise FileExistsError(f"{root.name}:{token}")
    return token
