# Final frozen-source review

Reviewed 2026-10-07 against PR45 `665817243cad59eef0d4140f17c2ea644f46971e`, branch `work/full-recovery-product-candidate`. This is a read-only source review; no product source or test expectation was edited.

`git diff --check` passes. A scan of 2837 tracked/non-ignored candidate files, including decompressed gzip evidence, found zero matches for the current ignored development-session credential and zero read failures; its value is neither printed nor retained here.

The Design System, protected-surface and visual-baseline documents, UI tokens, Playwright visual configuration, `suite_coverage.py`, `coverage_reconcile.py` and `postgres_gate.py` are byte-identical to PR45. The screenshot tolerance remains `maxDiffPixelRatio: 0.015`. Original frontend unit files and skip rules are preserved. All 19 original visual expectation lines remain in order, with fixture/navigation and additive geometry exceptions explicitly documented; exactly two retired Windows golden images are archived and migrated with original RED evidence. These migrated gold files are not described as unchanged original passes.

At review time the coverage manifest was the earlier 9140-node/802-source inventory, with twelve source digests already differing from the candidate. **Regenerate the complete manifest before claiming final-source Linux/package/hosted coverage.** Its original 9116-node relative order and original skip dictionary remain intact. Generated untracked `tests/fixtures/.workspace-mutation-locks/` and `tests/fixtures/novels/sample_novel/chapter_identity.json` should be kept out of the commit. The controlling agent is performing the final inventory and clean-source verification; this review does not substitute an older fingerprint for that result.

Live GitHub checks confirm Actions is enabled and the Cloud CI workflow blob matches the frozen PR45 source (`331158d667074e356761b0dfa37cbb8c6cb092a2`). Both `main` and the planned stack base `work/feature-completion-surface-freeze` are unprotected; repository rulesets are empty and the base protection endpoint returns 404. Thus the following are expected workflow checks, **not GitHub-enforced required checks** at review time:

| Workflow | Checks expected for a new Draft PR targeting PR45 |
| --- | --- |
| Cloud CI | Backend execution / file / shard 0; Backend execution / postgres / shard 0; Backend execution / postgres / shard 1; Backend / file; Backend / postgres; Frontend / unit-type-build-tokens; Windows / Host compile and native contracts; Windows / Fresh base and acceptance package |
| Local Interop V1 | Protocol and local transport / file; Protocol and local transport / postgres; Windows current-user pipe reference (MOCK_ONLY) |
| Shared R123 evidence | Original c6f2126 RED / Python 3.12.9; preservation of historical reproductions, not candidate-product acceptance |

Cloud CI and Local Interop have unrestricted push/pull-request triggers and no Draft exclusion. Shared R123 runs on pull requests. The A43 workflow's target-branch filter excludes the planned PR45 base; Post-Interop recovery has a different branch/path-only push trigger. Cloud CI uses Python 3.12.9, PostgreSQL16, locked Python constraints, Node22.14.0/pnpm10.6.5, .NET8.0.424 and unchanged strict collection/JUnit/source-digest reconciliation. Its synthetic provider environment is explicitly separate from the real Qwen product acceptance.

The existing checkout uses the PR merge revision by default. PR receipts must identify that checked-out/event SHA, while push receipts identify the actual head SHA; neither should be labelled as the other. A conflict prevents the pull-request trigger. These event and merge-revision semantics are supported by [GitHub's workflow event reference](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request).

Source-byte fingerprints also need a clean-checkout/archive comparison: this checkout has `core.autocrlf=input` and no `.gitattributes` EOL guarantee, so a Windows checkout that applies CRLF conversion can differ from the Linux Git archive even with the same commit. Keep the strict digest check and record actual head/tree/manifest/working-source identity after staging; do not loosen it to accept a mismatch. No new hosted run is claimed before the candidate commit is pushed.
