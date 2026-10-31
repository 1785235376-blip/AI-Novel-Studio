# Portable independent AudioAsset history evidence

This packet belongs to `../../HERMIA_AUDIO_HISTORY_REVIEW_20261025.md`. It contains explicitly selected textual logs and full reviewer-owned probe sources, not runtime user data. It is evidence, not a default test-suite addition or merge approval.

## Exact source identities

- Reviewed delivery: `2acab55d2ef64ca76f2093e376bf6388af364282`.
- Implementation: `2e2fcb79209a3afc03dc7e443f5e1901ff233ee1`.
- Fixed baseline: `11d8615cccb688462ff814d025b339e1b6eb0efe`.
- Original main comparison: `4fd956e461d3632b55a3b7e84a7ab344b8abc91f`.
- Documentation destination was clean at `d070c9f6354b76a1594e388cb0825fb280933c63` before this packet was added. Tests were NOT rerun against d070 merely to package the report.

## Sanitization and provenance

Logs preserve original output except these literal machine-location substitutions:

- Original baseline checkout absolute prefix → `<BASELINE_ROOT>`.
- Original pinned review checkout absolute prefix → `<REVIEW_ROOT>`.
- Original main checkout absolute prefix → `<MAIN_ROOT>`.
- Relative main virtualenv prefixes → `<MAIN_VENV>`.
- Interpreter installation prefix → `<PYTHON_RUNTIME>`.
- Executor home prefix → `<EXECUTOR_HOME>`.

These are path placeholders, not user identifiers. Exact machine locations are intentionally not published. The source-to-public hash manifest preserves both original and sanitized artifact SHA-256 values. Because substitution changes bytes, public hashes are not claimed to be the hashes of the unmodified local originals.

No source trace, error, test assertion, count, timing, synthetic UUID, digest, or synthetic sentinel was redacted. `token-reader`, `token-no-grants`, `synthetic-private-prompt-sentinel`, the synthetic provider endpoint, and similar strings are test fixtures, not credentials or private user data. `results/promotion-report.json` contains only these generated fixture identities/results. No authorization.json, identity.json, project/media fixture tree, credential file, environment dump, cache, or database was copied.

All `.py` and `.sh` sources are stored with a final `.txt` suffix. They are not collected by default pytest and do not alter production/test discovery. The archived recorded shell scripts contain path placeholders and are provenance, not directly runnable recipes. Use the separate portable recipe below.

## Reproduction

Use an already authorized disposable detached worktree at the pinned delivery and an approved existing Python environment. Do not checkout/reset the active main tree. If GitHub access or environment access is denied, stop; this packet does not authorize an alternate credential/network route. Do not install dependencies automatically.

From a shell, define absolute paths suitable for your own environment:

```sh
export REVIEW_ROOT=/path/to/disposable-pinned-worktree
export REVIEW_PYTHON=/path/to/approved-existing-venv/bin/python
export BUNDLE_ROOT=/path/to/this/evidence-directory
bash "$BUNDLE_ROOT/reproduce.sh.txt" query86
bash "$BUNDLE_ROOT/reproduce.sh.txt" baseline3
```

The script verifies the pinned Git HEAD, materializes only the included probe sources into ignored `.runtime` paths, isolates all app/profile/temp locations, and verifies actual application module files. It uses File/mock settings, clears inherited environment variables and blocks socket connects/DNS in the common launcher. Baseline groups use a fixed `git archive` into their own tree; they do not fake-import baseline modules. No production source, original test assertion, or repository configuration is edited. Baseline archive generation needs the baseline Git object already available locally.

Groups and expected *historical* observations:

| Group | Original observation | Public log |
|---|---|---|
| initial60 | 60 passed, 3 warnings | logs/initial-60.log |
| query86 | 85 passed, 1 failed, 3 warnings | logs/query-all.log |
| baseline3 | 3 passed, 3 warnings | logs/baseline-query-3.log |
| owner13 | 13 passed | logs/owner-extra-corrected.log |
| source2 | 2 passed, 3 warnings | logs/query-source-probe.log |
| retained5 | 5 passed | logs/retained-accounting-probe.log |
| chain1 | 1 passed | logs/chain-orphan-probe.log |
| baseline1 | 1 passed | logs/baseline-retained-control.log |
| promotion1 | 1 passed, 3 warnings | logs/promotion-run-5.log |

These runs overlap. Do not sum them into a fictional unique-case total. `initial60` includes the delivery's 58 cases plus two cases also in `query86`; `baseline3` is a control on another tree. `retained5` excludes the later chain-specific case intentionally, matching the historical 5+1 run split.

The portable recipe was syntax-checked, and Python probe sources were parsed, when packaged. It was NOT executed and is not presented as a new test result. The recorded promotion run used a separate isolated shell command and an in-memory synthetic provider. Its replay uses the stronger common env-clearing/network-denying wrapper; this packaging change is not represented as the exact historical command.

## Honest failed-probe record

- `logs/owner-extra.log` and `sources/test_owner_independent_initial.py.txt`: a reviewer-owned probe wrongly treated an absent `parameters` field and `{}` as identical persisted metadata. Only that probe was corrected to repeat an already committed identical value. Original delivered tests were untouched.
- `logs/promotion-run-1.log`: initial executor-home isolation failure, before the successful isolated run.
- `logs/promotion-run-2.log` / `promotion-run-3.log`: missing feature setup in the reviewer probe.
- `logs/promotion-run-4.log`: reviewer incorrectly expected `SUCCEEDED`; the genuine completed-but-unreviewed state is `AWAITING_REVIEW`. Correcting this expectation did not remove any privacy/promotion assertions.
- `logs/promotion-run-5.log`: final successful real service publish/promote plus mounted history reads.

These earlier promotion revisions are visible through their original failure logs. Only the final full promotion source is available in this packet; no claim is made that the final source reproduces those earlier setup errors unchanged.

## Integrity

`SHA256SUMS.txt` hashes every packet file except itself. `results/source-to-public-hashes.json` records original/sanitized pairs for copied evidence. `PACKET_METADATA.json` records packaged source identities and static safety checks. The report is separately hashed by the parent when committing this documentation-only handoff.
