# DesktopHost Window Acceptance Checklist

> This is a repeatable operating template, not an acceptance report. The current product claim is `0.7.0 Beta`, not a V1.0 release. DH-01 through DH-08 are currently `NOT_RUN` and the DesktopHost gate remains `BLOCKED`. This documentation change executes and proves no DesktopHost window acceptance.

Only evidence collected from the current release candidate and its freshly built WinExe is valid. An old build, old screenshot, browser session, API test, Playwright run, or startup-only screenshot cannot substitute for current DesktopHost window evidence. Merging a pull request does not pass this gate.

## Result Values

Every step must use exactly one result:

- `PASS`: the step was completed on the current release candidate and has complete evidence.
- `FAIL`: the observed result violated the expected contract.
- `BLOCKED`: a prerequisite or environment prevented execution.
- `NOT_RUN`: the step has not been executed.

## Current Gate Status

| Step | Scope | Initial result | Evidence |
| --- | --- | --- | --- |
| DH-01 | Startup and visible window | `NOT_RUN` | None |
| DH-02 | Project overview | `NOT_RUN` | None |
| DH-03 | Research records | `NOT_RUN` | None |
| DH-04 | Restart persistence | `NOT_RUN` | None |
| DH-05 | Deterministic Agent honesty | `NOT_RUN` | None |
| DH-06 | Missing video Provider | `NOT_RUN` | None |
| DH-07 | Single instance and cleanup | `NOT_RUN` | None |
| DH-08 | Logs and sensitive information | `NOT_RUN` | None |

## Run Metadata

Complete these fields only when executing the checklist:

| Field | Value |
| --- | --- |
| Main commit | `<CURRENT_MAIN_SHA>` |
| Release candidate | `<RELEASE_CANDIDATE_VERSION>` |
| Build SHA-256 | `<CURRENT_BUILD_SHA256>` |
| Operator | `<OPERATOR>` |
| Started at | `<ISO-8601>` |
| Runtime directory | `<RUNTIME_PATH>` |
| Database profile | `<DATABASE_PROFILE>` |
| DesktopHost PID | `<DESKTOP_HOST_PID>` |
| Backend PID | `<BACKEND_PID>` |
| Database port | `<DATABASE_PORT>` |
| Screenshot directory | `<SCREENSHOT_PATH>` |
| Log directory | `<LOG_PATH>` |

## Isolation And Safety Preconditions

- [ ] Rebuild the WinExe from the exact current release candidate source.
- [ ] Use a new isolated runtime directory, WebView2 profile, and test database.
- [ ] Do not read or modify the developer `.env` or any user production database.
- [ ] Do not use real credentials unless a separate authorization identifies the Provider, model, quota, test data, and logging boundary.
- [ ] Restrict every listener to loopback and record its owning process and port.
- [ ] Record the commit, build hash, time, DesktopHost/Backend/PostgreSQL PIDs, request IDs, and entity IDs.
- [ ] Redact credentials, tokens, passwords, DSNs, and user data from screenshots and logs.
- [ ] Define cleanup ownership before launch; never terminate unrelated processes.
- [ ] After execution, verify owned processes, ports, named mutex, WebView2 profile, and temporary runtime cleanup.
- [ ] Preserve all user source data and never delete a user data directory as cleanup.

## DH-01 - Startup And Visible Window

Start the freshly built current WinExe and verify through the real DesktopHost:

- The application window is visible.
- WebView2 initialization, bootstrap, and application readiness complete.
- Backend and database processes start as required by the selected profile.
- All listeners are loopback-only.
- The real window screenshot, PIDs, ports, logs, and exit code are recorded.

A startup screenshot proves only DH-01. It cannot prove DH-02 through DH-08.

## DH-02 - Project Overview

In the real window, select a test novel and verify:

- Chapter and word counts.
- Character, location, timeline, foreshadowing, rule, and research counts.
- Writing goals, pending items, and recent activity.
- The response reports `placeholder=false`.
- Switching novels does not expose another novel's data.
- Unavailable capabilities are not presented as connected or complete.

Record the window screenshot, novel ID, request ID, and a redacted response summary.

## DH-03 - Research Records

### Real Window Evidence

In the real window, exercise create, filter, edit, stale revision conflict/409, delete confirmation, delete, and novel isolation. Verify that provenance and list results report `external_fetch=false`. DH-04 separately verifies restart persistence.

### Independent Service Contract Evidence

Use isolated service or API contract evidence to verify that path traversal is rejected, the sidecar remains within its configured root, and no external fetching occurs. Confirm that File and PostgreSQL profiles continue to use the durable sidecar boundary. Sidecar contract evidence does not prove PostgreSQL composition or runtime wiring; that remains a separate integration gate.

Service or API evidence supports non-window boundaries such as path safety, but cannot replace real-window evidence for CRUD, stale revision conflict/409, delete confirmation, deletion, or novel isolation. Do not present a path-safety service test as a DesktopHost window operation.

## DH-04 - Restart Persistence

Keep one research record, close all owned processes normally, and restart with the same isolated business-data directory. Verify that content, revision, and novel ownership survive. Record before-and-after evidence, then verify that no owned process, port, named mutex, or temporary runtime residue remains after final shutdown.

## DH-05 - Deterministic Agent Honesty

Run a deterministic Agent task and verify:

- The terminal status is `VALIDATED`.
- The UI explicitly states "契约校验，未调用模型" or an equivalent unambiguous message.
- The evidence reports `model_called=false`.
- No review or apply action is available.
- An empty result is not presented as completed creative output.
- No real model request occurs.

The real-model path requires separate authorization and evidence; it cannot be represented by this deterministic check.

## DH-06 - Missing Video Provider

Prepare a valid novel, screenplay, shot, storyboard, and unlocked transition. Save a non-empty Motion Prompt and use valid, traceable first- and last-frame asset references. Leave the video Provider unconfigured.

From the real window, create and inspect the Motion Task:

- Record the task and transition IDs.
- Verify that the UI task list refreshes.
- Record the actual state immediately after task creation: `status=PENDING`, `progress=0`, and `error=VIDEO_PROVIDER_NOT_CONFIGURED`.
- Attempt execution and record the resulting state. It must remain `PENDING` with `progress=0` and `error=VIDEO_PROVIDER_NOT_CONFIGURED`.
- Verify that task history adds an entry with `status=PENDING` and `phase=PROVIDER_MISSING`.
- Verify that the task does not enter `FAILED`, `SUCCEEDED`, or another terminal state.
- Verify that no real video Provider request, successful artifact, or `placeholder://` artifact occurs.
- Verify that a deterministic placeholder Provider is not described as a healthy real video Provider.
- Do not describe this error-bearing `PENDING` state as task success, active generation, or terminal failure.

## DH-07 - Single Instance And Resource Cleanup

Run at least two complete start/close cycles and verify:

- No `SingleInstanceError` occurs.
- The named mutex is released after each close.
- Owned DesktopHost, Backend, and PostgreSQL processes exit.
- Their ports are released.
- No unrelated process is terminated.
- Each cycle records PIDs and exit codes.

## DH-08 - Logs And Sensitive Information

Inspect only the logs created by this acceptance run. Verify that they contain:

- No API key, password, token, complete DSN, or credential.
- No successful `placeholder://` artifact.
- No unhandled exception.
- No record that presents a mock or deterministic Provider as a real Provider.

Record only redacted log locations and scan results. Do not inspect developer historical logs.

## Per-Step Evidence Template

Create one record per step. Replace placeholders only with current-run, redacted evidence.

```json
{
  "step_id": "<DH-STEP-ID>",
  "result": "NOT_RUN",
  "blocked_reason": "<BLOCKED_REASON_OR_EMPTY>",
  "timestamp": "<ISO-8601>",
  "operator": "<OPERATOR>",
  "main_sha": "<CURRENT_MAIN_SHA>",
  "build_sha256": "<CURRENT_BUILD_SHA256>",
  "desktop_host_pid": "<DESKTOP_HOST_PID>",
  "backend_pid": "<BACKEND_PID>",
  "database_port": "<DATABASE_PORT>",
  "entity_ids": ["<REDACTED_ENTITY_ID>"],
  "request_ids": ["<REDACTED_REQUEST_ID>"],
  "screenshots": ["<SCREENSHOT_PATH>"],
  "log_locations": ["<LOG_PATH>"],
  "expected_result": "<EXPECTED_RESULT>",
  "actual_result": "<ACTUAL_RESULT_OR_NOT_RUN>",
  "cleanup_result": "<CLEANUP_RESULT_OR_NOT_RUN>"
}
```

## DesktopHost Gate Decision

| Step | Final result | Evidence reviewed by |
| --- | --- | --- |
| DH-01 | `NOT_RUN` | `<OPERATOR>` |
| DH-02 | `NOT_RUN` | `<OPERATOR>` |
| DH-03 | `NOT_RUN` | `<OPERATOR>` |
| DH-04 | `NOT_RUN` | `<OPERATOR>` |
| DH-05 | `NOT_RUN` | `<OPERATOR>` |
| DH-06 | `NOT_RUN` | `<OPERATOR>` |
| DH-07 | `NOT_RUN` | `<OPERATOR>` |
| DH-08 | `NOT_RUN` | `<OPERATOR>` |

Any `FAIL`, `BLOCKED`, or `NOT_RUN` result keeps the DesktopHost gate blocked. The gate may be marked passed only when all eight steps pass on the same release candidate with complete current evidence. Passing this gate does not by itself authorize a V1.0 release; every other release checklist gate must also pass.
