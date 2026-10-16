# Exact asset-to-image draft handoff — 2026-10-16

Baseline: `8d71994c9ccf6b4e975b63172b025557d4fd2ee6`. The containing local commit identifies delivery. Status: IMPLEMENTED bounded frontend handoff; independent IMAGE/VIDEO portfolio remains PARTIAL.

## Original-owner audit and behavior

The mounted AssetBrowser already produced exact asset ID/version/digest references, but IMAGE only displayed a notice. The existing `useStudioMediaExecution` already owned I2I sources, modern `imageSource` and auxiliary references, legacy bounded reference lists, provider selection, consent, preview, queue creation and UNKNOWN handling. These owners and contracts were reused; no backend, route, schema, permission, dispatch or second draft store was added.

IMAGE now goes through the same original workspace dirty-navigation decision as TIMELINE. The session-only intent opens the existing production panel. The author must explicitly choose the existing “参考图片生成图片” operation; handoff never changes operation, provider, route, prompt, parameters or license note. Other operations, prepared storyboard requests and unsettled original jobs block this handoff.

Explicit metadata review shows the exact source. Explicit apply rereads it and requires matching ID/version/SHA-256, image kind, undeleted status, no manual mask and matching current asset-list metadata. There is no latest-version substitution, source mutation, byte download, generation preview, queue, execution or paid call. A modern configured route gets one empty base-image slot while preserving auxiliary references and its original reference limit; an existing base is never replaced. Legacy I2I appends only up to the original five-source bound. Duplicate references and unsupported mixtures require the author to use original controls first.

Apply calls the original media `edit()` owner, preserving the draft and clearing its old execution preview/confirmation; cloud-send consent is explicitly cleared because the payload changed. Original later command validation, source checks, create, execute, review and reference owners remain unchanged. This draft remains session-only, with original dirty navigation, not a new persistent save format.

## Fences and verification

Owner revision fencing covers draft edits including same-tick ABA, source-list metadata ABA (including the incoming not-yet-bound asset), client/request/permission changes, current identity, busy/UNKNOWN, original job transitions, synchronous provider reload and cancellation. In-flight acceptance never applies after unmount or changed draft/configuration. Double submission consumes one intent once.

Final commands, exit codes, times, logs and source hashes are linked by `asset-image-handoff-20261016.json`. Selected mocked tests include the real mounted AssetBrowser→production panel flow, IMAGE/TIMELINE dirty-navigation cancel, exact rereads, stale retained callbacks, input/consent preservation, existing-image contract, bounds, malformed/changed metadata, source/client/busy/draft ABA, UNKNOWN, offline and cancellation paths. The final suite is 111 tests; 30 PUBLIC contracts, TypeScript, Vite, test discovery, UI token guard and 487-file PUBLIC source closure also pass. No backend owner was changed, so no new File test was needed. Existing mocked production contracts remain included.

An initial optional-state null guard regression and an IMAGE test fixture using a video kind were caught and fixed; failed receipts are retained. Independent review identified the incoming-source ABA gap; the original owner revision stamp and a regression were added before final acceptance. Earlier pass receipts are historical, not substituted for final-source verification.

## Explicit remaining boundaries

- VIDEO/STORYBOARD handoffs, broader multi-target proposals and persistent generation-draft recovery remain open.
- Unified DeliveryCenter stays BLOCKED: there is still no authoritative identity-specific entitlement producer. No allow flag or synthetic grant was introduced.
- Browser/visual/native input/performance, PostgreSQL/P0/security lifecycle, Windows/GPU/provider/user computer/full RC: NOT_RUN.
- P0 BLOCKED; R3-GATE HOLD; production Prompt Adoption writes disabled.
- Local commit only. No push/hosted CI because cost is unknown; no main merge, tag, release, new paid service or changed account/security configuration.

Parent independent review precedes the next tracked feature slice. Preserve historical receipts and all environment, cost and denial boundaries.
