# Audio listing inventory closure

Source/evidence checkpoint: 25742db. The unchanged original generator ran three complete unfiltered collection passes. Review, candidate and confirmation raw bytes match exactly, SHA256 308d06729f829499f97db5a8fd41839e8705e12b4eb38612ef530e7254e29a8c.

Canonical V2 SHA256: 80251092a5d769650dd2e2000625e2560ad1bdc776b54792898ca37d30419e4c. There are 17,505 rows and 2,718 source entries. All 17,498 predecessor full rows, order and backend classes remain exact; seven new File-only regression rows were added. The sole changed predecessor source is app/services/studio_audio_execution.py. Every candidate source hash matches its committed Git blob; all old tests, gates and historical skip policies remain unchanged. Frozen V1 is untouched.

Primary audits preceded separate candidate generation and exact-byte promotion. Independent review is unavailable and is not claimed. The unchanged coverage/runner tools had 45 self-tests pass in the immediately preceding Director closure; those tool bytes remain exact, and no fresh 45-test rerun is claimed here. Collection adds no executed or passing-test claim.

Actual scoped runtime evidence is in ../audio-listing-precedence-20261017 and AUDIO_LISTING_DIAGNOSTIC_PRECEDENCE.md. The five original Audio listing failures were reproduced without changing tests, then all original selected cases passed alongside new immutable-binding regressions. Browser, PostgreSQL and whole-product acceptance remain separate.
