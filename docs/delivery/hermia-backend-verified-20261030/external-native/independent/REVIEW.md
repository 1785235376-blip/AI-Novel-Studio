# Independent explicit OTIO native-priority review

Approved scope: explicit opt-in only, backend Studio timeline transfer; strict default preserved. No publication, frontend edits, audio quota/history work, dependency installation or blocked security-review tasks performed.

## Contract findings

- Precision NS `ai_novel_studio_exchange_v1` is distinct from Studio projection NS `ai_novel_studio_timeline_v1`. Only valid stale Clip/Gap start/duration and Clip speed precision hints may yield to native edits. Native available-range/global/transition mismatch remains strict. Studio projection restoration retains original digest/re-derivation/binding validation.
- Frontend transfer parser is closed and computes six-field canonical input digest. Default STRICT mode must be omitted from canonical input; default success response must retain exact legacy keys. Explicit compatibility responses are API-only until separate frontend owner integrates them.
- Independent review found confirmation idempotency request digest initially included default STRICT even when preview digest did not. This broke replay against a pre-feature committed strict receipt. Implementer fixed in 3c3e5a441e39f282e4690a630a8846a296801063. Independent historical-receipt reconstruction and retry now passes.
- Native source bounds refer to declared available_range. Original source-current owner verifies formal identity, project scope, current version/hash/kind and content but does not probe actual media duration. No actual-media-duration proof claimed.
- Strict conflict diagnostic capability field intentionally updates after feature approval; original422/code/message remains and source/remainder validation remains NOT_EVALUATED. Auxiliary diagnostic classification must not replace primary errors.

## Baseline and verification

Immutable baseline651aa1a5ef7fbff3866f920216baa975f8ffea54: original strict runtime+diagnostic19 passed; manifests identical. Two newly added native acceptance cases fail solely because mode is not supported, demonstrating feature gap rather than prior strict defect. Initial test collection failed due to default identity data directory on read-only home; corrected to isolated XDG_DATA_HOME/NOVEL_DATA_PATH, no escalation or dependency changes.

Immutable candidate3c3e5a441e39f282e4690a630a8846a296801063: first61 passed; enlarged combined95 passed/no skips, source app/tests manifests identical. Includes42 independent cases plus original runtime, diagnostics, native-mode implementation and private-link loss suites. Tests use official installed opentimelineio0.18.1, real native serialization and synthetic formal media through both mounted API prefixes. Existing warnings3 are Starlette/httpx deprecation and two Pydantic field shadows.

Coverage: exact old successful response keys/digest; explicitSTRICT/default equality; native trim write+replay; byte SHA echo; loss confirmation; equal-content cross-mode receipt mismatch; mutated original bytes; stale request/actual saved target; pins; revoked session; other-project source; malformed hint shapes/rationals; fractional-ms; native unsupported speed; speed+gap; declared source limits; mode enum/location constraints; historical strict receipt replay. File-store snapshots verify refusals do not mutate state.

Implementer self-review then identified semantic stale duration0/>86400 boundary needing tightening; reviewer added three independent old-hint semantic-bound tests plus two actual target-save cases. Final updated SHA result will be appended after verification.

Limitations: focused File/HTTP tests only, no PostgreSQL or full repository test suite; no Premiere/Resolve interaction or arbitrary NLE roundtrip claim; existing frontend does not expose mode. Native precision conversion is bounded to supported integer-ms/rational contracts, not full OTIO interoperability.

## Final freeze

Final independent immutable source: commit `9f8ca0aff280eb7c055ae47ee3a610022fd90a3d`, tree `ad5c04b97939a6e842233da629e2cb447ae9b439`.
Final combined run: **110 passed, 0 skipped, exit0**,32.68s,3 existing warnings. This comprises47 independent cases and63 repository regression/feature cases, not additive to earlier runs or implementer totals. Source app/tests SHA256 manifest before/after identical. Exact loaded parser/transfer/model module paths, hashes and officialOTIO0.18.1 path captured in final-module-provenance.txt. Reviewer test source SHA256 is recorded in evidence-manifest.sha256.

All five added semantic-bound and actual-target-change cases pass. No outstanding finding in reviewed scope. Strict legacy successful response/canonical input and historical replay preserved; truthful strict diagnostic capability fields are the intentional approved difference. Read-only proof and refusals retain real original owners; compatibility is not a bypass of asset authorization, native supported range, locks or CAS.
