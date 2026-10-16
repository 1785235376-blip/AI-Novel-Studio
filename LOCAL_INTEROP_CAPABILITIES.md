# Local Interop V1 capabilities

Capabilities are stable protocol strings. The granted set must be a subset of
both advertised and explicitly permitted capabilities. Missing capability returns
CAPABILITY_NOT_SUPPORTED, never best-effort access to a more privileged action.

| Capability | V1 purpose | Boundary |
| --- | --- | --- |
| project.context.read | Versioned scoped capsule | Metadata by default |
| project.selection.share | Explicitly selected content | Preview and per-request consent |
| project.metadata.read | Authorized project metadata | No project enumeration outside scope |
| task.status.read | Structured current task state | Host state, not model self-report |
| task.error.read | Error code | No raw prompt/log dump |
| diagnostics.read | Sanitized diagnostics | Allowlist and preview |
| model.registry.read | Model metadata projection | No secrets or execution |
| model.runtime.status.read | Runtime availability | No model installation/start |
| tutor.guidance.request | User-requested advice | No implicit content consent |
| tutor.guidance.receive | Display advisory response | Never executes steps |
| verifier.request | Structured condition evaluation | Trusted evidence only |
| verifier.result.receive | Display result | No silent mutation |
| case.candidate.create | Local candidate preview | Approval and memory gate |
| handoff.open_feature | Navigate existing feature | Explicit click |
| handoff.open_project | Navigate authorized project | Explicit click and live access |
| handoff.open_task | Navigate authorized current task | Explicit click and version check |

V1 deliberately has no model.execute, project.write, credential.read, shell,
mouse/keyboard control, arbitrary file access or remote MCP capability.
Optional capabilities may be omitted without stopping either independent product.
Unknown capabilities never silently grant an equivalent action.
