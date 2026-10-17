# Explicit existing-storyboard image binding

Base: `d11ea893a9deb4c2ceda23a4383f83054e9f25dd`.
Branch: `work/dot-storyboard-handoff-20261016`.

## Bounded result

Asset → STORYBOARD now opens a session-only exact-image recipient. The user explicitly lists and selects an **existing** STORYBOARD document, reads its saved receipt, selects an existing shot, and inspects the incoming image's original ID/version/digest. These operations are GET-only. No first document/shot is selected, derived or created automatically.

The final control explicitly **saves a new document version and revokes the old storyboard approval**. This is not an unsaved draft-reference feature. The original `StoryboardProductionPanel` / `useStoryboardProductionController` remains the write owner and uses the existing `storyboardBindImage` endpoint. The ordinary picker and CreativeWorkspace mount retain their paths. There is no backend, lifecycle, authorization, dependency, schema, second store or execution-engine change.

Before the single explicit POST, the controller re-reads the exact formal nondeleted image and target receipt, requiring the unchanged source pin, document ID/version/digest/content, ordered shot records and source bindings. It does not silently rebase. Success requires version +1, revoked approval, the same complete ordered shot records except the selected image pin, unchanged director sources, and an original-document refresh with matching ID/version/mode, authored content, author shot order and source provenance. Receipt sorting uses a copied shot-number sort without rewriting authored order.

Current-owner, permission, handoff, client, document, selection, busy, cancellation/unmount and ABA fences apply across asynchronous boundaries and immediately before POST. Synchronous in-flight and consumed guards block duplicate and retained-callback dispatch. The original host semaphore distinguishes its own operation from unrelated busy work. Pending receipt input participates in existing dirty navigation, including cancellation and explicit discard, while unrelated production controls/automatic reads are suspended for the recipient and restored when it closes.

## UNKNOWN limit

The original binding API has no request-specific recovery identifier. Network/5xx/malformed success and any failed or invalid post-success document refresh retain the attempted source and target as UNKNOWN. Neither an unchanged original document nor a matching +1 binding proves this request's outcome. Explicit receipt/document reads report only observed current state; they never claim recovered success/failure, adopt it as a successful request, unlock another save, or automatically retry. The user may explicitly leave through the existing discard warning, which does not cancel a possibly completed remote save. Authoritative 401/403 uses the original deny path. Generic video handoff remains out of scope because it requires reviewed production-job/source-shot proof.

## Evidence and retained failures

- [Independent final verification](../delivery/v2-development/storyboard-image-handoff-20261016/independent/README.md): **178/178** passed across six suites: 82 controller, 19 mounted host, 30 direct recipient, and 47 unchanged original cases (131 new additive cases). Forced TypeScript, production build, global/scoped token checks passed; all 1,274 frontend hashes stayed unchanged. [Earlier controlled test history](../delivery/v2-development/storyboard-image-handoff-20261016/tests/README.md) remains preserved; overlapping reruns are not added to unique counts.
- Diagnostic run 2 retained 17 real host-entry failures and a disclosed runtime edit overlap. It is **not acceptance evidence**. The automatic production asset read's unrelated busy lease caused entry retirement; its handoff-specific gate fixed the failure without weakening retirement tests.
- [Sequential forced typecheck/build/token evidence](../delivery/v2-development/storyboard-image-handoff-20261016/verification/README.md): the initial inference failure and subsequent passing logs/source hashes are retained. Production build retains its existing large-chunk warning.
- The direct recipient tests cover retained directory/document read and selection callbacks, cached metadata removal, owner-output ABA, delayed response fences, and retirement Close-button recovery before the pending read resolves.
- Existing frozen tests/guards/manifests are not edited by this slice. Parent inventory binding and local commit are separate review steps.

DS-v1.0 and protected-surface guidance plus the canonical IMAGE reference were reviewed. Visible controls reuse existing Panel/Button/StatusMessage and semantic form controls; no new styling, shell, geometry, tokens or primitive changes.

Browser/visual/geometry acceptance, real HTTP, File/PG integration, native/Windows, provider/GPU/model quality and full release acceptance are **NOT_RUN**. The prior browser socket EPERM boundary was respected; no retry, Python, dependency installation, paid resources, user-machine work, push, main merge or release occurred. P0 BLOCKED and existing release gates remain unchanged.

Final staging note: unrestricted staged `git diff --check` reports exit 2 only for final blank lines in six preserved raw test logs. Product source, additive tests and documentation pass the check when raw logs are excluded. Verified raw evidence bytes were not normalized.
