from __future__ import annotations

READ_SCOPES = ("workspace.summary", "novel.chapter", "novel.lore", "novel.characters", "novel.locations", "runtime.models")
DENIED_SCOPES = ("novel.write", "novel.delete", "generation.submit", "content.publish", "external.request")


class HarnessContextAdapter:
    """Permission contract for the optional local Harness runtime."""
    def contract(self) -> dict:
        return {"version": "1.0", "mode": "read_only", "read_scopes": list(READ_SCOPES), "denied_scopes": list(DENIED_SCOPES), "confirmation_required": [], "writes_enabled": False}


harness_context_adapter = HarnessContextAdapter()
