BEGIN;
ALTER TABLE chapters ADD COLUMN IF NOT EXISTS document jsonb;
ALTER TABLE chapters ADD COLUMN IF NOT EXISTS version integer NOT NULL DEFAULT 1;
CREATE TABLE chapter_versions(id uuid PRIMARY KEY DEFAULT gen_random_uuid(),chapter_id uuid NOT NULL REFERENCES chapters ON DELETE CASCADE,version integer NOT NULL,document jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),operator text NOT NULL,source text NOT NULL,UNIQUE(chapter_id,version));
ALTER TABLE generation_jobs ADD COLUMN IF NOT EXISTS result jsonb;
ALTER TABLE generation_jobs ADD COLUMN IF NOT EXISTS retry_count integer NOT NULL DEFAULT 0;
ALTER TABLE generation_jobs ADD COLUMN IF NOT EXISTS timeout_seconds integer NOT NULL DEFAULT 120;
INSERT INTO schema_versions(version) VALUES ('0.4.0');
COMMIT;
