# TEXT-16 — saved screenplay EPUB export

Status: **INTEGRATED SELECTED VERIFICATION COMPLETE / HOSTED PENDING / PARTIAL**.

Baseline: `3a234ed242a2d15698560752d6ac3a982da7c350`, original development branch / Draft PR47.

This is the next bounded Text roadmap slice after mandatory adaptation archival.
The pure encoder was developed in a separate sparse worktree at e29, local commit
`6d894508921250aa52af8c3ec41aea3001255206`. Its original 150-pass receipt belongs
only to that source. Integrated checks below bind the current candidate to the
published archive baseline; they do not substitute for new-SHA hosted acceptance.

## Product and owner boundary

A saved independent or source-bound SCREENPLAY can choose EPUB in the existing
format selector. The original CreativeService export owner performs permission,
CAS/version, source/privacy and document-digest checks both before and after
encoding. Original client response verification checks captured session/branch,
version, MIME, byte capacity and actual SHA256 before exposing a download.

The original standard-library EPUB3 encoder produces five package members, with
mimetype first/uncompressed, a navigation document and one shared spine content
document. Every saved scene becomes a navigable section in existing list order.
Authored heading, location/time, emotion, action, dialogue and delivery remain
readable. Only the existing export provenance allowlist is projected; private
model receipts, Prompt or proposal fields are not included. This is reflowable
reading text, not professional screenplay pagination. Existing encoder heading
trimming, line-ending-to-paragraph projection and zh-CN language metadata are
explicit inherited limits; JSON remains the full structured export.

No new document/asset/export owner, model call, remote resource, font dependency
or package installation is introduced. Generic SCRIPT retains its existing
TXT/Markdown/DOCX formats. Existing Fountain/DOCX/Markdown behavior and the original
PDF-rejection tests remain unchanged. Invalid XML 1.0 characters fail before the
old encoder can silently remove them. The existing 8,000,000-byte output cap
remains enforced.

## Layered verification plan and actual evidence

- Separate pure-encoder source: **150 passed in 5.28 s**, including 148 new cases
  and two original stdlib DOCX/EPUB tests. Imported module paths and unchanged
  before/after source hashes were checked.
- Added integrated owner/API cases cover saved/reopened independent and
  source-bound export, exact binary receipt, stale version, source/privacy change,
  post-encoding revocation/archive, foreign branch, default-off and V1 gates.
- Added client/panel cases cover EPUB MIME and actual hash, corrupt/stale receipts,
  captured authority, supported format boundaries, dirty-state gate, deduplicated
  clicks and the original document-key remount/abort boundary.
- One additive real File browser journey uses the existing screenplay creation
  helpers, selects EPUB, saves downloaded bytes, verifies the first ZIP member
  and the actual response hash, checks unchanged document/source and captures
  the existing selector. It has not been run locally; the prior OS socket EPERM
  remains BLOCKED and is not bypassed.
- Final File/new-PG/UI/build/infrastructure/catalog/source identities and the
  published SHA will be recorded after they actually complete. No old suite
  result is substituted for this integrated tree.

External EPUB readers, EPUBCheck certification, Windows interactive acceptance
and full V2 strict CI acceptance are not claimed. Historical FAILED_OBSERVED,
File/PG cancellations and independent-security-review BLOCKED remain distinct.

## Integration execution records

The first two selected File commands used nonexistent generic-Script test file
names and exited 4 before running any test. Their original FAIL receipts remain;
this was command selection, not a product assertion failure. The corrected third
command uses the actual `test_v2_generic_script.py` plus the two new EPUB modules,
original screenplay export and Creative foundation. It completed **238 passed /
88 profile skips** in 15.49 seconds. Four targeted original/new export client and
panel files completed **23 passed** in 1.92 seconds. The same five modules
against a new empty PostgreSQL database completed **238 passed / 88 profile
skips** in 23.60 seconds, with original 20 migrations and normal server shutdown.
Complete frontend: **2,451 passed / 8 original skips**, 287 files passed /
two skipped, 78.60 seconds. Original TypeScript/Vite build and 52-file token
guard pass; complete infrastructure **352 passed** in 10.78 seconds; official
actionlint 1.7.12 default validation exits 0. Source map: **1,775 inputs**,
SHA256 `137162f021b0ad29797354ac1d6ec69927b3d631e4942b651b74f95ff7e06118`.

A same-round read-only review found no blocking issue; its suggested API invalid-
XML boundary was added before integrated tests. This is ordinary implementation
review, not the historical independent security review. A saved U+000B action
returns 422 with no download header/ZIP bytes and unchanged document data.

PDF is intentionally still unsupported here. The original screenplay export
contract contains two File/PG assertions rejecting PDF for a valid saved document;
those bytes and expectations remain intact. The roadmap's future PDF requirement
is not declared done or bypassed through a duplicate route.

Two independent complete collection inventories each contain **12,072 ordered
nodes**, with no collection errors and identical contents. Inventory is not test
execution. The original frozen V1 gate/hash/skips remain unchanged.
