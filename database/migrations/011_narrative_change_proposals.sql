BEGIN;
CREATE TABLE narrative_change_proposals(
 id TEXT PRIMARY KEY,project_id TEXT NOT NULL,proposal_type TEXT NOT NULL,status TEXT NOT NULL,
 subject_type TEXT NOT NULL,subject_id TEXT NOT NULL,chapter_version_id TEXT NOT NULL,
 fingerprint TEXT NOT NULL,summary TEXT NOT NULL,payload JSONB NOT NULL,evidence_ids JSONB NOT NULL,
 created_at TIMESTAMPTZ NOT NULL,updated_at TIMESTAMPTZ NOT NULL,UNIQUE(project_id,fingerprint)
);
CREATE INDEX idx_narrative_change_proposals_project ON narrative_change_proposals(project_id,status,id);
INSERT INTO schema_versions(version) VALUES ('0.5.5-narrative-change-proposals');
COMMIT;
