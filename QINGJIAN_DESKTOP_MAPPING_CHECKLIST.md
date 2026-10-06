# QingJian Desktop Source Mapping Checklist

Status: **LOCAL_REQUIRED**. Complete real QingJian Desktop source is not in the current Cloud repository. No guessed Desktop source paths are listed. The paths below for prepared adapters refer only to this preparation, not an assumed native architecture.

Before implementing a mapping, record the actual owner, actual source path, existing public contract, current lifecycle, authorization owner, test fixture and evidence. Do not replace an owner merely because an adapter is easier to write.

| Owner to locate in real source | Map to prepared boundary | Verify before enabling |
|---|---|---|
| ContextSystem / Context V2 | Tutor context ingress | Existing category, authority, privacy, evidence and provenance rules; readonly external context |
| ContextAssembler | Product-owned assembly callback | Bounded inclusion; no authority promotion; current project/task scope |
| Recall Gate | Product-owned recall callback | Permission/privacy checks before retrieval; no automatic memory write |
| Memory Gate | Memory candidate preview/submit | Exact candidate digest, policy, explicit approval/trusted bounded rule, live recheck |
| Tutor Orchestrator / QingJian Main | InteropTutorAdapter | Existing orchestration and Verified Case retrieval; advisory output only; model internals stay private |
| Verifier | InteropVerifierAdapter | Fresh trusted state before execution/delivery; source/permission/version changes fail closed |
| Case DB / Case Gate | InteropCaseGateAdapter | Solved evidence → candidate → preview → approval → gate → store; no implicit Cloud upload |
| Model Scheduler | InteropModelRegistryProvider | Own readonly metadata; no credentials, endpoints, directory scan or execution |
| Desktop Settings | Feature/trust/config owners | Default OFF; acceptance mode OFF; separate product config; trust store stores no grants/secrets |
| App Lifecycle | InteropLifecycleCoordinator | Startup isolated from bridge failure; bounded shutdown; fresh instance on restart; no restored grants |
| Notification system | InteropNotificationAdapter | INFO/ACTION_REQUIRED/ERROR; user settings/rate policy; no unsolicited popup loop |
| Deep Link / navigation | InteropHandoffHandler + UserPresenceGate | Exact semantic target, current ownership/version and one-use local click/dialog; actual Windows registration |
| Windows Host | NamedPipeTransport + OS identity adapter | Current-user SID ACL, remote rejection, non-inheritable handles, framing, cancellation, limits and peer PID/SID |
| Installer / signed binary registration | ProductionPeerAttestation | Real executable/signature/publisher evidence; approved installation record; downgrade/revocation |
| Event producer owners | InteropEventSourceRegistry | Direct source callbacks where available; honest POLLING fallback; independent subscribers and live permissions |

## Required evidence for each mapped owner

- Actual Desktop repository revision and owner path, discovered from source rather than inferred
- Existing owner API and the smallest adapter, with no second state/memory/config database
- Synthetic, non-user-content fixture and contract test
- Real two-product test where needed, including reconnect/revoke/upgrade/expiry
- NOT_RUN or LOCAL_REQUIRED for unavailable environment, never a mocked production claim
- No paid API, real manuscript, credential sharing, automatic software/model launch, public/LAN listener, write/control capability or production deployment

## Completion order

Inspect source → map owners → implement adapters → retain owner systems → contract/product tests → Windows pipe and distinct-user tests → real two-product acceptance → separately reviewed Beta decision. Current Beta/default feature gates remain OFF.
