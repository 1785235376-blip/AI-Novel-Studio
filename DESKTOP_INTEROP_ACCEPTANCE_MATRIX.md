# Desktop Interop Acceptance Matrix

Run the bounded, offline contract driver explicitly:

```sh
python -m local_interop_desktop.acceptance --mock-only --output receipts/desktop-acceptance.json
```

The runner uses the actual prepared SDK with a compiled-in synthetic peer. It starts no product, socket, model, paid API or installer. Synthetic proof is never a production trust record. Native probes must run in the actual Desktop environment; a missing probe is NOT_RUN/LOCAL_REQUIRED.

| ID | Scenario | Contract scope | Native status / requirement |
|---|---|---|---|
| A01 | Install state | Empty and populated registered-source discovery; no scanning or automatic launch. | LOCAL_REQUIRED: Actual installed-product records and explicit absent/present desktop UI checks. |
| A02 | Peer discovery | Bounded installed/running/pipe discovery from explicit product-owned sources. | LOCAL_REQUIRED: Actual QingJian Desktop registration, running instance and approved pipe composition. |
| A03 | Trust | Fail-closed OS-fact/installation/publisher/approval policy with synthetic evidence. | LOCAL_REQUIRED: Real connection-handle SID/PID plus binary signature, publisher and approved installation. |
| A04 | Handshake | Observable connected, handshake, authenticated, session and negotiated stages. | LOCAL_REQUIRED: Real two-product V1 exchange over current-user Named Pipe. |
| A05 | Capability negotiation | Only known requested V1 capabilities; connection alone grants no content. | LOCAL_REQUIRED: Actual product capability owners and per-scope permission center. |
| A06 | Metadata context | Metadata capsule contains no selection, manuscript or prompt. | LOCAL_REQUIRED: Actual products with synthetic project metadata and independent settings. |
| A07 | Selection context | Selected text is rejected without explicit scope consent; authorized preview only. | LOCAL_REQUIRED: Real editor selection preview/consent with synthetic text. |
| A08 | Chapter context | Current chapter is rejected without explicit consent; current-version binding. | LOCAL_REQUIRED: Real chapter/version preview/consent with synthetic text. |
| A09 | Diagnostic | Strict non-content diagnostic and bounded audit allowlists. | LOCAL_REQUIRED: Native diagnostic source and audit sink inspection with synthetic credentials. |
| A10 | Event | Metadata projection, direct/poll/synthetic provenance and isolated subscriber revocation. | LOCAL_REQUIRED: Native producer event hooks and actual cross-product subscription delivery. |
| A11 | Session revoke | Disconnect revokes the local session and cancels pending delivery. | LOCAL_REQUIRED: Actual transport/session/subscription cancellation on both products. |
| A12 | Permission revoke | Fresh authorization at event delivery; revoke A while B continues. | LOCAL_REQUIRED: Two real subscribers with independent live permissions. |
| A13 | Tutor guidance | Actual frozen TutorRequest/TutorGuidance exchange; advice performs no mutation. | LOCAL_REQUIRED: Actual Tutor orchestrator/ContextAssembler composition, without paid model invocation. |
| A14 | Verifier | Fresh-state boundary; untrusted wire authority never proves verification. | LOCAL_REQUIRED: Actual Verifier owner with independently trusted current source and permission revision. |
| A15 | Deep Link | Single-use, bounded, locally issued user-presence token and current target resolution. | LOCAL_REQUIRED: Real Windows URI registration plus user-click navigation. |
| A16 | Model Registry | Read-only ModelRegistry projection, secret rejection and stale cache. | LOCAL_REQUIRED: Actual QingJian Model Scheduler projection and source freshness. |
| A17 | Tutor crash | Synthetic peer failure cannot produce a usable response. | LOCAL_REQUIRED: Real Tutor process crash and subsequent host recovery. |
| A18 | Studio crash | Simulated host shutdown revokes volatile session/grant state. | LOCAL_REQUIRED: Real Studio process crash, no surviving sender, and restart identity. |
| A19 | Restart | Fresh instance on restart; no session or standing-grant restoration. | LOCAL_REQUIRED: Real desktop restart with non-restored content and standing-event grants. |
| A20 | Upgrade compatibility | Product version compatibility, existing 1.0 selection and unknown-major refusal. | LOCAL_REQUIRED: Real product upgrade/install identity and signature revalidation. |
| A21 | Different Windows user | A genuine separately authenticated Windows-user client must be denied by another SID pipe. | NOT_RUN: Run the distinct-user Windows probe; same-user CI is not evidence for this scenario. |
| A22 | Fake product_id | Claimed known product ID without approved installation must fail production policy. | LOCAL_REQUIRED: Real hostile process plus trusted installer registry/signature evidence. |
| A23 | Expired session | Fixed session expiry rejects use; heartbeat cannot extend the original expiry. | LOCAL_REQUIRED: Real two-product elapsed session expiry without implicit renewal. |
| A24 | Offline | Missing peer/bridge failure remains isolated from host application startup. | LOCAL_REQUIRED: Offline actual user-machine acceptance and host startup timing. |

## Required negative and regression supplements

The core and product-adapter suites additionally cover project A→B, chapter 37→38, session A→B late response, permission revision changes, trust downgrade, unknown protocol, no automatic grant restoration, credential isolation, queue pressure, bounded polling and stalled shutdown. Original R1/R2/R3 assertions are retained.

A21 requires two actual Windows logons. Run the committed native cross-user harness under the documented separate identities. Passing ACL text inspection, same-user exchange or synthetic SID comparison does not pass A21.

Do not enable Beta from this matrix. Real QingJian Desktop source mapping, signed installation proof and real two-product acceptance remain required.
