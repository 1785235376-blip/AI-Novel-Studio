BEGIN;
CREATE TABLE character_memories(
 id uuid PRIMARY KEY,novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
 character_id uuid NOT NULL REFERENCES characters(id) ON DELETE CASCADE,business_id text NOT NULL,
 memory_type text NOT NULL CHECK(memory_type IN ('EXPERIENCE','STATE_CHANGE','KNOWLEDGE_CHANGE','RELATIONSHIP_CHANGE')),
 schema_version integer NOT NULL DEFAULT 1 CHECK(schema_version=1),content jsonb NOT NULL,
 status text NOT NULL CHECK(status IN ('ACTIVE','SUPERSEDED','RETRACTED')),
 valid_from_chapter integer,valid_to_chapter integer,proposal_id uuid NOT NULL REFERENCES lore_proposals(id) ON DELETE RESTRICT,
 supersedes_id uuid REFERENCES character_memories(id) ON DELETE RESTRICT,retraction_reason text,
 created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(novel_id,business_id),CHECK(valid_to_chapter IS NULL OR valid_from_chapter IS NULL OR valid_to_chapter>=valid_from_chapter),
 CHECK(status<>'RETRACTED' OR retraction_reason IS NOT NULL)
);
CREATE TABLE memory_snapshots(
 id uuid PRIMARY KEY,novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
 scope text NOT NULL CHECK(scope IN ('CHAPTER','VOLUME','NOVEL')),scope_key text NOT NULL,
 schema_version integer NOT NULL DEFAULT 1 CHECK(schema_version=1),range_start integer,range_end integer,
 memory jsonb NOT NULL,version integer NOT NULL CHECK(version>=1),source_watermark jsonb NOT NULL,
 content_hash text NOT NULL,supersedes_id uuid REFERENCES memory_snapshots(id) ON DELETE RESTRICT,
 created_by text NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(novel_id,scope,scope_key,version),CHECK(range_end IS NULL OR range_start IS NULL OR range_end>=range_start)
);
CREATE INDEX idx_character_memories_active ON character_memories(novel_id,character_id,status);
CREATE INDEX idx_memory_snapshots_latest ON memory_snapshots(novel_id,scope,scope_key,version DESC);
INSERT INTO schema_versions(version) VALUES ('0.5.1-memory');
COMMIT;
