-- Additive A43-02/A43-03 identity/order separation. No manuscript, UUID,
-- history, cache or job is rewritten or removed. Apply to an isolated copy
-- first; retained legacy references are not proof of a clean history.
-- No surviving record can prove the maximum number ever handed to an old
-- client. Pre-upgrade projects allocate disjoint typed UUID public IDs;
-- brand-new projects created after the upgrade have a trusted numeric namespace.
ALTER TABLE novels ADD COLUMN IF NOT EXISTS chapter_identity_provenance TEXT NOT NULL DEFAULT 'LEGACY_UNKNOWN';
ALTER TABLE novels ALTER COLUMN chapter_identity_provenance SET DEFAULT 'ALLOCATED';
ALTER TABLE chapters ADD COLUMN IF NOT EXISTS public_token TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS chapter_public_token_unique ON chapters(novel_id, public_token);
ALTER TABLE chapters ADD COLUMN IF NOT EXISTS sort_order INTEGER;
ALTER TABLE chapters ADD COLUMN IF NOT EXISTS identity_status TEXT NOT NULL DEFAULT 'ACTIVE';
UPDATE chapters SET sort_order = chapter_number WHERE sort_order IS NULL;

CREATE TABLE IF NOT EXISTS chapter_identities (
    novel_id UUID NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    chapter_number INTEGER NOT NULL CHECK (chapter_number > 0),
    chapter_id UUID,
    public_token TEXT,
    state TEXT NOT NULL CHECK (state IN ('ACTIVE', 'DELETED', 'AMBIGUOUS')),
    provenance TEXT NOT NULL,
    PRIMARY KEY (novel_id, chapter_number)
);

CREATE UNIQUE INDEX IF NOT EXISTS chapter_reserved_token_unique ON chapter_identities(novel_id, public_token);

-- Old move() changed chapter_number but kept markdown_path. Those surviving
-- contradictory aliases cannot safely be assigned to either historical owner.
UPDATE chapters SET identity_status = 'AMBIGUOUS'
WHERE (markdown_path ~ '^chapters/chapter-[0-9]+[.]md$'
       AND substring(markdown_path from 'chapter-([0-9]+)[.]md$')::INTEGER <> chapter_number)
   OR EXISTS (SELECT 1 FROM chapter_versions v WHERE v.chapter_id = chapters.id AND v.version >= chapters.version);

INSERT INTO chapter_identities(novel_id, chapter_number, chapter_id, public_token, state, provenance)
SELECT novel_id, chapter_number, id, public_token, identity_status, 'LEGACY_UNKNOWN'
FROM chapters
ON CONFLICT (novel_id, chapter_number) DO NOTHING;

-- Reserve former numeric aliases even when no current row occupies them.
INSERT INTO chapter_identities(novel_id, chapter_number, chapter_id, state, provenance)
SELECT novel_id, substring(markdown_path from 'chapter-([0-9]+)[.]md$')::INTEGER,
       NULL, 'AMBIGUOUS', 'LEGACY_PATH_REFERENCE'
FROM chapters
WHERE identity_status = 'AMBIGUOUS'
  AND markdown_path ~ '^chapters/chapter-[0-9]+[.]md$'
  AND substring(markdown_path from 'chapter-([0-9]+)[.]md$')::INTEGER > 0
ON CONFLICT (novel_id, chapter_number) DO NOTHING;

-- Retained jobs can outlive a deleted chapter (their FK becomes NULL).
-- Reserve the original source alias without rebinding it to another UUID.
INSERT INTO chapter_identities(novel_id, chapter_number, chapter_id, state, provenance)
SELECT aliases.novel_id, aliases.number::INTEGER, aliases.chapter_id, 'DELETED', 'LEGACY_JOB_REFERENCE'
FROM (
  SELECT g.novel_id, g.chapter_id,
    CASE WHEN substring(g.request->'_repository_payload'->>'chapter_id' FROM length(n.slug)+2) ~ '^[1-9][0-9]{0,9}$'
      THEN substring(g.request->'_repository_payload'->>'chapter_id' FROM length(n.slug)+2)::BIGINT
      ELSE NULL END AS number
  FROM generation_jobs g JOIN novels n ON n.id = g.novel_id
  WHERE left(g.request->'_repository_payload'->>'chapter_id', length(n.slug)+1) = n.slug || ':'
) aliases
WHERE aliases.number BETWEEN 1 AND 2147483647
ON CONFLICT (novel_id, chapter_number) DO NOTHING;

-- A stored source alias and a surviving job UUID disagree: preserve both
-- objects, quarantine the involved aliases, and never guess which one to use.
UPDATE chapters c SET identity_status = 'AMBIGUOUS'
FROM generation_jobs g JOIN novels n ON n.id = g.novel_id
WHERE g.chapter_id IS NOT NULL
  AND c.novel_id = n.id
  AND (g.request->'_repository_payload'->>'chapter_id') = n.slug || ':' || c.chapter_number::TEXT
  AND g.chapter_id <> c.id;
UPDATE chapter_identities i SET state = 'AMBIGUOUS'
FROM chapters c WHERE i.novel_id = c.novel_id AND i.chapter_number = c.chapter_number
  AND c.identity_status = 'AMBIGUOUS';

-- Inventory exact aliases in known persisted reference stores, including
-- optional experimental storage only when installed. No prose digits or
-- unscoped numeric fields are interpreted as chapter ownership. Reservations
-- are conservative evidence, never a claim of complete historical provenance.
DO $identity_references$
DECLARE source_column RECORD;
BEGIN
  FOR source_column IN
    SELECT table_schema, table_name, column_name
    FROM information_schema.columns
    WHERE table_schema = current_schema() AND data_type IN ('json', 'jsonb')
      AND (table_name, column_name) IN (
        ('novels', 'metadata'), ('generation_jobs', 'request'), ('generation_jobs', 'result'),
        ('chapter_context_snapshots', 'snapshot'), ('experimental_scope_documents', 'document'),
        ('story_states', 'state'), ('canon_entries', 'fact_value'), ('pending_canon', 'proposal'),
        ('timeline_events', 'details'))
  LOOP
    EXECUTE format($scan$
      INSERT INTO chapter_identities(novel_id, chapter_number, chapter_id, state, provenance)
      SELECT DISTINCT aliases.novel_id, aliases.number::INTEGER, NULL::UUID, 'DELETED', 'LEGACY_REFERENCE'
      FROM (
        SELECT n.id AS novel_id,
          CASE WHEN substring(ref.value #>> '{}' FROM length(n.slug)+2) ~ '^[1-9][0-9]{0,9}(:v[0-9]+)?$'
            THEN split_part(substring(ref.value #>> '{}' FROM length(n.slug)+2), ':', 1)::BIGINT
            ELSE NULL END AS number
        FROM %I.%I source
        CROSS JOIN LATERAL jsonb_path_query(source.%I::jsonb, '$.** ? (@.type() == "string")') ref(value)
        JOIN novels n ON left(ref.value #>> '{}', length(n.slug)+1) = n.slug || ':'
      ) aliases
      WHERE aliases.number BETWEEN 1 AND 2147483647
      ON CONFLICT (novel_id, chapter_number) DO NOTHING
    $scan$, source_column.table_schema, source_column.table_name, source_column.column_name);
  END LOOP;
END
$identity_references$;
