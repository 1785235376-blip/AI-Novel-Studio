# Explicit Director author draft recovery copy

The original Graph Director Console offers a local JSON download while author
input is dirty or a save outcome is blocked/uncertain. It uses the current
Creative author input projection, not the complete server record, and retains
the original draft, dirty state, unknown-save state and graph bindings.

The closed top-level envelope is studio-director-author-draft-backup/1. It is
labelled LOCAL_AUTHOR_RECOVERY_COPY, server_save_confirmed=false and
execution_authority=false. Base ID/version are context only; a digest is included
only when the already observed pin matches that base version. No server evidence,
actor metadata, session/transport credentials or execution capability is copied.
Authored text remains authored text and must be protected by the person exporting.

Incomplete drafts can be backed up without passing the server-save gate. JSON
bytes are capped at 2 MiB; an oversized draft remains untouched. Current original
edit authority, scope, owner client, busy/lock, author epoch and IME composition
are checked before download. No new API call, create/update, automatic save retry,
cloud upload, browser storage or graph execution occurs. This file is a readable
manual recovery copy; automatic re-import/merge is not implemented.

Evidence: director-author-backup-ui-r1: 14 focused new/original Director Console
checks and TypeScript PASS. Incomplete input, unknown-save semantics, mismatched
base digest omission, server metadata exclusion, byte bound, explicit download,
unchanged dirty state, no owner writes and permission loss are checked. No full
build/suite, backend changes, product browser or release-readiness claim.
