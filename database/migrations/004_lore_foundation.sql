BEGIN;
CREATE TABLE evidence_records(
 id uuid PRIMARY KEY, novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
 schema_version integer NOT NULL DEFAULT 1 CHECK(schema_version=1), source_type text NOT NULL,
 source_id text NOT NULL, chapter_id uuid REFERENCES chapters(id) ON DELETE SET NULL,
 chapter_version integer, generation_job_id uuid REFERENCES generation_jobs(id) ON DELETE SET NULL,
 excerpt text, locator jsonb NOT NULL, content_hash text NOT NULL,
 privacy text NOT NULL CHECK(privacy IN ('LOCAL_ONLY','CLOUD_ALLOWED','REDACT_BEFORE_CLOUD')),
 status text NOT NULL CHECK(status IN ('ACTIVE','INVALIDATED')), invalidation_reason text,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(novel_id,source_type,source_id,content_hash),
 CHECK(source_type IN ('CHAPTER_VERSION','USER_ACTION','GENERATION_JOB','LEGACY_IMPORT')),
 CHECK(source_type<>'CHAPTER_VERSION' OR (chapter_id IS NOT NULL AND chapter_version IS NOT NULL)),
 CHECK(source_type<>'GENERATION_JOB' OR generation_job_id IS NOT NULL),
 CHECK(status<>'INVALIDATED' OR invalidation_reason IS NOT NULL)
);
CREATE TABLE lore_proposals(
 id uuid PRIMARY KEY, novel_id uuid NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
 proposal_type text NOT NULL CHECK(proposal_type IN ('CHARACTER_MEMORY','RELATIONSHIP','EVENT','SECRET_CHANGE','WORLD_RULE','CANON_SUGGESTION')),
 schema_version integer NOT NULL DEFAULT 1 CHECK(schema_version=1), payload jsonb NOT NULL,
 approved_payload jsonb, status text NOT NULL CHECK(status IN ('PENDING','APPROVED','REJECTED')),
 source_chapter_id uuid REFERENCES chapters(id) ON DELETE SET NULL, source_version integer,
 agent_name text, generation_job_id uuid REFERENCES generation_jobs(id) ON DELETE SET NULL,
 confidence numeric CHECK(confidence BETWEEN 0 AND 1), reviewed_by text, reviewed_at timestamptz,
 rejection_reason text, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 CHECK(status<>'APPROVED' OR (approved_payload IS NOT NULL AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)),
 CHECK(status<>'REJECTED' OR (approved_payload IS NULL AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL))
);
CREATE TABLE lore_proposal_evidence(
 proposal_id uuid NOT NULL REFERENCES lore_proposals(id) ON DELETE CASCADE,
 evidence_id uuid NOT NULL REFERENCES evidence_records(id) ON DELETE RESTRICT,
 schema_version integer NOT NULL DEFAULT 1 CHECK(schema_version=1),
 relevance text NOT NULL CHECK(relevance IN ('PRIMARY','SUPPORTING','CONTRADICTING')),
 note text, created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(proposal_id,evidence_id)
);
CREATE INDEX idx_evidence_novel_status ON evidence_records(novel_id,status,created_at);
CREATE INDEX idx_lore_proposals_novel_status ON lore_proposals(novel_id,status,created_at);
CREATE INDEX idx_lore_relation_evidence ON lore_proposal_evidence(evidence_id);
INSERT INTO schema_versions(version) VALUES ('0.5.1-lore');
COMMIT;
