from __future__ import annotations

import json


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

    def create(self, kind, payload):
        table, character = self._table(kind); columns=["id","project_id","payload"]; values=[payload["id"],payload["project_id"],json.dumps(payload)]
        if kind=="timeline":
            columns.extend(["novel_id","event_time","sequence","title"])
            values.extend([payload.get("novel_id",payload["project_id"]),payload.get("start_time") or "UNKNOWN",payload.get("sequence_index") or 0,payload.get("title") or payload["id"]])
        if character: columns.insert(2,character); values.insert(2,payload[character])
        if kind=="relationships": columns.insert(3,"target_character_id"); values.insert(3,payload["target_character_id"] )
        if kind=="canon_dependencies": columns[2:2]=["source_canon_id","target_canon_id"]; values[2:2]=[payload["source_canon_id"],payload["target_canon_id"]]
        if kind=="findings": columns[2:2]=["fingerprint","finding_type"]; values[2:2]=[payload["id"],payload["finding_type"]]
        placeholders=",".join(["%s"]*len(values))
        with self.session_factory() as conn:
            conn.execute(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders}) ON CONFLICT (id) DO NOTHING",values); conn.commit()
        return self.get_by_id(kind,payload["id"] )

    def get_by_id(self,kind,record_id):
        table,_=self._table(kind)
        with self.session_factory() as conn: row=conn.execute(f"SELECT payload FROM {table} WHERE id=%s",(record_id,)).fetchone()
        if not row: raise KeyError(record_id)
        return row[0]

    def list_by_project(self,kind,project_id):
        table,_=self._table(kind)
        with self.session_factory() as conn: rows=conn.execute(f"SELECT payload FROM {table} WHERE project_id=%s ORDER BY id",(project_id,)).fetchall()
        return [r[0] for r in rows]

    def list_by_character(self,kind,character_id):
        table,column=self._table(kind)
        if not column: return []
        with self.session_factory() as conn: rows=conn.execute(f"SELECT payload FROM {table} WHERE {column}=%s ORDER BY id",(character_id,)).fetchall()
        return [r[0] for r in rows]

    def list_by_evidence(self,kind,evidence_id):
        table,_=self._table(kind)
        with self.session_factory() as conn: rows=conn.execute(f"SELECT payload FROM {table} WHERE payload->'evidence_ids' ? %s ORDER BY id",(evidence_id,)).fetchall()
        return [r[0] for r in rows]

    def set_finding_status(self,finding_id,status):
        with self.session_factory() as conn:
            row=conn.execute("UPDATE continuity_findings SET payload=jsonb_set(payload,'{status}',to_jsonb(%s::text)) WHERE id=%s RETURNING payload",(status,finding_id)).fetchone(); conn.commit()
        if not row: raise KeyError(finding_id)
        return row[0]
