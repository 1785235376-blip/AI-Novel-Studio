BEGIN;
DELETE FROM schema_versions WHERE version='0.5.2-context-intelligence';
DROP TABLE IF EXISTS chapter_context_snapshots;
DROP TABLE IF EXISTS context_validation_reports;
DROP TABLE IF EXISTS context_intents;
COMMIT;
