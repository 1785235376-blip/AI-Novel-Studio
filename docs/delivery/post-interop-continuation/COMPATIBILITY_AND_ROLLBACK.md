# Continuation compatibility and rollback

Initial integration guidance; each wave must supplement this with its executed upgrade cases.

The continuation reuses the existing original repositories and ExperimentalStore schema-version-1 File scope documents / PostgreSQL `experimental_scope_documents` JSONB rows. Additive record fields and new metadata collections do not require a new SQL table or modification of old SQL migrations. This is not permission to rewrite old migration files or to point an experiment at a real V1 data profile.

- Existing records without optional new fields must retain their historical interpretation, with safe explicit defaults and no automatic model invocation.
- New source snapshots, history records, review receipts and pins are immutable evidence or derived metadata, not a second mutable manuscript, Model Center, task state or Canon authority.
- Existing source CAS, final authorization, privacy, cancellation and terminal fences remain authoritative.
- File and PostgreSQL contracts use the same service code and generic scope-document persistence. A File-only run is not PostgreSQL evidence; final hosted marked-PG cases must execute and pass.
- Before upgrading an experimental profile, take a recoverable backup through the existing backup authority. Preserve the separate original V1 profile.
- A code rollback alone does not make newly introduced record kinds/fields writable by an old version. Old UI may not display them or may reject new enum values. Stop editing those new records with the old application, retain their original store files/rows and restore the experimental-profile backup if necessary. No downgrade script deletes new records or rewrites old migrations.
- Restoring an old backup changes the experimental profile's state and must be an explicit user choice. It is not performed by CI or by this continuation.

Final delivery will state whether any SQL migration was actually added and list the exact old-data upgrade tests. Native installer/upgrade/uninstall retention remains LOCAL_REQUIRED and is not inferred from JSON persistence tests.
