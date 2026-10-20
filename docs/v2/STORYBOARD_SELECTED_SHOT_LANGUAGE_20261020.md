# Selected-shot camera-language authoring: bounded closeout

Closeout base: `9b3506e3ea3de95d65285442242cdced7381e514`, preserving fixed
df07 and text-to-image work without changing either review branch. The seven
original files were frozen against `3c4dd726225e96719917e52f43f485c3f184e6b4`.
Their SHA-256 values and recovery ZIP were verified before restoring into this
new worktree. Tracked Canvas and Workspace base blobs at 3c4 and 9b3506 are
identical. This slice does not accept the whole historical SHOT-03 row or either
canvas layer. Template and PUBLIC acceptance retain their independent evidence.

## Behavior and original owners

The existing Canvas already supplies shot search/navigation, ordering and timing
tools. The collapsed batch control lets the author explicitly select current-scene
shots and set one of `shot_size`, `camera_angle` or `camera_motion`. Every selected
shot's identity and old/new value are shown before a separate confirmation. An
unchanged-only operation does not apply.

Every other field and array order remain exact: IDs, numbers, scene membership,
duration, prompts, camera geometry, continuity, director references, source/media
bindings and approval data. Other scenes are ineligible. The original limit of
200 shots and each field's 80 Unicode characters remain. Blank/whitespace-only
values are refused; nonblank text is preserved without silently trimming.

One confirmation invokes original `onChange` once. The original Save performs
validation and expected-version persistence; batch authoring never saves itself.
A before/after undo receipt works only while that exact result remains current,
dirty and writable in the same scene/version. Further edits, Save, busy/permission
transitions, owner changes and unmount retire it. No global history is added.

Selection, value/field changes and observable source, scene, version or authority
ABA retire old previews/callbacks. DOM-value and IME guards run before preview and
Apply. Owner changes remount text/select controls to reject old composition ends.

The real `CreativeWorkspace` supplies synchronous admission through its existing
draft refs, host authority and mutation lock. Original draft writes, mode/scene
transitions, director busy and production dirty changes advance an owner revision
before React commits. A view refresh keeps ABA observable when React coalesces
updates. Retained Apply/Undo compare that revision and the exact original Draft
object, preventing same-event author changes from being overwritten. Undo records
the revision after original `change()`. No second draft store, permission source,
history engine, provider, model call, automatic Save or task is introduced.

## Ownership and evidence

Seven original paths: `CreativeCanvas.tsx`, `storyboardShotBatch.ts`,
`StoryboardShotBatchTools.tsx`, their two additive tests,
`CreativeCanvas.shotBatch.additive.test.tsx`, and this note. Closeout also changes
original `CreativeWorkspace.tsx` and adds its real-owner additive regression test:
nine paths total. No stylesheet, AppShell, DSH/interaction, portable, recipe,
backend, public-build manifest or shared Graph owner changes belong to this slice.

Sibling `shot-batch-evidence-20261020` retains frozen source hashes, the recovery
ZIP and earlier checks: 56 focused tests in four files, then 21 affected tests
after accessible labels; typecheck and serial build PASS; token guard PASS (52
files); original AppShell+Canvas browser fixtures at 1366x768, 1440x900 and
1920x1080 PASS for exact single-field editing, preview, undo and no overflow.
Those static fixtures issued zero Save/run/external requests. They do not prove
real Host or persistence behavior. Original missing-control, selector and type
failures remain in that evidence directory.

Sibling `storyboard-shot-closeout-evidence-20261020` holds closeout commands,
source-integrity records and raw failures. The first fixture omitted a required
source pin. With that corrected, four real same-batch Apply/Undo author-edit and
draft-ABA assertions failed against the original owner. Two additional UI
assertions exposed coalesced production-dirty ABA leaving old controls visible.
Those assertions remain after repair. The final handoff records targeted tests,
typecheck, build, browser checks and fixed commit/tree hashes.

Not accepted or run: whole SHOT-03/canvas completion, real Host/PG persistence,
native packaged Windows E2E, actual provider/GPU/model execution or quality,
release/install and GitHub Actions. The owner Save test uses an HTTP fixture,
checks original expected_version and never claims server persistence. No push,
main merge, archive publication or DSH integration is part of this task.
