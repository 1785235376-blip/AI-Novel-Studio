# M4 Windows V2 Host profile: cloud verification

Base: `a40df1156a3aaafd88668b11c4bee647ba9330ad`.

**Implementation verified in cloud; native Windows integration remains NOT_RUN.**
This is a bounded explicit V2 package configuration and separate Windows
credential namespace. It does not complete M4, GPU/model acceptance, or release
acceptance. No native launcher, model runtime or credential store was exercised.

## Change and original owners

`--profile v2` / `-LaunchProfile v2` selects a fixed, server-owned profile.
Default paths, feature values and vault targets retain the original contract.
V2 uses the original process factory, PostgreSQL, lifecycle, data stores,
bootstrap registry and C# WebView2 Host. The package sets the five required
flags explicitly; inherited wildcard/other feature values cannot expand it.
`V1_ACCEPTANCE_MODE` is propagated unchanged and disables the experimental
features through the existing server gate while retaining V2 data isolation.

V2 Windows credentials have the fixed separate
`AI-Novel-Studio-V2/provider/` target prefix. Missing/failing reads never fall
back to V1, keyring or memory. Unknown selectors, injected backends and unsafe
fallback configuration fail before access. Existing V1 credentials are not
read, enumerated, migrated or deleted. The launcher no longer imports the vault
merely to obtain a pure framing helper before it has selected the backend
profile; the existing control-pipe credential owner itself remains unchanged.

V2 roots also bind the original identity and provider-sidecar owners. Existing
symlinks, reparse points and regular hard links are rejected with bounded,
streaming state validation. Only the exact original executable-only PostgreSQL
junction for Unicode installations is permitted, with fixed path/digest/type
and exact installed target checks. Same-base roots are scanned once. The V2
Host process receives its explicit owned WebView2 data directory instead of an
inherited override. No C# Host, session/bootstrap, flag-registry or authorization
implementation was changed.

Detailed launch instructions and the trusted-Application, OS-account,
filesystem-race and synchronous-I/O limitations are in
[`docs/v2/packaged-launch-profile.md`](docs/v2/packaged-launch-profile.md).

## Verification matrix

- Final new-profile plus original package/vault/Host-authority regression:
  **385 passed, 3 skipped**. The skips are two existing PostgreSQL-only cases
  and the original manual Windows Credential Manager integration case.
- Final original M4 execution/graph/adaptation/authority selection:
  **632 passed, 285 existing PostgreSQL skips**, with no source drift. An
  earlier successful run overlapped a source edit and is retained as
  development evidence rather than final source-bound proof.
- Three new files add **135 collected test cases**. Existing test files remain
  byte-identical to the base. The Windows cases use real ctypes records with
  fake API functions; they are not native Windows ABI or vault evidence.
- Two complete collections using the unchanged generator are identical:
  **12,294 nodes**, versus 12,159 at the parent. All prior nodes retain their
  order; historical skip maps and external gates are unchanged. Collection is
  inventory only, not successful full-suite execution.
- Frozen V1 manifest SHA256 remains
  `6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262`.
  Only the separate generated V2 inventory is refreshed.
- Python parsing and `git diff --check` pass. A read-only review found no
  remaining blocking issue after the import, alias, WebView and Unicode-path
  corrections. The original tests and gates were not weakened.

Source-bound logs, manifests, inventory comparisons and preliminary failure
receipts are preserved losslessly under `docs/delivery/v2-development/`; the
evidence index records raw/compressed hashes and distinguishes intermediate
source drift. Test selections overlap; their counts must not be summed.

## Native handoff and remaining gates

The Windows child must build the exact reviewed revision using SDK 8.0.424 and
the existing package pipeline, then launch the explicit V2 profile with owned
roots. Before model work, verify real bootstrap readiness, actual WebView2 and
credential targets, unchanged V1 state, Chinese-path startup, controlled close,
restart and session invalidation. No operating-system vault fallback is allowed.

The first intended real model is the separately verified existing Qwen3.5-9B
Q4_K_M. Select, validate and register it through the original Model Center;
review one bounded local request before dispatch. This profile performs no
automatic model startup, credential import, inference or cloud dispatch.

Native PowerShell/WebView2, Windows vault, PostgreSQL runtime, CUDA, inference,
literary quality and end-user interaction remain unverified by this report.
No public release, merge, PR-body update or publication occurred in this task.
