# Independent Audio sample-peak normalization review

Verdict: PASS for the bounded PCM16 WAV feature, not full Audio acceptance.

Baseline: e1e66cedeb7a140b6894850bc21a1e5ac7e06c16. Isolated worktree: studio-audio-normalize. Six production files changed; existing tests and prior fixtures are unchanged. Review made no product edits, installations, commits, pushes, or merges.

## Design and source review

Original StudioAudioExecution remains execution owner, with original durable Job, source authority, Candidate, explicit Review, receipt, and UNKNOWN reconciliation. No provider or alternate engine was introduced. Normalization is optional and standalone only. The exact selected PCM16 source frames supply a shared absolute sample peak across channels; unseeked FFmpeg atrim sample indices process the same range. Fractional frame boundaries and rate/channel conversion are rejected. Combined double-precision normalization/manual volume avoids intermediate integer clipping; original fades follow. Legacy normalization-absent arguments and serialization are preserved.

Target is explicitly before manual gain and fades, bounded -24 to -1 dBFS; correction is bounded -60 to +12 dB and digital silence is rejected. Target plus manual gain cannot exceed -1 dBFS. Final actual WAV samples, frame count and PCM hash are measured. Persisted proof validates finite arithmetic, source hash, frame counts, output ceiling and, without fades, target within one S16 LSB. Fades can lower the final peak. This is neither LUFS nor true-peak processing. FLAC/MP3 normalization is explicitly unsupported; their existing paths remain available without normalization.

Pre-edit serialization capture was reviewed before runtime edits. Seven variants cover omitted controls, gain/rate/channels, FLAC, versioned MP3, Graph, zero fade and positive fades. Fixture SHA256: d818680bf5895014cd400671d5ed95d3ca61a8886cec4e58c2f8dfcc0c4dcc16. Capture uses actual original serializer/preview/body/binding/receipt methods with documented fixed collaborators and constructed QUEUED receipt; it is not lifecycle evidence.

## Independent execution

- Backend: 171 passed, 48 PostgreSQL deselected. All three new modules plus original fade contract and MP3 compatibility. Includes real CPU output, asymmetric stereo, full-scale negative input, louder discarded regions, exact 44.1 kHz boundaries, manual gain/fades, silence/boost rejection, low-level quantization, immutable proof/reopen, cancellation, source changes, Host revoke/ABA and UNKNOWN non-replay.
- Frontend: 170 passed in four suites: new peak (23), original fade, WAV contract and MP3 contract.
- Fresh clean-Python startup and original-runner PathFinder probes before/after passed.
- All nine primary and four independent receipts share the same complete 2590-path source snapshot, unchanged before/after and matching current files. Every receipt and raw-log hash was audited. Original tests remain immutable.
- Primary evidence additionally records new backend 95, legacy backend 268, frontend 360 in 15 suites, forced TypeScript, build, design tokens and origin checks passing. Counts overlap and must not be added.

Machine-readable closure: independent-evidence-index.json. Tests use owned isolated File profiles and tiny synthetic fixtures; no paid/provider/model invocation.

## Limits

No PostgreSQL, browser visual/geometry, Windows DesktopHost, packaging, real models/providers, subjective audio quality, LUFS, or true-peak acceptance. Existing known Audio listing failures are outside this selected scope; no claim of full repository pass. Parent owns any subsequent commit/local integration and must rerun integration checks against its resulting source tree.
