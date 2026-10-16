# Legacy discovery credential and cached-owner diagnosis

Observed 2026-10-09 against HEAD `9851bdd2d692df983664bc8f4597fbc05c0e2ceb` plus the existing uncommitted M3-B file-observation changes. This is source inspection only: no tests, browser, host inventory, network probes, or production mutations were run. No source, test, or configuration files were modified. This evidence directory is outside `scripts/run_v2_checks.py:60–75` source-snapshot inputs.

## Confirmed compatibility failure

1. `frontend/src/novel/LocalHostSessionPanel.tsx:22–25` verifies the supplied credential with `/api/local-session`, then calls `bindLocalHostSession`. `frontend/src/localHostSession.ts:6–8` stores only the trimmed token, actor, and incremented epoch in the existing non-persisted Zustand owner. It does not populate the collaboration token; the original contract explicitly tests this in `frontend/src/localHostSession.test.ts:8–12`.
2. `frontend/src/App.tsx:1242` supplies onboarding only when `independentStudios` is enabled. Default-off / V1 therefore reaches `ModuleWorkspaceRoutes.tsx:51` → `ModelCenter.tsx:46–66` → the legacy branch at `LocalAiDiscovery.tsx:92–93`.
3. `LocalAiDiscovery.tsx:181–191` calls `legacyDiscovery.snapshot()` on mount. `localAiDiscoveryApi.ts:152–155` reads only `getCollaborationContext().sessionToken`; it does not use the independently verified local token.
4. Production mounts both API prefixes with host authority (`app/main.py:372–373`). `discovery_api.py:52–68` applies this to every discovery endpoint. `discovery_authority.py:47–48` rejects the missing token with 401. Legitimate explicit local-host binding therefore does not make the default-off discovery snapshot succeed.
5. Simultaneously, the general Model Center reads use `api.requestToken` (`api.ts:66–70,93–100`), which does fall back to the bound local credential in the permitted local context. Health can return mutable while discovery has expired. Its retry is disabled by `expired` (`LocalAiDiscovery.tsx:370`).
6. The legacy scan click eventually calls `legacyDiscovery.scan()` (`LocalAiDiscovery.tsx:289–297`), which has the same credential mismatch. Backend legacy scan remains supported when V2 is off (`discovery.py:317–323`); changing server authorization is neither necessary nor appropriate.

## Confirmed cached-view gaps and important limits

- `useLocalAiOwnerKey(undefined)` returns literal `legacy` even when host epoch changes (`localAiDiscoveryOwner.ts:12–15`). Existing Model Center keyed content therefore does not remount or refetch health on same-mounted local-host binding changes.
- Legacy discovery does not use the captured owner boundary, and its default `isCurrentOwner` always returns true (`LocalAiDiscovery.tsx:92–101,139–156`). Its generation guards cover request replacement, cancellation, and unmount, not a still-mounted host owner change.
- After an observed 401/403, `report()` sets expired and disables actions but clears snapshot/scan only in V2 (`LocalAiDiscovery.tsx:163–167`). Cached hardware, paths, candidates, and registrations can remain rendered. The same-mode `canMutate: true → false` purge is also V2-only (`:198–206`).
- `LOCAL_AI_HOST_AUTHORITY_UNAVAILABLE` is excluded from the general auth branch and only specially handled for V2 (`:163,168`). Legacy treats this 403 as retryable and can leave controls enabled, although the server still denies all private requests.
- Clearing snapshot/scan alone is insufficient when a private path has already been copied into roots or runtime forms. Invalidation must also clear roots/editRoots, runtimeForm/runtimeId, registrationForm, and confirmation. This is the same privacy cleanup, not a separate feature.
- This does **not** establish an unauthorized server disclosure. Existing production authority checks and post-work guards reject revoked or wrong-host responses. This concerns client retention of previously delivered private evidence and frontend compatibility.
- Ordinary project/session/actor/scope transitions already remount `ModuleWorkspaceRoutes` through `App.tsx:1242` (its key includes token, actor ID, novel ID, and all scope IDs). The old discovery cleanup aborts mount/poll reads and ignores unmounted results. Do not duplicate or modify that protected App key.
- The visible local-host unlink control lives in Agent Team. Navigating there unmounts Model Center; that normal journey already clears its component cache. A same-mounted epoch/ABA case is still worth covering because the owner API permits it and pending transport responses need independent fencing.
- Packaged mode is immutable per document (`desktop-host/AI.NovelStudio.DesktopHost/Program.cs:256–257`), and the host injects its bootstrap session header (`:260–267`). There is no supported dynamic packaged-mode toggle to blame for a same-page fallback leak. Never borrow a development local token in packaged mode. Packaged server revocation still needs all-mode cached-view purging once a denial is observed.

## Existing coverage, and what it misses

- `frontend/src/ui/LocalAiDiscovery.test.tsx`: legacy lifecycle, no mount scan, explicit operations, transient-error retention, cancellation/old-poll guards, expiry preventing further mutation, and unmount behavior. It spies on the original singleton. The expiry test at lines 163–167 does not assert private cache removal. No verified local-host fallback or same-mount epoch/ABA case.
- `frontend/src/localAiDiscoveryApi.test.ts:9–13`: verifies an explicitly supplied collaboration session header. It does not bind the separate local-host owner.
- `frontend/src/localHostSession.test.ts`: covers the shared api.ts fallback rules, explicit empty captured identity, and no local fallback for actor/scope/packaged contexts; it does not exercise the discovery singleton.
- `frontend/src/localAiDiscoveryConsentApi.test.ts`: captured V2 client token, explicit-empty, actor/scope/packaged exclusions, before/after guards, safe diagnostics. These cases are V2 transport only.
- `frontend/src/ui/LocalAiDiscoveryConsent.test.tsx:65–80` and `ModelCenterOnboarding.test.tsx:13–21`: V2 permission loss, stale response, host epoch/ABA, and owner remount behavior. All supply onboarding.
- `frontend/tests/e2e/v2-local-ai-consent-live.spec.ts:82–87`: the original default-off/V1 journey performs the real credential binding but only asserts the old button is visible, new endpoints return 404 with explicitly supplied request headers, and no probes occurred. It never requires successful UI snapshot, an enabled old button, or a successful explicit old scan.
- `tests/test_local_ai_environment_v2.py:64–72`: verifies V1/default-off scan shape via direct service scan and an explicitly authorized router seam, not the frontend credential transport.
- `tests/test_v2_discovery_host_authority.py`: original production auth protects both API prefixes, off/on flags, collaboration isolation, direct/forwarded/origin constraints, backend ABA/revocation, and packaged bootstrap revocation. Preserve these tests and gates unchanged.
- `tests/test_v2_discovery_onboarding_api.py:110–119`: off/V1 new endpoints are gated and cause no probes; no frontend legacy success.

## Minimal implementation proposal (not implemented during diagnosis)

1. Export and reuse the existing `api.requestToken(context, url)` rule. Keep every legacy singleton method and exact call signature intact. In discovery `call`, an already captured token must be used verbatim, including the empty string; resolve fallback only for an uncaptured request or at captured-client construction.
2. Each uncaptured legacy request snapshots its local-host epoch/token at dispatch and rejects late results if that owner changed, including A → B → A. Check after response-body parsing as well as fetch, and do not convert an obsolete auth error into expiry for a new owner. A token-value-only comparison is insufficient. Do not add a credential registry, persist identity, or expose token values through keys/URLs/logs.
3. Reuse the existing React discovery owner for both presentation modes. With onboarding absent, derive the existing collaboration/project context. Still pass the `v2` client only when onboarding exists; legacy continues to invoke the old singleton so all original spies and exact-argument assertions remain unchanged. Make the existing opaque owner key change on host epoch even for legacy, which also remounts the existing Model Center health consumer.
4. Apply owner-current checks immediately before legacy dispatch and retain existing after-response checks. In particular, `run`, refresh, polling, and protected rereads must not dispatch under an obsolete captured owner during a React transition.
5. Make observed 401/403, host-unavailable denial, owner invalidation, and actual permission revocation clear private state across flags. Keep initial loading with `canMutate=false` distinct from revocation. Keep transient 503/state-recovery semantics unchanged. Preserve V2-only preview/consent/file presentation and all normal default-off labels, geometry, and singleton signatures.
6. No App/ModuleWorkspace/protected-shell change, server auth change, Model Center host-only gate, credential persistence, or new owner registry is needed.

## Additive verification requested after the frozen backend run

Keep every original test and assertion unchanged. Add separate tests for:

- Legacy singleton snapshot and scan with explicitly verified local owner; exact old URL/body/header contract.
- No fallback for explicit empty captured token, actor metadata, collaboration scope/token, or packaged host; current packaged bootstrap behavior remains server/host-owned.
- Late successful and failed responses after unlink, A → B, and A → B → A with equal final token values; include delayed JSON body parsing.
- Same-mounted legacy snapshot, poll, and mutation responses after owner invalidation and canMutate revocation; remove copied private form fields too.
- Legacy rebind remount refreshes health/snapshot without automatically scanning.
- Original real File/HTTP/UI default-off and V1 acceptance journeys: UI binding → successful private snapshot → enabled old Detect control → one explicit legacy POST scan → terminal evidence. Opening, binding, refresh, and skipping must produce zero scan/probe operations.
- Collaboration denial cannot reveal host-private data or grant host authority, while legal shared Model Center controls retain their existing contract.

The only necessary scope clarification is that all-mode private-state purging includes already-copied forms and host-unavailable 403, not merely snapshot/scan. No broader architectural work is required by the findings above.
