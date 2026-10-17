# B05 reusable terminology JSON

## Original-owner gap and bounded author workflow

Existing B05 editions already own individual glossary drafts, approval/locking,
source privacy checks, CAS/history, translation execution, memory and issue
navigation. This increment adds reusable glossary files without replacing those
owners. B05 remains PARTIAL; this is not translation-quality acceptance.

1. Explicitly generate a UTF-8 JSON download from the current authorized edition.
   The file contains the exact language pair and all current rule text, including
   notes and revoked/draft rules. It excludes IDs, actors, approvals, locks,
   history and manuscript/translation prose. Download is an explicit local link;
   no cloud upload, provider or automatic filesystem export occurs.
2. Select a local JSON file. Local parsing performs bounded format validation;
   selecting the file sends no request. Explicit preview submits it to the
   current original B05 service as unchanged raw text, which revalidates the complete
   closed schema and rejects duplicate JSON keys. Local JSON.parse is advisory
   and does not itself detect duplicate keys.
3. Inspect every row's literal text, aliases, category, strategy, matching mode,
   forbidden variants and note. Exact duplicates and source/alias overlaps are
   identified against both the file and every existing rule state. The first
   otherwise eligible file duplicate can be selected; later duplicates and all
   conflicting rows are disabled. Existing approved, locked and revoked rules
   cannot be overwritten or bypassed.
4. Select eligible rows, then explicitly confirm draft adoption. All selected
   rows succeed together in one original edition `_mutate` CAS/history action,
   or none do. Source/actor/scope/project incarnation are checked at commit.
5. Refresh/reopen the original edition and use its existing individual approval
   controls. Import does not approve rules, unlock rules, alter translations,
   increment the effective terminology revision or accept language quality.

## Format and limits

Schema: `language-terminology-v1`; exact case-sensitive source/target language
pair; 512 KiB UTF-8 maximum; up to 100 file rows and 100 total edition rules.
Every row has exactly `source_term`, `source_aliases`, `preferred`,
`target_aliases`, `forbidden`, `category`, `strategy`, `match`, `note`.
Original RuleIn constraints remain authoritative: 160-character terms, at most
20 variants per list, 1000-character note, exact preservation strategy and
approved/forbidden disjointness. JSON duplicate keys, unsupported schema/fields,
invalid Unicode and values that would need original-owner whitespace trimming
are rejected. No normalization, regex supplied by files, CSV interpretation,
formula execution or markup rendering occurs. Literal FEFF, combining marks,
emoji, RTL and formula-looking strings remain ordinary text.

## Lifetime and original authority

The coordinator composes the existing edition owner and wraps its SAME raw
ExperimentalStore with the original CreativeProjectStore identity reader.
Constructor is read-only. `existing_owner_only` prevents marker provisioning;
missing/invalid original File identity blocks only this new portability workflow
until the normal Studio owner path initializes it. It does not create another
UUID, store, lifecycle engine, service, provider or manuscript writer.

Read operations take raw-scope then original-owner leases. Adoption enters the
owner lease from the original mutation's in-transaction authorization fence and
retains it through original atomic commit; no nested raw transaction is created.
The preview binds the original project incarnation, edition immutable identity,
version, actor/scope, source snapshot, rules and document. Adoption recomputes the
preview against actual current records. A same-ID recreated project or edition
cannot use an old receipt even if version and rule text were copied.

Client/file/edition/block changes invalidate asynchronous file reads, preview
results and downloads; blob URLs are revoked on invalidation/close. Unknown
admissions are latched per captured session/scope client and edition across
panel remounts. Only explicit fresh authorized edition GET reconciliation clears
the latch. A fresh GET does not prove an earlier request failed or cancel it;
renewed user intent must select the file, obtain a fresh preview and confirm
again. Original CAS and duplicate/conflict revalidation prevent double import
if an old request commits late. There is no automatic POST replay.

## Verification status

Primary serialized verification completed after fresh natural/actual-runner
PathFinder-only origin proofs using the approved clean interpreter. New tests:
30 pass, 15 actual-PG-marked deselected. Unchanged original owner/mounted/
translation regression: 79 pass, 72 actual-PG-marked deselected. UI: 58 pass
(20 new, 38 unchanged). Forced TypeScript, Vite and 52-file token guard pass.
All original-runner receipts report unchanged source hashes during each check;
exact timestamps, commands, hashes and source counts are indexed in the adjacent
JSON. Independent review reran fresh origins, 30 new owner tests (15 PG deselected),
79 unchanged owner tests (72 PG deselected) and all 58 UI tests successfully.
All 11 primary/review receipt before/after maps match the current 2,590-file
source closure. Actual PUBLIC wheel/sdist is NOT_RUN here and deferred to the
parent integrated full-root gate. The exact one-line manifest addition is verified. No browser/native/model/PG run occurred.

Initial transport launch produced no process or receipt; reconciliation and
failure note were retained. The next launcher failed on an unsupported --label
argument before product import. With parent approval only the launcher was
corrected to the original runner's positional label, then origin r3 passed.
Both failed launch artifacts remain preserved; no product/test fix followed
these failures. Expected existing duplicate-ID React warning and large-chunk
Vite warning remain. A schema field-shadow warning does not alter validation.

The checkout is intentionally thin: historical docs/delivery absent, all code
and tests retained. No full historical-document closure claim is made.
Original old tests are unchanged. PostgreSQL is NOT_RUN, never substituted by File.

New tests cover literal roundtrip/history/reopen/original approval, duplicate and
alias conflict policy including revoked/locked records, capacity/closed-schema
bounds, project/edition incarnation, actor/scope/source/final authority fences,
missing original identity, unknown late commit/CAS (deterministic selected interleaving, not live concurrency), explicit UI consent and local
selection, delayed read/preview/export callbacks, remounts, invalid Unicode and
literal formula/markup text. Tests establish only the assertions actually run;
these descriptions are not pass receipts.

No push, hosted CI, paid/model call, PG/security acceptance, browser/visual/native,
Windows/user-machine, main merge, release or full RC claims are made. Existing
P0 BLOCKED / R3-GATE HOLD and production approval gates are unchanged.

Independent review decision: PASS_WITH_EXPLICIT_LIMITS. See
`terminology-portability-independent-review-20261017.{md,json}` for the
reviewer audit and exact receipt/source closure verification. Parent owns
commit, integration and actual PUBLIC packaging; this branch makes no release claim.
