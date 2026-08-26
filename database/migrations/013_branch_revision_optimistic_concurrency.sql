BEGIN;
ALTER TABLE storyline_branches ADD COLUMN revision BIGINT NOT NULL DEFAULT 0 CHECK(revision>=0);
INSERT INTO schema_versions(version) VALUES ('0.5.5-branch-revision-optimistic-concurrency');
COMMIT;
