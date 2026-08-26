BEGIN;
CREATE TABLE users(
 id TEXT PRIMARY KEY,
 display_name TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('ACTIVE','INACTIVE')),
 created_at TIMESTAMPTZ NOT NULL,
 updated_at TIMESTAMPTZ NOT NULL,
 metadata JSONB NULL
);
CREATE TABLE workspace_memberships(
 id TEXT PRIMARY KEY,
 user_id TEXT NOT NULL REFERENCES users(id),
 workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 status TEXT NOT NULL CHECK(status IN ('ACTIVE','INACTIVE')),
 created_at TIMESTAMPTZ NOT NULL,
 updated_at TIMESTAMPTZ NOT NULL,
 metadata JSONB NULL,
 UNIQUE(user_id,workspace_id)
);
CREATE INDEX idx_workspace_memberships_workspace_status ON workspace_memberships(workspace_id,status);
CREATE INDEX idx_workspace_memberships_user_status ON workspace_memberships(user_id,status);

-- Collaboration metadata is nullable for legacy rows; existing operator/source
-- fields remain intact and no synthetic actor is backfilled.
ALTER TABLE chapter_versions ADD COLUMN actor_id TEXT NULL REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE chapter_versions ADD COLUMN session_id TEXT NULL;
ALTER TABLE chapter_versions ADD COLUMN scope_type TEXT NULL CHECK(scope_type IN ('WORKSPACE','PROJECT','STORYLINE','BRANCH'));
ALTER TABLE chapter_versions ADD COLUMN scope_id TEXT NULL;
ALTER TABLE chapter_versions ADD COLUMN metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE chapter_versions ADD COLUMN reason TEXT NOT NULL DEFAULT 'MANUAL_SAVE'
 CHECK(reason IN ('MANUAL_SAVE','AI_ACCEPT','RESTORE','CHAPTER_SWITCH','EXPLICIT_CHECKPOINT'));

ALTER TABLE chapter_context_snapshots ADD COLUMN actor_id TEXT NULL REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE chapter_context_snapshots ADD COLUMN session_id TEXT NULL;
ALTER TABLE chapter_context_snapshots ADD COLUMN scope_type TEXT NULL CHECK(scope_type IN ('WORKSPACE','PROJECT','STORYLINE','BRANCH'));
ALTER TABLE chapter_context_snapshots ADD COLUMN scope_id TEXT NULL;
ALTER TABLE chapter_context_snapshots ADD COLUMN context_mode TEXT NOT NULL DEFAULT 'V1' CHECK(context_mode IN ('V1','V2'));
ALTER TABLE chapter_context_snapshots ADD COLUMN ordering JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE chapter_context_snapshots ADD COLUMN budget JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE generation_jobs ADD COLUMN context_snapshot_id UUID NULL
 REFERENCES chapter_context_snapshots(id) ON DELETE RESTRICT;
CREATE INDEX idx_generation_jobs_context_snapshot ON generation_jobs(context_snapshot_id);
INSERT INTO schema_versions(version) VALUES ('0.5.6-collaboration-runtime-foundation');
COMMIT;
