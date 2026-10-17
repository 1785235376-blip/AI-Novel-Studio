# Audio history diagnostic precedence

Status: scoped fix verified; not a repository-wide green or release claim.

The unchanged original listing suite reproduced exactly the five previously recorded failures: unsupported stored body, oversized prompt, too many source snapshots, malformed graph binding and mismatched source snapshot. The other 41 selected checks passed; two PostgreSQL-only cases were excluded. The raw RED receipt is retained as audio-listing-precedence-baseline-r1.

The fix only changes diagnostic priority for a matching owner's read-only listing. When the raw immutable request hash differs, the listing may report the existing bounded shape/source errors. That path always rejects. It cannot accept normalized content, return a partial history, rewrite persistence, or refresh source bindings. get, execution and review retain their original hash-first behavior. Other tampering still reports JOB_BINDING_CHANGED. Actor/scope/incarnation filtering, duplicate-ID handling, single snapshot loading and linear visitation are unchanged.

Seven new regressions verify valid-shape tampering remains rejected in both list and get, invalid-shape diagnostics are listing-only, and actual persisted JSON bytes remain unchanged. No original test was modified or skipped to make the failures disappear.

Verification:

- Original listing, new integrity regressions and MP3 compatibility: 79 passed, two PostgreSQL cases deselected.
- WAV/fade/peak and editing/FLAC/MP3 API contracts: 231 passed, 106 PostgreSQL cases deselected.
- Editing pipeline, real CPU fade/peak/FLAC/MP3 and original Audio API: 117 passed, 90 PostgreSQL cases deselected.
- Fresh forced TypeScript, production build and token guard passed. Frontend source is unchanged from the preceding 332-test Director verification; those frontend tests were not rerun here.
- PUBLIC packaging: 87 passed. Two actual wheels and two actual sdists were re-read without installation and all included payload hashes match current source, including studio_audio_execution.py. Four-archive inspection and original package logs/receipts are retained in delivery/v2-development/audio-listing-precedence-20261017.

All successful check receipts share the same source snapshot. The failed baseline remains distinct. No PostgreSQL, live provider, browser, Windows, GPU or full V2 acceptance is claimed. Production Director route activation remains off. This change does not alter mature-content/public-backend isolation.
