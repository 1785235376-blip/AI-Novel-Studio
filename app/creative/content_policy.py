"""CONTENT_POLICY_FRAMEWORK: RESERVED — extension points only, NOT an implementation.

A future Studio may let a project declare a creative content scope (for example
Standard Creative, Mature Creative or a custom policy). This module reserves the
places that such a framework would need, without implementing it:

- the vocabulary and the project default live here, so the value has exactly one
  owner and every reader agrees on STANDARD when nothing was declared;
- the asset, model-centre and export/delivery entry points are pure functions that
  describe the future contract and are never consulted by today's behaviour.

Deliberately NOT done here, per the reservation: no Mature/NSFW mode, no content
review system, no filtering of discovered models, no export blocking, no UI switch,
no permission change, no new storage, no change to any existing asset record or to
the asset/model/export owners. A policy is not a way around a safety limit: the
future framework still depends on user responsibility, platform rules, age limits
and moderation policy.

Status marker: ``RESERVED`` (never ``IMPLEMENTED``).
"""
from __future__ import annotations

from typing import Mapping

POLICIES: tuple[str, ...] = ("STANDARD", "MATURE", "RESTRICTED", "CUSTOM")
DEFAULT_CONTENT_POLICY = "STANDARD"
STATUS = "RESERVED"


def effective_content_policy(preferences: Mapping | None) -> str:
    """The project's effective policy: an undeclared or legacy value reads STANDARD.

    Accepts the stored preference mapping (``WorkspacePreferences.model_dump()`` or
    the raw scope row). A value outside the vocabulary cannot come from the typed
    owner, but if an unknown one is ever passed it degrades to the default rather
    than propagating an unvetted scope.
    """
    value = preferences.get("content_policy") if isinstance(preferences, Mapping) else None
    return value if value in POLICIES else DEFAULT_CONTENT_POLICY


def asset_policy_for(project_policy: str | None) -> str:
    """Reserved: an asset inherits the policy of the project it came from.

    The asset owner is NOT changed and no asset metadata field is added yet;
    persisting a per-asset policy would be a typed, backward-compatible extension of
    that owner (with migration and tests), not a side effect of this reservation.
    """
    return project_policy if project_policy in POLICIES else DEFAULT_CONTENT_POLICY


def model_content_policy_support(entry: Mapping | None) -> tuple[str, ...]:
    """Reserved read of an OPTIONAL declaration on a model registry entry.

    Reports only what an entry declares, defaulting to STANDARD. It never filters,
    hides, enables or launches a model, and an unknown declaration is not trusted.
    """
    declared = entry.get("content_policy_support") if isinstance(entry, Mapping) else None
    if isinstance(declared, (list, tuple)) and declared and all(value in POLICIES for value in declared):
        return tuple(declared)
    return (DEFAULT_CONTENT_POLICY,)


def export_notice(project_policy: str | None) -> dict:
    """Reserved export/delivery notice descriptor.

    It exists so a future export can state which policy a package was produced
    under. It is not rendered and it never blocks or changes an export.
    """
    return {"kind": "CONTENT_POLICY_NOTICE", "policy": asset_policy_for(project_policy),
            "rendered": False, "blocking": False, "status": STATUS}
