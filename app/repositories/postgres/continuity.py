from __future__ import annotations

import json
from uuid import NAMESPACE_URL, UUID, uuid5


TABLES = {
    "timeline": ("timeline_events", None), "locations": ("character_location_states", "character_id"),
    "relationships": ("relationship_states", "source_character_id"), "canon_dependencies": ("canon_dependencies", None),
    "knowledge": ("character_knowledge", "character_id"), "findings": ("continuity_findings", None),
}


class PostgresContinuityRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def _table(self, kind):
        if kind not in TABLES: raise ValueError(f"Unknown continuity kind: {kind}")
        return TABLES[kind]

    @staticmethod
    def _timeline_storage_id(record_id):
        # The original owner has a UUID primary key; the domain ID stays opaque.
        # Keep UUID records at their original keys and never expose this adapter
        # key as an alias for a different public identity.
        try:
            return UUID(record_id)
        except (ValueError, TypeError, AttributeError):
            return uuid5(NAMESPACE_URL, "ai-novel-studio:continuity:timeline:" + record_id)

    @staticmethod
    def _timeline_explicit_novel(conn, payload, novel_id):
        if "novel_id" not in payload:
            return
        explicit = payload["novel_id"]
        if not isinstance(explicit, str) or not explicit:
            raise ValueError("TIMELINE_PROJECT_MISMATCH")
        try:
            physical_id = UUID(explicit)
        except ValueError:
            physical_id = None
        matches = conn.execute(
            "SELECT id FROM novels WHERE slug=%s OR id=%s",
            (explicit, physical_id),
        ).fetchall()
        if {row[0] for row in matches} != {novel_id}:
            raise ValueError("TIMELINE_PROJECT_MISMATCH")

    @staticmethod
    def _timeline_rows(conn, predicate, values):
        return conn.execute(
            "SELECT t.id,t.project_id,t.payload,t.novel_id,t.details,n.slug "
            "FROM timeline_events t JOIN novels n ON n.id=t.novel_id WHERE " + predicate,
            values,
        ).fetchall()

    def _timeline_match(self, conn, record_id, project_id=None):
        rows = self._timeline_rows(
            conn, "t.id=%s OR t.payload->>'id'=%s OR t.details->>'_source_id'=%s",
            (self._timeline_storage_id(record_id), record_id, record_id),
        )
        if not rows:
            raise KeyError(record_id)
        if len(rows) != 1:
            raise ValueError("TIMELINE_IDENTITY_CONFLICT")
        _, stored_project, payload, novel_id, details, slug = rows[0]
        # A UUID hit is not authorization to return another public ID. Likewise,
        # an imported Story Timeline alias cannot be rebound into continuity.
        if (not isinstance(payload, dict) or payload.get("id") != record_id
                or not isinstance(details, dict)
                or details.get("_source_id", record_id) != record_id):
            raise ValueError("TIMELINE_IDENTITY_CONFLICT")
        if (stored_project != slug or payload.get("project_id") != slug
                or (project_id is not None and slug != project_id)):
            raise ValueError("TIMELINE_PROJECT_MISMATCH")
        self._timeline_explicit_novel(conn, payload, novel_id)
        return payload

    def _create_timeline(self, payload):
        record_id, project_id = payload["id"], payload["project_id"]
        storage_id = self._timeline_storage_id(record_id)
        with self.session_factory() as conn:
            # Use the same original novel lock as Story Timeline writes. Slugs
            # are public identities, never UUID-shaped aliases for novels.id.
            novel = conn.execute("SELECT id FROM novels WHERE slug=%s FOR UPDATE", (project_id,)).fetchone()
            if novel is None:
                raise FileNotFoundError(project_id)
            self._timeline_explicit_novel(conn, payload, novel[0])
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                         ("continuity:timeline:" + str(storage_id),))
            try:
                existing = self._timeline_match(conn, record_id, project_id)
            except KeyError:
                existing = None
            if existing is not None:
                return existing
            conn.execute(
                "INSERT INTO timeline_events (id,project_id,payload,novel_id,event_time,sequence,title,details) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING",
                (storage_id, project_id, json.dumps(payload), novel[0],
                 payload.get("start_time") or "UNKNOWN", payload.get("sequence_index") or 0,
                 payload.get("title") or record_id, json.dumps({"_source_id": record_id})),
            )
            # Also check an INSERT conflict before commit: do not silently bind
            # to an unrelated original-owner row or leak its payload.
            result = self._timeline_match(conn, record_id, project_id)
            conn.commit()
            return result

    def _list_timeline(self, predicate, values, project_id=None):
        with self.session_factory() as conn:
            rows = self._timeline_rows(conn, predicate, values)
            result = []
            for row in rows:
                payload = row[2]
                if not isinstance(payload, dict) or not isinstance(payload.get("id"), str):
                    raise ValueError("TIMELINE_IDENTITY_CONFLICT")
                result.append(self._timeline_match(conn, payload["id"], project_id))
            # Sort public IDs, just like File, rather than UUID adapter keys.
            return sorted(result, key=lambda row: row["id"])

    def create(self, kind, payload):
        if kind == "timeline":
            return self._create_timeline(payload)
        table, character = self._table(kind); columns=["id","project_id","payload"]; values=[payload["id"],payload["project_id"],json.dumps(payload)]
        if character: columns.insert(2,character); values.insert(2,payload[character])
        if kind=="relationships": columns.insert(3,"target_character_id"); values.insert(3,payload["target_character_id"] )
        if kind=="canon_dependencies": columns[2:2]=["source_canon_id","target_canon_id"]; values[2:2]=[payload["source_canon_id"],payload["target_canon_id"]]
        if kind=="findings": columns[2:2]=["fingerprint","finding_type"]; values[2:2]=[payload["id"],payload["finding_type"]]
        placeholders=",".join(["%s"]*len(values))
        with self.session_factory() as conn:
            conn.execute(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders}) ON CONFLICT (id) DO NOTHING",values); conn.commit()
        return self.get_by_id(kind,payload["id"] )

    def get_by_id(self,kind,record_id):
        if kind == "timeline":
            with self.session_factory() as conn:
                return self._timeline_match(conn, record_id)
        table,_=self._table(kind)
        with self.session_factory() as conn: row=conn.execute(f"SELECT payload FROM {table} WHERE id=%s",(record_id,)).fetchone()
        if not row: raise KeyError(record_id)
        return row[0]

    def list_by_project(self,kind,project_id):
        if kind == "timeline":
            return self._list_timeline(
                "t.project_id=%s OR t.payload->>'project_id'=%s OR (n.slug=%s AND t.payload<>'{}'::jsonb)",
                (project_id, project_id, project_id), project_id,
            )
        table,_=self._table(kind)
        with self.session_factory() as conn: rows=conn.execute(f"SELECT payload FROM {table} WHERE project_id=%s ORDER BY id",(project_id,)).fetchall()
        return [r[0] for r in rows]

    def list_by_character(self,kind,character_id):
        table,column=self._table(kind)
        if not column: return []
        with self.session_factory() as conn: rows=conn.execute(f"SELECT payload FROM {table} WHERE {column}=%s ORDER BY id",(character_id,)).fetchall()
        return [r[0] for r in rows]

    def list_by_evidence(self,kind,evidence_id):
        if kind == "timeline":
            return self._list_timeline("t.payload->'evidence_ids' ? %s", (evidence_id,))
        table,_=self._table(kind)
        with self.session_factory() as conn: rows=conn.execute(f"SELECT payload FROM {table} WHERE payload->'evidence_ids' ? %s ORDER BY id",(evidence_id,)).fetchall()
        return [r[0] for r in rows]

    def set_finding_status(self,finding_id,status):
        with self.session_factory() as conn:
            row=conn.execute("UPDATE continuity_findings SET payload=jsonb_set(payload,'{status}',to_jsonb(%s::text)) WHERE id=%s RETURNING payload",(status,finding_id)).fetchone(); conn.commit()
        if not row: raise KeyError(finding_id)
        return row[0]

    def mutate_finding(self, project, finding_id, callback):
        with self.session_factory() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", ("continuity:" + project + ":" + finding_id,))
            existing = conn.execute("SELECT project_id,payload FROM continuity_findings WHERE id=%s FOR UPDATE", (finding_id,)).fetchone()
            if existing and existing[0] != project: raise FileNotFoundError(finding_id)
            result = callback(existing[1] if existing else None)
            if result.get("project_id") != project or result.get("id") != finding_id: raise ValueError("FINDING_SCOPE_MISMATCH")
            if existing:
                conn.execute("UPDATE continuity_findings SET payload=%s WHERE project_id=%s AND id=%s", (json.dumps(result), project, finding_id))
            else:
                conn.execute("INSERT INTO continuity_findings (id,project_id,fingerprint,finding_type,payload) VALUES (%s,%s,%s,%s,%s)",
                             (finding_id, project, finding_id, result["finding_type"], json.dumps(result)))
            conn.commit()
        return result
