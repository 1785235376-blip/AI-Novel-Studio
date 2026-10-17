# Explicit updated-source independent Graph draft

A saved Director or Storyboard planning node with a STALE reference now offers an explicit current-source metadata read. The user sees the old/new versions and digests, confirms that particular inspected version, and prepares a separate unsaved Graph draft. Only the selected node's pin changes. The source document identity and mode must match; the revision must increase and its digest must differ.

The original graph and history stay untouched. All other node parameters, connections, groups, notes, camera and author content remain in the new draft. Other references are not refreshed; downstream ancestry/compatibility is not fabricated. No model call, Graph run, automatic save or old review/run authority is inherited. The original explicit Save creates the new graph and rechecks current authority, references, quotas and request identity. Original uncertain-create handling remains in force.

The existing controller owns the transition. Its original independent-draft transition is shared, not replaced by a second store or engine. Identity, mutation authority, live locks, selected node, navigation, full draft and source transitions retire the inspected intent, including A-to-B-to-A. Delayed reads are aborted/ignored and cannot unlock a newer request. Consent is bound to one inspected result and consumed synchronously.

Primary checks on the final candidate: 450 frontend cases in35 files, forced TypeScript, production Vite and the original token guard pass.32 new cases cover transformation, consent, stale metadata/reads, ownership/selection/edit epochs, duplicate action, the mounted inspector and original Save/create.71 focused cases overlap this450 total. Existing tests and backend guards are unchanged.

Separate real native File and PostgreSQL process smoke checks use the original full app lifespan, one-shot packaged trust bootstrap and actual HTTP owners. They create an old graph, edit its source, explicitly create a separate current-pin graph, then completely restart and reopen both; old graph/history remain unchanged and neither graph acquires a run. These manual-content HTTP checks do not execute the React UI or model. Mocked React and native owner evidence are separate, not a claimed browser E2E.

The first new-test failure used a Vitest matcher unavailable in the installed version. The second exposed an incorrectly shaped it.each argument table: its nominal39 passes do not establish the intended negative payload cases. Both failures are retained; the corrected object-wrapped table is covered by final71/450 runs. No original assertions or gates were weakened. Independent-agent review was unavailable; this is primary review and scoped testing.

Actual browser/visual interaction, live model quality, Windows installer/GPU and complete V2 acceptance remain open. PG private model-review persistence remains unsupported; this manual Graph fork does not change that boundary.
