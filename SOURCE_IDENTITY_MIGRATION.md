# A43 chapter source identity migration

Scope: A43-02/A43-03 on the separate fix branch inherited from PR43/ad1a90d. No frozen PR, release, protocol 1.0, QingJian, model runtime, or user project is changed by this document. Tests use disposable synthetic projects/schemas. F00 remains INTEGRATED; the other 39 functions remain PARTIAL. Historical independent review remains BLOCKED and unrun device/model environments remain NOT_RUN/LOCAL_REQUIRED.

## Public identity and ordering

- A chapter ID identifies a logical manuscript, never a list position. Moving a chapter preserves its ID, PostgreSQL UUID, document/version, history owner, archive state and references.
- New projects have a trusted allocation log. Existing numeric public IDs (`project:1`) remain compatible; durable reservations prevent reissuing them after chapter deletion, deletion of every chapter or process restart. Explicit occupied/reserved numbers fail with FileExistsError/HTTP 409 before replacement.
- Pre-upgrade projects have UNKNOWN allocation provenance: neither surviving files nor a database maximum proves which numbers an old editor remembers. New chapters in those projects use the disjoint public syntax `project:~canonical-lowercase-UUID`. Creation stays available, including in an empty legacy project. Existing unambiguous numeric owners retain their original numeric aliases.
- A new typed-ID chapter has no numeric alias. Its returned `number` is an immutable internal storage/display locator. Requests using `project:<that number>` fail rather than target the new generation, even when versions match. Use the complete returned ID for URLs, saves, jobs, cache anchors, history and derived writes. Numeric summary calls resolve only an actual numeric owner; typed chapters require the complete ID.
- File keeps chapter order separately. PostgreSQL adds `sort_order`; reorder changes only that field under the novel namespace lock. Document CAS remains on the unchanged internal UUID.
- Tokens must be canonical. Leading-zero/signed/whitespace numbers, malformed or uppercase UUIDs and UUIDs without `~` are rejected. Tokens are project-scoped. Persisted duplicate tokens and forced allocator UUID collisions fail closed before creation. Reservations retain typed tokens after deletion.

## File lifecycle and migration

`chapter_identity.json` is additive project metadata containing a versioned allocation ledger, high-water mark, immutable public tokens, active/reserved/deleted/ambiguous state, and legacy provenance. Existing project lifecycle locking covers reads, allocation, deletion and reorder across participating processes.

For a newly created project the empty ledger is persisted immediately. Chapter creation reserves its identity before writing manuscript bytes. Failed partial creation burns the reservation; a retry cannot silently inherit it. Deletion records a tombstone before removing the current manuscript/document files. Historical revision and summary bytes are retained. Active contexts exclude known deleted or ambiguous summaries.

For a project without the ledger, migration inventories chapter/document/history/summary paths and exact retained source aliases, including version-qualified aliases, archive/order state, original runtime jobs and scoped experimental/capability records. It reserves the evidence without deleting or renumbering it. Allocation provenance remains UNKNOWN; the inventory is not proof of complete historical ownership. New typed IDs provide safety even when no old evidence survived.

Contradictory document IDs or revision numbers not older than the current generation mark the source AMBIGUOUS. Reads/writes through that source fail closed. Legacy File revisions lack a generation owner: their bytes remain available for explicit offline review, but the normal history/restore path does not attach those unverified revisions to the live chapter. Newly recorded revisions for ledger-established chapters use their stable owner. A direct valid typed source can be resolved without accidentally reading a quarantined sibling; whole-project list/export may stop on an unresolved sibling rather than silently omit it.

## PostgreSQL additive migration 020

The migration preserves every existing chapter UUID, numeric owner, current document, version, title, path, history row and job payload. It adds:

- `novels.chapter_identity_provenance`: pre-upgrade rows become LEGACY_UNKNOWN; subsequently created projects default to ALLOCATED
- `chapters.public_token`, `sort_order` and `identity_status`
- `chapter_identities`: persistent `(novel_id, storage_number)` reservations with original UUID, optional typed token, state and provenance; no chapter FK erases a reservation on chapter deletion
- Unique typed-token indexes for live objects and retained reservations

Surviving path/number contradictions from the old swapping algorithm and conflicting job UUID/source aliases are quarantined. Exact aliases in known persisted reference stores, including optional experimental storage when present, are reserved conservatively. Existing documents, history, graph/job references and caches are never mass-purged or silently rebound. The absence of contradictions does not certify that old move-back/delete/reuse never happened; historical provenance remains UNKNOWN.

All normal creation and audited creation use the same namespace-locked allocation path. Move/create/delete serialize on that namespace. Reorder does not increment a document version to disguise a changed owner. File-to-PostgreSQL import retains typed tokens and source tombstones; it refuses a destination with a different public owner and reports unverified legacy history instead of importing it under a guessed owner.

The historical feature-migration registry API remains compatible. The actual default packaged runner additionally loads the mandatory shared identity chain and includes it in readiness/checksum validation for flags OFF, flags ON and V1 mode. Missing or failed migration 020 blocks readiness. Explicit custom migration chains remain explicit custom chains. Transaction control is still forbidden in migration files; transaction-neutral quoted PL/pgSQL blocks are permitted inside the runner's enclosing transaction.

## Isolated-copy upgrade and recovery procedure

1. Stop writers and queued callbacks for the copied project/database. Preserve a complete backup, including original ledger absence, documents, histories, summaries, caches, job payloads and source references. Record source commit/schema and hashes. Do not test on a real project.
2. Apply migration 020 in a database transaction, or initialize File identity metadata on the isolated copy. Review the UNKNOWN/AMBIGUOUS report and all retained references. Verify unchanged manuscript/history/job bytes and UUIDs before exercising new typed creation.
3. Exercise old numeric URL/CAS rejection against a new typed generation, new typed read/save/archive/history/restart, same-version A/B move, delayed jobs, exports/graph references and concurrency. Run both API aliases with flags OFF/ON/V1.
4. Resolve a quarantined historical source only from independent backup/original-generation evidence and explicit owner review. Do not clear all history, mark UNKNOWN as verified merely because versions align, or bulk-reassign number-based references. If ownership cannot be established, preserve the originals and recover selected material as an explicitly reviewed new chapter; references to the unresolved source remain invalid.
5. Rollback requires the complete pre-upgrade copy. Do not run an old binary against new typed-ID data or remove allocation metadata: old code can reuse/rebind identities. Schema downgrade and production backport/release need separate authorization.

## Limits and evidence

This fixes chapter identity within a retained project namespace. Deleting a whole project and later recreating its same slug is a separate project-generation problem; this work does not claim globally unique identities across that operation. Existing explicit PostgreSQL deletion/cascade semantics are unchanged; migration and move do not delete history.

The untouched real PostgreSQL baseline established same-version wrong-object save on PostgreSQL 16/Python 3.12.9. Local File safety RED and GREEN receipts, additive migration tests and the API/reference matrix are recorded separately. Local Python 3.12.14 runs are supplemental and never represented as the locked hosted environment. Only actual completed hosted receipts establish PostgreSQL GREEN; synthetic/minimal migration fixtures and source inspection do not replace the full application matrix.


## Dependent-consumer and error-precedence contract

`docs/delivery/a43-fixes/IMPLEMENTATION_SURFACES.json` records the exact path/hash/reason map: 13 shared document/identity/lifecycle owners and 26 dependent consumer files. The dependents carry complete identities through the existing API/context/agent/job/snapshot/search/export/import/packaged-startup owners and four existing frontend request consumers. Two separate frontend files add regression assertions only. This count does not represent new product features or alternate stores.

After a deleted-source PG completion write is refused, the durable generation row can correctly retain an older status. Acceptance now resolves that original durable chapter before interpreting completion status, after the existing content/accounting/security checks. A missing owner remains 404/409 rather than an unrelated incomplete-draft400; an existing unfinished draft retains its original400 contract. The existing real-PG matrix and a separately labelled File refusal fixture test both conditions. No old source alias is rebound and no detached result is made writable to achieve a passing status.

Prospective non-reuse and immutable owner/order separation do not reconstruct unknowable pre-upgrade generations. Existing UNKNOWN provenance is not upgraded to trusted ownership merely because current IDs/versions look consistent. Only evidenced contradictions can be quarantined automatically; uncertain historical ownership still needs independent backup evidence and explicit reconciliation. This uncertainty does not block safe new typed-ID creation in an otherwise readable legacy project.


## Drive-qualified legacy project components

File identifiers such as `C:`, `C:foo` and `D:foo` are rejected before deriving a path or lock on every platform. PureWindowsPath demonstrates that these relative drive forms may resolve to the novels directory, alias another project or change drives; checking only `is_absolute()` is insufficient. Ordinary slug-generated IDs and existing supported dot-directory IDs remain valid. This is a narrow namespace guard, not a general filesystem sandbox or native-device certification.

A manually created POSIX legacy directory with such a literal ID requires explicit operator reconciliation from an isolated backup before normal application access. Its bytes are retained, with no automatic rename or ownership reassignment. This specific unsafe project-name boundary is distinct from ordinary readable legacy projects, where safe typed-UUID chapter creation remains available.
