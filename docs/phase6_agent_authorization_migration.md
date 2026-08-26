# Phase 6.4 Agent Job Authorization Migration

## Scope

All Agent Job lifecycle routes must use the same trusted-session boundary before export auditing is enabled.

## Routes

- `POST /api/agent-jobs`
- `GET /api/agent-jobs`
- `GET /api/agent-jobs/{job_id}`
- `POST /api/agent-jobs/{job_id}/start`
- `POST /api/agent-jobs/{job_id}/execute`
- `POST /api/agent-jobs/{job_id}/cancel`
- `POST /api/agent-jobs/{job_id}/retry`
- `POST /api/agent-jobs/{job_id}/review`
- `POST /api/agent-jobs/{job_id}/apply`
- `GET /api/agent-jobs/export.csv`

## Required boundary

1. Resolve `X-Session-Token` with `trusted_session_resolver`.
2. Resolve the task's novel to its workspace/project scope.
3. Require the operation-specific membership capability through `membership_authorization_service`.
4. Pass the trusted `ActorContext` to audit-capable operations.
5. Return `401` for missing/invalid sessions and `403` for insufficient scope.

### Current status

All listed Agent Job routes now require a trusted `X-Session-Token`; missing or invalid sessions return `401`. Branch-bound tasks use the real novel-to-workspace mapping and `membership_authorization_service` for scope and capability checks. Legacy unscoped tasks remain compatibility-only and do not infer a default scope.

The authorization matrix and cross-workspace rejection tests are included in the Phase 6 acceptance gate.

## Capability mapping

- list/detail/export: `domain.read`
- create/start/execute/cancel/retry: `domain.write`
- review: `domain.review`
- apply: `domain.write` plus explicit review state

## Role matrix

| Role | Read/list/detail/export | Create/start/cancel/retry | Review | Apply |
| --- | --- | --- | --- | --- |
| `ADMIN` | allowed | allowed | allowed | allowed |
| `DOMAIN_LEAD` | allowed | allowed | allowed | allowed |
| active member without a role | denied for branch-bound jobs | denied for branch-bound jobs | denied | denied |

`DOMAIN_LEAD` now explicitly includes `domain.review`; legacy jobs without `branch_id` remain compatibility-only and do not infer a scope or role.

## Export audit implementation status

The Agent Job service now exposes a safe export summary containing only result count and identifier/date filters. Persisting this summary through `AuditService` is gated on a branch-bound request with a fully resolved `AuthorizationScope`; legacy unscoped exports remain non-audited for compatibility.

## Audit gate

CSV export audit remains disabled until every route above uses the same boundary. Once enabled, audit metadata may contain only actor, scope, filter summary, result count and timestamp; never prompts, context bodies, credentials or model responses.
