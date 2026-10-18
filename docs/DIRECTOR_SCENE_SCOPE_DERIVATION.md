# Source-pinned scene sub-Director drafts

2026-10-18. Adds selected-scene derivation to the original Creative document derive owner and existing Director Console. This closes a bounded part of distinct sub-Director responsibility; it is not a new agent, workflow engine or privilege role.

## Behavior

After reading a saved Director document and its exact digest, the user enters a responsibility label, selects one or more existing scenes and explicitly confirms creation of one separate DRAFT Director document. The original derive transaction validates source version/digest, scope and current authority, copies only selected scenes and their existing Director notes, and records the exact parent document snapshot plus responsibility/scene IDs in derivation provenance. Original scene order, IDs, text and notes are preserved; unrelated scenes and notes are excluded. Relevant chapter bindings are retained. The new draft remains tied to the original parent source lifecycle.

The responsibility label describes authored division of work; it does not grant permissions or impose a permanent execution policy. The initial document contains the selected scene subset. Later author edits still use normal Creative validation and source guards. No parent approval, model call, job or graph binding is copied. Subsequent storyboard derivation uses the same original service and only the selected scenes in this new draft.

The mounted Console keeps parent authoring and graph navigation dirty fences active while a child-creation intent is pending. A successful result is displayed without automatically replacing the parent or inserting a graph node. The user can explicitly read the new original document, then use the existing document catalog/node binding workflow. A lost/invalid creation response is held as uncertain; the UI cannot automatically retry. The user must inspect the original directory before explicitly clearing the local intent.

## Evidence

- File: 15 passed / 15 deselected; real PostgreSQL: 15 passed / 15 deselected. Original SCRIPT→SCREENPLAY derivation regressions included. Cases cover selected-scene save/reopen, original unchanged, downstream storyboard derivation, malformed/stale scope rejection without writes, final authorization rollback, parent-change invalidation and mounted HTTP write permission. PostgreSQL reused disposable UTF-8 OID 16384 and stopped cleanly.
- UI final suite: 39 passed, TypeScript and Vite production build passed, shared UI token guard passed. Additional test-only mounted/transport suite: 7 passed plus TypeScript. It verifies original captured authenticated derive transport and actual Console parent dirty lock/create/explicit reopen, rather than only a detached form.
- The first UI suite genuinely exposed duplicate submission through a retained callback after an uncertain response. The form now synchronously consumes the confirmed intent token and checks live consent/availability. The original failing assertion is retained and passes; failure logs are preserved.
- API/catalog and actual public wheel check recorded in director-scene-scope-public. No new API operation is added; the existing derive request gains the explicit Director scope variant.

## Limits

This is source-bound authoring and duplication, not autonomous responsibility delegation, camera/sound/budget control-node execution, cross-project copying, automatic approval or complete professional Console acceptance. Original derive persistence is reused; no server idempotency guarantee is inferred merely from a request header. Real browser visual/end-to-end and Windows acceptance remain pending. Runtime tests use synthetic authored documents, not real-model quality evidence.

Public/catalog checks: 6 passed. API count 2375; backend fingerprint `bc94b8833ed4f03b20d5566a9d9954b3c4ad8a179ee4625b00248fbe5fc24fa4`. Test wheel is not a Release.
