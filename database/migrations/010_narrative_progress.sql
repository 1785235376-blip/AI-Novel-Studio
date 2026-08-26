BEGIN;
CREATE TABLE narrative_mysteries(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,status TEXT NOT NULL,payload JSONB NOT NULL);
CREATE INDEX idx_narrative_mysteries_project ON narrative_mysteries(project_id,id);
CREATE TABLE narrative_character_goals(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,character_id TEXT NOT NULL,status TEXT NOT NULL,payload JSONB NOT NULL);
CREATE INDEX idx_narrative_character_goals_project ON narrative_character_goals(project_id,id);
CREATE TABLE narrative_chapter_links(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,chapter_id TEXT NOT NULL,chapter_version INTEGER NOT NULL,entity_type TEXT NOT NULL,entity_id TEXT NOT NULL,progress_type TEXT NOT NULL,event_id TEXT NOT NULL,payload JSONB NOT NULL);
CREATE INDEX idx_narrative_chapter_links_project ON narrative_chapter_links(project_id,chapter_id,chapter_version,id);
INSERT INTO schema_versions(version) VALUES ('0.5.4-narrative-progress');
COMMIT;
