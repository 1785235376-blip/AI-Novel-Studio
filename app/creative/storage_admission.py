"""Bounded disk admission for the original binary owner, never model cleanup.

No client filesystem path is accepted. This adapter measures only the existing
asset filesystem and applies a safety reserve. It neither scans nor changes
model, runtime, cache, export or unrelated project directories.
"""
from __future__ import annotations

import shutil


class StudioStorageCapacityError(ValueError):
    pass


class StudioStorageAdmission:
    RESERVE_BYTES = 64 * 1024 * 1024

    def __init__(self, workspace):
        self.workspace = workspace

    def available(self):
        try:
            measured = shutil.disk_usage(self.workspace.assets.root)
        except OSError:
            raise StudioStorageCapacityError("CREATIVE_STORAGE_UNAVAILABLE") from None
        if type(measured.free) is not int or measured.free < 0:
            raise StudioStorageCapacityError("CREATIVE_STORAGE_UNAVAILABLE")
        return max(0, measured.free - self.RESERVE_BYTES)

    def require(self, incoming_bytes):
        if type(incoming_bytes) is not int or incoming_bytes < 1:
            raise ValueError("CREATIVE_STORAGE_ESTIMATE_INVALID")
        if incoming_bytes > self.available():
            raise StudioStorageCapacityError("CREATIVE_STORAGE_LOW_SPACE")

    def view(self, quota_remaining):
        try:
            available = min(max(0, quota_remaining), self.available())
            state = "READY" if available else "LOW_SPACE_OR_QUOTA"
        except StudioStorageCapacityError:
            available, state = None, "UNAVAILABLE"
        return {"state": state, "available_import_bytes": available, "reserve_bytes": self.RESERVE_BYTES,
                "measurement": "CURRENT_ORIGINAL_ASSET_FILESYSTEM_AND_PROJECT_QUOTA",
                "paths": {"project": "EXISTING_PROJECT_OWNER", "assets": "EXISTING_ASSET_LIBRARY",
                          "models": "MODEL_CENTER_REFERENCES_ONLY", "cache": "EXISTING_CACHE_OWNER",
                          "exports": "USER_SELECTED_DOWNLOAD"},
                "external_model_scan": False, "automatic_cleanup": False, "automatic_migration": False}
