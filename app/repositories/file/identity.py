from __future__ import annotations

import json
from pathlib import Path

from ...storage import atomic_write
from .mutation_coordinator import workspace_mutation


class FileIdentityRepository:
    def __init__(self, root: Path):
        self.path = Path(root) / "identity.json"

    def _read(self) -> dict:
        if not self.path.exists():
            return {"users": [], "memberships": []}
        value = json.loads(self.path.read_text(encoding="utf-8"))
        return {"users": list(value.get("users", [])), "memberships": list(value.get("memberships", []))}

    def _write(self, value: dict) -> None:
        atomic_write(self.path, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))

    def _save(self, key: str, item: dict, uniqueness: tuple[str, ...]) -> dict:
        data = self._read()
        old_id = next((x for x in data[key] if x["id"] == item["id"]), None)
        old_unique = next((x for x in data[key] if all(x[name] == item[name] for name in uniqueness)), None)
        old = old_id or old_unique
        if old:
            if old != item:
                raise ValueError(f"{key} already exists")
            return old
        data[key].append(item)
        data[key].sort(key=lambda x: x["id"])
        self._write(data)
        return item

    def save_user(self, item: dict) -> dict:
        return self._save("users", item, ("id",))

    def get_user(self, user_id: str) -> dict:
        item = next((x for x in self._read()["users"] if x["id"] == user_id), None)
        if item is None:
            raise KeyError(user_id)
        return item

    def list_users(self, status: str | None = None) -> list[dict]:
        return [x for x in self._read()["users"] if status is None or x["status"] == status]

    def save_membership(self, item: dict) -> dict:
        return self._save("memberships", item, ("user_id", "workspace_id"))

    def _audit_repository(self):
        from .scope import FileAuthorizationRepository
        return FileAuthorizationRepository(self.path.parent)

    def save_membership_with_audit(self, item: dict, audit: dict) -> dict:
        # Both files are snapshotted so an injected audit failure cannot leave a member orphaned.
        before = self.path.read_bytes() if self.path.exists() else None
        try:
            result = self.save_membership(item)
            self._audit_repository().append_audit_event(audit)
            return result
        except Exception:
            if before is None:
                self.path.unlink(missing_ok=True)
            else:
                self.path.write_bytes(before)
            raise

    def get_membership(self, user_id: str, workspace_id: str) -> dict:
        item = next((x for x in self._read()["memberships"] if x["user_id"] == user_id and x["workspace_id"] == workspace_id), None)
        if item is None:
            raise KeyError((user_id, workspace_id))
        return item

    def remove_membership_with_audit(self, user_id: str, workspace_id: str, audit: dict, protect_last_admin: bool = True) -> dict:
        with workspace_mutation(self.path.parent, workspace_id):
            before = self.path.read_bytes() if self.path.exists() else None
            try:
                item = self.update_membership_status(user_id, workspace_id, "INACTIVE", audit.get("timestamp", ""), protect_last_admin)
                data = self._read()
                data["memberships"] = [row for row in data["memberships"] if not (row["user_id"] == user_id and row["workspace_id"] == workspace_id)]
                self._write(data)
                self._audit_repository().append_audit_event(audit)
                return item
            except Exception:
                if before is None:
                    self.path.unlink(missing_ok=True)
                else:
                    self.path.write_bytes(before)
                raise

    def list_memberships(self, user_id: str | None = None, workspace_id: str | None = None, status: str | None = None) -> list[dict]:
        return [x for x in self._read()["memberships"] if (user_id is None or x["user_id"] == user_id) and (workspace_id is None or x["workspace_id"] == workspace_id) and (status is None or x["status"] == status)]

    def update_membership_status(self, user_id: str, workspace_id: str, status: str, updated_at: str, protect_last_admin: bool = True) -> dict:
        with workspace_mutation(self.path.parent, workspace_id):
            data = self._read()
            item = next((x for x in data["memberships"] if x["user_id"] == user_id and x["workspace_id"] == workspace_id), None)
            if item is None: raise KeyError((user_id, workspace_id))
            if protect_last_admin and status != "ACTIVE":
                auth_path = self.path.with_name("authorization.json")
                auth = json.loads(auth_path.read_text(encoding="utf-8")) if auth_path.exists() else {"role_assignments": []}
                admins = {x["principal_id"] for x in auth.get("role_assignments", []) if x["role"] == "ADMIN" and x["scope"]["workspace_id"] == workspace_id}
                active = {x["user_id"] for x in data["memberships"] if x["workspace_id"] == workspace_id and x["status"] == "ACTIVE"}
                if user_id in admins and len(admins & active) <= 1: raise ValueError("LAST_ACTIVE_ADMIN")
            item.update(status=status, updated_at=updated_at)
            self._write(data)
            return item

    def update_membership_status_with_audit(self, user_id: str, workspace_id: str, status: str, updated_at: str, audit: dict, protect_last_admin: bool = True) -> dict:
        with workspace_mutation(self.path.parent, workspace_id):
            before = self.path.read_bytes() if self.path.exists() else None
            try:
                result = self.update_membership_status(user_id, workspace_id, status, updated_at, protect_last_admin)
                self._audit_repository().append_audit_event(audit)
                return result
            except Exception:
                if before is None:
                    self.path.unlink(missing_ok=True)
                else:
                    self.path.write_bytes(before)
                raise
