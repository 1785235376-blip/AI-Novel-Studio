BEGIN;
CREATE TABLE generation_jobs(id uuid PRIMARY KEY DEFAULT gen_random_uuid(), novel_id uuid REFERENCES novels ON DELETE CASCADE, chapter_id uuid REFERENCES chapters ON DELETE SET NULL, operation text NOT NULL, status text NOT NULL, request jsonb NOT NULL DEFAULT '{}', draft_path text, provider text, model text, fallback_used boolean NOT NULL DEFAULT false, error_code text, error_message text, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX idx_generation_jobs_novel_status ON generation_jobs(novel_id,status,created_at DESC);
INSERT INTO schema_versions(version) VALUES ('0.2.0');
COMMIT;
