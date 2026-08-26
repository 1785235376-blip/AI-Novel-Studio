BEGIN;
CREATE TABLE narrative_threads(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,payload JSONB NOT NULL);
CREATE INDEX idx_narrative_threads_project ON narrative_threads(project_id,id);
CREATE TABLE narrative_foreshadowing(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,payload JSONB NOT NULL);
CREATE INDEX idx_narrative_foreshadowing_project ON narrative_foreshadowing(project_id,id);
CREATE TABLE narrative_events(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,subject_id TEXT NOT NULL,chapter_version_id TEXT NOT NULL,fingerprint TEXT NOT NULL,payload JSONB NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT now(),UNIQUE(project_id,fingerprint));
CREATE INDEX idx_narrative_events_project ON narrative_events(project_id,created_at) INCLUDE (id);
INSERT INTO schema_versions(version) VALUES ('0.5.4-narrative-state');
COMMIT;
