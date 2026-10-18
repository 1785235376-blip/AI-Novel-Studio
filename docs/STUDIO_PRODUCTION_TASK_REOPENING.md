# Original Studio production tasks in the independent Tasks workspace

The independent Tasks workspace now includes a read-only list of original Studio image/video production jobs. It reuses StudioProductionClient list/get and existing decoders. It is not a second queue or a generic experimental task adapter.

An explicit open performs an owner/id-specific GET and compares the complete selected receipt, including version and request digest, before handing the validated job to the existing StudioMediaExecutionPanel externalJob path. A changed receipt requires a fresh list and new explicit choice. No auto-execution, input replacement, candidate read, review or cancellation is added.

The original shell navigation retains dirty-input confirmation. The handoff lease is rechecked after any delayed decision. Scope/identity/branch, current client, source version, busy state, list refresh, newer selection, permission changes and unmount invalidate old handlers. Metadata uses existing overflow-safe task list markup. Other task owners and Graph runs remain outside this bounded new projection.

Evidence: u07-studio-task-reopening-final-metadata records 100 focused tests; an intermediate StrictMode initial-read failure is preserved in u07-studio-task-reopening-fences. Root audio-studio-tasks-final records final combined 134 tests, TypeScript, Vite production build and UI token guard on the stable shared source. Actual mounted workspace tests exercise image/video opening, unchanged author input, changed receipt rejection, dirty-navigation cancel/confirm, newer selection and project/host round trips. These are jsdom/transport-fixture checks, not actual browser/provider acceptance. No new backend endpoint or authorization owner is introduced.
