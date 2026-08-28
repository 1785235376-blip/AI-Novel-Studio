# V1.0 Target Release Checklist

> 当前产品声明为 `0.7.0 Beta`。本文件是未来 V1.0 的目标发行门禁，不是 V1.0 发布声明或通过证明。当前发行结论为 `BLOCKED`。

This checklist records evidence requirements, not implementation inventory. Merging a pull request does not pass a release gate. Every unchecked item remains unverified, and every release or DesktopHost result must use the current release candidate, current WinExe, and current evidence. Browser, API, Playwright, and startup-only evidence cannot replace real DesktopHost window business evidence.

## A. Release Candidate Identity

- [ ] Record the exact main or release commit and independently verify it before building.
- [ ] Verify that backend, frontend, package metadata, release notes, and tag use the same approved version.
- [ ] Verify that the source worktree is clean and contains only reviewed commits.
- [ ] Rebuild the package from that exact commit in a clean environment.
- [ ] Record a fresh checksum for every current release artifact.
- [ ] Confirm that no old staging directory, package hash, screenshot, log, or acceptance conclusion is reused.

## B. Clean Regression

- [ ] Run the complete backend suite in a clean and reproducible environment.
- [ ] Run the complete frontend suite.
- [ ] Run TypeScript typecheck and the production frontend build.
- [ ] Run repository whitespace and diff validation.
- [ ] Confirm that the release candidate introduces no new failure.
- [ ] Record every remaining baseline failure with owner, severity, evidence, and disposition.
- [ ] Confirm that no failure was hidden by `skip`, `xfail`, test deletion, assertion weakening, or reduced suite scope.
- [ ] Record commands, environment boundaries, and artifacts without hard-coding transient test counts in this checklist.

## C. E2E Database Isolation

- [ ] Require an explicit `E2E_DATABASE_URL`; do not read `.env` and do not fall back to a generic `DATABASE_URL`.
- [ ] Require the database name to match `ai_novel_studio_e2e_[a-z0-9_-]{1,42}`.
- [ ] Allocate a unique database name for every parallel run or CI job.
- [ ] Require `E2E_DATABASE_CONFIRM_DROP` to match the exact database name before destructive setup or cleanup.
- [ ] Reject target-overriding query keys before any connection, including encoded or case-variant forms.
- [ ] Keep the DSN, username, password, host, and query out of commands, logs, reporters, snapshots, and error messages.
- [ ] Make fixture setup, probe, and cleanup fail closed; a cleanup failure must fail teardown.
- [ ] Verify that fixture, backend, and frontend subprocesses receive only their minimum required database environment.
- [ ] Run the real PostgreSQL and Playwright integration without silently skipping its database scenarios.
- [ ] Verify Windows PowerShell and CI propagation using the same isolation contract.

## D. PostgreSQL And Data Recovery

- [ ] Run parity tests against a newly provisioned, explicitly owned real PostgreSQL instance.
- [ ] Apply all migrations from a clean baseline and verify their checksums.
- [ ] Verify concurrency, transaction, idempotency, and rollback boundaries.
- [ ] Create and verify a backup of representative test data.
- [ ] Restore that backup into a new isolated instance and verify data integrity.
- [ ] Exercise migration, startup, transaction, backup, and restore failure recovery.
- [ ] Prove that no user production database or user source-data directory was read, changed, or deleted.
- [ ] Verify PostgreSQL composition and repository wiring independently; durable sidecar tests are not evidence for this gate.

## E. Credential And Provider Lifecycle

- [ ] Reject unknown Provider IDs before any credential backend access and return the stable unsupported-Provider API contract.
- [ ] Verify compatibility for static Providers, including text/runtime and other static catalog or runtime-registry sources.
- [ ] Verify dynamic persisted Provider lifecycle only for asset, audio, and video JSON sources; do not claim that this proves an equivalent dynamic persisted text/runtime configuration.
- [ ] Clear credentials before deleting Provider configuration or its final registry source.
- [ ] If credential cleanup fails, fail closed and retain Provider configuration and registry sources.
- [ ] If the vault is degraded, reject persistent credential cleanup rather than reporting a memory-only clear as success.
- [ ] Verify that shared credentials remain while any Provider source still references them.
- [ ] Use an explicit memory backend and OS-access guards for ordinary automated tests.
- [ ] Run real Windows Credential Manager integration only as a separately authorized, isolated gate.
- [ ] Confirm that no real secret is read, returned by an API, written to the repository, or emitted in logs.

## F. Durable Research Sidecar

- [ ] Verify File sidecar persistence across a service restart.
- [ ] Verify novel isolation, revision conflict/409, deletion, and path-traversal protection.
- [ ] Verify creation and listing provenance report `external_fetch=false` without external network access.
- [ ] Describe File and PostgreSQL profiles truthfully as using the durable sidecar boundary.
- [ ] Keep PostgreSQL composition and runtime wiring as a separate, independently executed integration gate.

## G. Text, Chat, And Video Fail-Closed Behavior

### Text Generation

- [ ] Without a configured real text Provider, require the generation job to end as `FAILED`.
- [ ] Return a structured public `error_code` of `TEXT_PROVIDER_NOT_CONFIGURED` and a safe user-facing message.
- [ ] Reject Accept for failed drafts.
- [ ] Confirm that a mock Provider is never identified as DeepSeek or another real Provider.

### Controller Chat

- [ ] In packaged runtime without a configured text Provider, return a stable HTTP 503.
- [ ] Return no fabricated model response or model identity.

### Video

- [ ] Without a configured video Provider, keep the Motion Task at `PENDING` with `progress=0` and `error=VIDEO_PROVIDER_NOT_CONFIGURED` after creation and execution attempts.
- [ ] Record an execution-attempt history entry with `status=PENDING` and `phase=PROVIDER_MISSING`; do not reinterpret this contract as `FAILED`, `SUCCEEDED`, active generation, or another terminal state.
- [ ] Make no real video Provider request and produce no successful or `placeholder://` artifact.
- [ ] Do not report a deterministic placeholder Provider as a healthy real Provider.
- [ ] Require a saved non-empty Motion Prompt and valid, traceable first- and last-frame references.
- [ ] Verify that UI and task state display the stable configuration error without implying success or active generation.

## H. Agent Honesty

- [ ] Require deterministic Agent tasks to terminate only as `VALIDATED`.
- [ ] State explicitly that contract validation did not call a model and report `model_called=false`.
- [ ] Expose no review or apply action for deterministic validation.
- [ ] Do not present an empty deterministic result as completed creative work.
- [ ] Exercise the real-model review/apply path separately with authorization and verify its existing contract.

## I. Windows Package And DesktopHost

Use the [DesktopHost Window Acceptance Checklist](desktop_host_acceptance_checklist.md). Its current DH-01 through DH-08 results are `NOT_RUN`, so this gate remains `BLOCKED`.

- [ ] Rebuild the current WinExe from the exact release candidate and record its checksum.
- [ ] Verify package installation, startup, normal exit, uninstall, and owned-resource cleanup.
- [ ] Verify loopback-only listeners and an isolated WebView2 profile.
- [ ] Verify logs, screenshots, and exported evidence contain no sensitive information.
- [ ] Complete DH-01 through DH-08 on the same release candidate with current window evidence.
- [ ] Establish and validate the GitHub Actions release contract.
- [ ] Establish and validate a standard PowerShell/package E2E entry point.
- [ ] Independently prove the p0 Playwright database semantics on the supported Windows environment.

## J. Real Provider Authorization

- [ ] Obtain explicit authorization before any real Provider request.
- [ ] Record the approved Provider, model, quota, request count, test-data boundary, and log-redaction plan.
- [ ] Use isolated non-user test data and the minimum number of requests.
- [ ] Keep real credentials out of the repository, `.env`, commands, URLs, logs, screenshots, and reports.
- [ ] Keep this gate `NOT_RUN` when authorization is absent; a mock result cannot substitute for it.

## K. Release Decision

- [ ] Confirm that open P0 and P1 release blockers equal zero.
- [ ] Record every approved exception with owner, risk, expiration, and explicit sign-off; do not waive security, data integrity, credential, or DesktopHost gates.
- [ ] Confirm that DH-01 through DH-08 all pass on the same current release candidate.
- [ ] Confirm that backup and restore verification passed on isolated representative data.
- [ ] Record the current package identity and checksum.
- [ ] Verify release notes, version metadata, commit, and tag consistency.
- [ ] Record explicit approval by the accountable release owner.

Unless every mandatory gate above is satisfied with current evidence, the release decision remains `BLOCKED`.

## L. Rollback And Data Protection

- [ ] Stop the affected service and record the operator, time, reason, and observed state.
- [ ] Restore the latest independently verified backup into the approved target.
- [ ] Roll back to the previous trusted package and verify its checksum.
- [ ] Rotate credentials when exposure is possible, without recording their values.
- [ ] Do not delete a source-data directory or overwrite a user database during rollback.
- [ ] Verify restored data and service behavior before reopening access.
- [ ] Record the rollback result, remaining risk, and follow-up owner.
