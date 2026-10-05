"""Server-owned experimental flags, disabled unless explicitly opted in.

No wildcard enable: an accidental environment value cannot expand scope.
"""
from __future__ import annotations
import os
from fastapi import HTTPException

FLAGS = (
    "advanced_planning_v2", "semantic_import_v2", "world_character_engines_v2",
    "unified_review_inbox", "agent_team_recipes", "media_adapter_registry",
    "cover_storyboard_generation", "visual_embeddings", "audiobook_v2",
)


def enabled_flags() -> frozenset[str]:
    if os.getenv("V1_ACCEPTANCE_MODE", "").strip().lower() in {"1", "true", "yes", "on"}:
        return frozenset()
    configured = {v.strip().removeprefix("experimental.") for v in os.getenv("EXPERIMENTAL_FEATURES", "").split(",") if v.strip()}
    return frozenset(configured.intersection(FLAGS))


def require_flag(name: str) -> None:
    if name not in enabled_flags():
        raise HTTPException(404, {"code": "EXPERIMENTAL_FEATURE_DISABLED", "feature": name})


def flag_status() -> dict:
    enabled = enabled_flags()
    return {"experimental": True, "default_enabled": False,
            "features": {f"experimental.{name}": name in enabled for name in FLAGS}}
