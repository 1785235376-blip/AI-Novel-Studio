-- Additive Post-V1 metadata only. Legacy tables and migrations remain unchanged.
-- Rollback: disable all experimental flags first; export the scope documents,
-- then DROP TABLE experimental_scope_documents only when explicitly authorized.
CREATE TABLE IF NOT EXISTS experimental_scope_documents (
    scope_key text PRIMARY KEY CHECK (length(scope_key) = 64),
    novel_id text NOT NULL,
    scope jsonb NOT NULL CHECK (jsonb_typeof(scope) = 'object'),
    document jsonb NOT NULL CHECK (jsonb_typeof(document) = 'object'),
    revision bigint NOT NULL DEFAULT 1 CHECK (revision >= 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS experimental_scope_documents_novel_idx
    ON experimental_scope_documents (novel_id);
