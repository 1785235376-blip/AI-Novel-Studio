"""Bounded, immutable asset payloads for durable resource-package exports.

No filesystem paths, URLs, or live asset services are accepted by this reader.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import re

from ..industry_export_formats import MAX_PACKAGE_RESOURCE_BYTES, MAX_RESOURCE_BYTES

PACKAGE_FORMATS = frozenset({"screenplay-package", "shot-list-package", "storyboard-package"})


def capture_asset(asset: dict, content: bytes, *, asset_id: str, novel_id: str, branch_id: str | None = None) -> dict:
    if asset.get("id") != asset_id or str(asset.get("novel_id")) != str(novel_id):
        raise ValueError("asset ownership or identity mismatch")
    if branch_id is not None and asset.get("branch_id") != branch_id:
        raise ValueError("asset branch ownership mismatch")
    if not isinstance(content, bytes) or len(content) > MAX_RESOURCE_BYTES:
        raise ValueError("asset exceeds the resource byte limit")
    if type(asset.get("size")) is not int or asset["size"] != len(content):
        raise ValueError("asset size mismatch")
    digest = hashlib.sha256(content).hexdigest()
    if asset.get("sha256") != digest:
        raise ValueError("asset checksum mismatch")
    return {
        "id": asset_id, "novel_id": str(novel_id), "branch_id": asset.get("branch_id"), "filename": asset.get("filename"),
        "media_type": asset.get("media_type"), "size": len(content), "sha256": digest,
        "content_base64": base64.b64encode(content).decode("ascii"),
    }


class FrozenExportResources:
    def __init__(self, snapshot: dict):
        self.novel_id = str(snapshot.get("novel_id") or "")
        self.branch_id = snapshot.get("branch_id")
        self.rows = snapshot.get("resource_payloads") or {}
        if not isinstance(self.rows, dict):
            raise ValueError("invalid frozen asset payloads")
        total = 0
        for row in self.rows.values():
            if not isinstance(row, dict) or type(row.get("size")) is not int or row["size"] < 0:
                raise ValueError("invalid frozen asset size")
            total += row["size"]
        if total > MAX_PACKAGE_RESOURCE_BYTES:
            raise ValueError("assets exceed the package resource byte limit")

    def get(self, asset_id: str) -> dict:
        if not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]{0,254}", asset_id):
            raise ValueError("unsafe asset identity")
        row = self.rows.get(asset_id)
        if not isinstance(row, dict):
            raise FileNotFoundError("asset not captured")
        if row.get("id") != asset_id or row.get("novel_id") != self.novel_id:
            raise ValueError("frozen asset ownership or identity mismatch")
        if self.branch_id is not None and row.get("branch_id") != self.branch_id:
            raise ValueError("frozen asset branch ownership mismatch")
        return {key: value for key, value in row.items() if key != "content_base64"}

    def content(self, asset_id: str) -> bytes:
        metadata = self.get(asset_id)
        encoded = self.rows[asset_id].get("content_base64")
        if not isinstance(encoded, str) or len(encoded) > ((MAX_RESOURCE_BYTES + 2) // 3) * 4:
            raise ValueError("invalid frozen asset encoding or size")
        try:
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("invalid frozen asset encoding") from exc
        capture_asset(metadata, content, asset_id=asset_id, novel_id=self.novel_id, branch_id=self.branch_id)
        return content
