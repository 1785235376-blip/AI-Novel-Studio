BEGIN;
CREATE TABLE narrative_expectations(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,payload JSONB NOT NULL);
CREATE INDEX idx_narrative_expectations_project ON narrative_expectations(project_id,id);
CREATE TABLE narrative_findings(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,payload JSONB NOT NULL);
CREATE INDEX idx_narrative_findings_project ON narrative_findings(project_id,id);
INSERT INTO schema_versions(version) VALUES ('0.5.4-narrative-findings');
COMMIT;
