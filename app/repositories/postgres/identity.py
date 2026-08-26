from __future__ import annotations

import json


class PostgresIdentityRepository:
    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    @staticmethod
    def _lock_workspace(connection, workspace_id: str) -> None:
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"authorization:{workspace_id}",),
        ).fetchone()

    def save_user(self, item: dict) -> dict:
        return self._save("users", item, (item["id"], item["display_name"], item["status"], item["created_at"], item["updated_at"], json.dumps(item.get("metadata"))))

    def save_membership(self, item: dict) -> dict:
        values = (item["id"], item["user_id"], item["workspace_id"], item["status"], item["created_at"], item["updated_at"], json.dumps(item.get("metadata")))
        return self._save("workspace_memberships", item, values)

    def save_membership_with_audit(self, item: dict, audit: dict) -> dict:
        values = (item["id"], item["user_id"], item["workspace_id"], item["status"], item["created_at"], item["updated_at"], json.dumps(item.get("metadata")))
        with self.connection_factory() as connection:
            connection.execute("INSERT INTO workspace_memberships(id,user_id,workspace_id,status,created_at,updated_at,metadata) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING", values)
            row = connection.execute("SELECT id,user_id,workspace_id,status,created_at,updated_at,metadata FROM workspace_memberships WHERE user_id=%s AND workspace_id=%s", (item["user_id"], item["workspace_id"])).fetchone()
            stored = self._row("workspace_memberships", row) if row else None
            if stored != item:
                raise ValueError("workspace_memberships id already exists with different data")
            audit_row = connection.execute("INSERT INTO authorization_audit_events(id,payload) VALUES (%s,%s::jsonb) ON CONFLICT(id) DO UPDATE SET id=EXCLUDED.id WHERE authorization_audit_events.payload=EXCLUDED.payload RETURNING payload", (audit["id"], json.dumps(audit))).fetchone()
            if not audit_row:
                raise ValueError(f"audit id already exists: {audit['id']}")
            connection.commit()
            return stored

    def _save(self, table: str, item: dict, values: tuple) -> dict:
        columns = "id,display_name,status,created_at,updated_at,metadata" if table == "users" else "id,user_id,workspace_id,status,created_at,updated_at,metadata"
        with self.connection_factory() as connection:
            connection.execute(
                f"INSERT INTO {table}({columns}) VALUES ({','.join(['%s'] * len(values))}) ON CONFLICT DO NOTHING",
                values,
            )
            where, params = (("id=%s", (item["id"],)) if table == "users" else ("user_id=%s AND workspace_id=%s", (item["user_id"], item["workspace_id"])))
            row = connection.execute(f"SELECT {columns} FROM {table} WHERE {where}", params).fetchone()
            stored = self._row(table, row) if row else None
            if stored != item:
                raise ValueError(f"{table} id already exists with different data")
            connection.commit()
            return stored

    def get_user(self, user_id: str) -> dict:
        return self._get("users", "id=%s", (user_id,), user_id)

    def get_membership(self, user_id: str, workspace_id: str) -> dict:
        return self._get("workspace_memberships", "user_id=%s AND workspace_id=%s", (user_id, workspace_id), (user_id, workspace_id))

    def remove_membership_with_audit(self, user_id: str, workspace_id: str, audit: dict, protect_last_admin: bool = True) -> dict:
        with self.connection_factory() as connection:
            self._lock_workspace(connection, workspace_id)
            if protect_last_admin:
                connection.execute("SELECT id FROM domain_role_assignments WHERE payload->>'role'='ADMIN' AND payload->'scope'->>'workspace_id'=%s FOR UPDATE", (workspace_id,)).fetchall()
                is_admin = connection.execute("SELECT 1 FROM domain_role_assignments WHERE payload->>'role'='ADMIN' AND payload->>'principal_id'=%s AND payload->'scope'->>'workspace_id'=%s", (user_id, workspace_id)).fetchone()
                active_admins = connection.execute("SELECT COUNT(DISTINCT r.payload->>'principal_id') FROM domain_role_assignments r JOIN workspace_memberships m ON m.user_id=r.payload->>'principal_id' AND m.workspace_id=%s AND m.status='ACTIVE' WHERE r.payload->>'role'='ADMIN' AND r.payload->'scope'->>'workspace_id'=%s", (workspace_id, workspace_id)).fetchone()[0]
                if is_admin and active_admins <= 1:
                    raise ValueError("LAST_ACTIVE_ADMIN")
            row = connection.execute("DELETE FROM workspace_memberships WHERE user_id=%s AND workspace_id=%s RETURNING id,user_id,workspace_id,status,created_at,updated_at,metadata", (user_id, workspace_id)).fetchone()
            if row is None:
                raise KeyError((user_id, workspace_id))
            audit_row = connection.execute("INSERT INTO authorization_audit_events(id,payload) VALUES (%s,%s::jsonb) ON CONFLICT(id) DO UPDATE SET id=EXCLUDED.id WHERE authorization_audit_events.payload=EXCLUDED.payload RETURNING payload", (audit["id"], json.dumps(audit))).fetchone()
            if not audit_row:
                raise ValueError(f"audit id already exists: {audit['id']}")
            connection.commit()
            return self._row("workspace_memberships", row)

    def _get(self, table: str, where: str, params: tuple, key) -> dict:
        columns = "id,display_name,status,created_at,updated_at,metadata" if table == "users" else "id,user_id,workspace_id,status,created_at,updated_at,metadata"
        with self.connection_factory() as connection:
            row = connection.execute(f"SELECT {columns} FROM {table} WHERE {where}", params).fetchone()
        if row is None:
            raise KeyError(key)
        return self._row(table, row)

    def list_users(self, status: str | None = None) -> list[dict]:
        return self._list("users", {"status": status})

    def list_memberships(self, user_id: str | None = None, workspace_id: str | None = None, status: str | None = None) -> list[dict]:
        return self._list("workspace_memberships", {"user_id": user_id, "workspace_id": workspace_id, "status": status})

    def update_membership_status(self, user_id: str, workspace_id: str, status: str, updated_at: str, protect_last_admin: bool = True) -> dict:
        with self.connection_factory() as connection:
            self._lock_workspace(connection, workspace_id)
            if protect_last_admin and status != "ACTIVE":
                connection.execute("SELECT id FROM domain_role_assignments WHERE payload->>'role'='ADMIN' AND payload->'scope'->>'workspace_id'=%s FOR UPDATE", (workspace_id,)).fetchall()
                is_admin = connection.execute("SELECT 1 FROM domain_role_assignments WHERE payload->>'role'='ADMIN' AND payload->>'principal_id'=%s AND payload->'scope'->>'workspace_id'=%s", (user_id, workspace_id)).fetchone()
                active_admins = connection.execute("SELECT COUNT(DISTINCT r.payload->>'principal_id') FROM domain_role_assignments r JOIN workspace_memberships m ON m.user_id=r.payload->>'principal_id' AND m.workspace_id=%s AND m.status='ACTIVE' WHERE r.payload->>'role'='ADMIN' AND r.payload->'scope'->>'workspace_id'=%s", (workspace_id, workspace_id)).fetchone()[0]
                if is_admin and active_admins <= 1: raise ValueError("LAST_ACTIVE_ADMIN")
            row = connection.execute("UPDATE workspace_memberships SET status=%s,updated_at=%s WHERE user_id=%s AND workspace_id=%s RETURNING id,user_id,workspace_id,status,created_at,updated_at,metadata", (status, updated_at, user_id, workspace_id)).fetchone()
            if row is None: raise KeyError((user_id, workspace_id))
            connection.commit()
            return self._row("workspace_memberships", row)

    def update_membership_status_with_audit(self, user_id: str, workspace_id: str, status: str, updated_at: str, audit: dict, protect_last_admin: bool = True) -> dict:
        with self.connection_factory() as connection:
            self._lock_workspace(connection, workspace_id)
            if protect_last_admin and status != "ACTIVE":
                connection.execute("SELECT id FROM domain_role_assignments WHERE payload->>'role'='ADMIN' AND payload->'scope'->>'workspace_id'=%s FOR UPDATE", (workspace_id,)).fetchall()
                is_admin = connection.execute("SELECT 1 FROM domain_role_assignments WHERE payload->>'role'='ADMIN' AND payload->>'principal_id'=%s AND payload->'scope'->>'workspace_id'=%s", (user_id, workspace_id)).fetchone()
                active_admins = connection.execute("SELECT COUNT(DISTINCT r.payload->>'principal_id') FROM domain_role_assignments r JOIN workspace_memberships m ON m.user_id=r.payload->>'principal_id' AND m.workspace_id=%s AND m.status='ACTIVE' WHERE r.payload->>'role'='ADMIN' AND r.payload->'scope'->>'workspace_id'=%s", (workspace_id, workspace_id)).fetchone()[0]
                if is_admin and active_admins <= 1:
                    raise ValueError("LAST_ACTIVE_ADMIN")
            row = connection.execute("UPDATE workspace_memberships SET status=%s,updated_at=%s WHERE user_id=%s AND workspace_id=%s RETURNING id,user_id,workspace_id,status,created_at,updated_at,metadata", (status, updated_at, user_id, workspace_id)).fetchone()
            if row is None:
                raise KeyError((user_id, workspace_id))
            audit_row = connection.execute("INSERT INTO authorization_audit_events(id,payload) VALUES (%s,%s::jsonb) ON CONFLICT(id) DO UPDATE SET id=EXCLUDED.id WHERE authorization_audit_events.payload=EXCLUDED.payload RETURNING payload", (audit["id"], json.dumps(audit))).fetchone()
            if not audit_row:
                raise ValueError(f"audit id already exists: {audit['id']}")
            connection.commit()
            return self._row("workspace_memberships", row)

    def _list(self, table: str, filters: dict) -> list[dict]:
        active = [(name, value) for name, value in filters.items() if value is not None]
        where = " WHERE " + " AND ".join(f"{name}=%s" for name, _ in active) if active else ""
        columns = "id,display_name,status,created_at,updated_at,metadata" if table == "users" else "id,user_id,workspace_id,status,created_at,updated_at,metadata"
        with self.connection_factory() as connection:
            return [self._row(table, row) for row in connection.execute(f"SELECT {columns} FROM {table}{where} ORDER BY id", tuple(value for _, value in active)).fetchall()]

    @staticmethod
    def _row(table: str, row) -> dict:
        names = ("id", "display_name", "status", "created_at", "updated_at", "metadata") if table == "users" else ("id", "user_id", "workspace_id", "status", "created_at", "updated_at", "metadata")
        value = dict(zip(names, row))
        value["created_at"] = value["created_at"].isoformat()
        value["updated_at"] = value["updated_at"].isoformat()
        return value
