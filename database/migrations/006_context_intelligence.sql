BEGIN;
CREATE TABLE context_intents(
 id uuid PRIMARY KEY, novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
 intent_type text NOT NULL CHECK(intent_type IN ('CHAPTER_WRITE','CHAPTER_REWRITE','CHAPTER_REVIEW','CONTINUATION','WORLD_BUILDING','CHARACTER_DEVELOPMENT')),
 payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE context_validation_reports(
 id uuid PRIMARY KEY, novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
 context_id text NOT NULL, report jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE chapter_context_snapshots(
 id uuid PRIMARY KEY, novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
 chapter_id uuid NOT NULL REFERENCES chapters(id) ON DELETE CASCADE, chapter_version integer NOT NULL,
 context_pack_hash text NOT NULL, canon_version text NOT NULL, memory_version jsonb NOT NULL,
 character_state_version text NOT NULL, timeline_version text NOT NULL, prompt_version text NOT NULL,
 model text NOT NULL, snapshot jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(chapter_id, chapter_version, context_pack_hash, prompt_version, model)
);
CREATE INDEX idx_context_snapshots_chapter ON chapter_context_snapshots(chapter_id, chapter_version, created_at DESC);
INSERT INTO schema_versions(version) VALUES ('0.5.2-context-intelligence');
COMMIT;
