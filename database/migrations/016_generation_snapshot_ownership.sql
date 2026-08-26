BEGIN;
DO $$
DECLARE constraint_name text;
BEGIN
 SELECT c.conname INTO constraint_name
 FROM pg_constraint c
 JOIN pg_class t ON t.oid=c.conrelid
 WHERE t.relname='chapter_context_snapshots' AND c.contype='u'
   AND pg_get_constraintdef(c.oid) LIKE '%chapter_id, chapter_version, context_pack_hash, prompt_version, model%';
 IF constraint_name IS NOT NULL THEN
  EXECUTE format('ALTER TABLE chapter_context_snapshots DROP CONSTRAINT %I',constraint_name);
 END IF;
END $$;
CREATE INDEX idx_context_snapshots_dedup_lookup
 ON chapter_context_snapshots(chapter_id,chapter_version,context_pack_hash,prompt_version,model);
INSERT INTO schema_versions(version) VALUES ('0.5.6-generation-snapshot-ownership');
COMMIT;
