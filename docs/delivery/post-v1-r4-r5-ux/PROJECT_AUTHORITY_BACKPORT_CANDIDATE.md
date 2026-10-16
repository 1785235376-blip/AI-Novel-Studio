# Candidate: declared-level project authority validation

Status: implemented only on the post-V1 PR #39 branch. This is a backport
candidate, not authorization or evidence of a backport to frozen PR #37 or
PR #38. Their branches, packages, and acceptance results are unchanged.

## Reproduced defect and narrow repair

The inherited `_authorize_novel_project` builds a genuine `PROJECT` scope
when no branch is requested, then passes it to the collaboration validator
that requires both a storyline and a branch. The same code is present in
the read-only inspected frozen SHA `1ad947e458a1ebb4b0f74e06b4e0e3fb3322bab0`.

Before this repair, two mounted File requests to the supported `media-tasks`
route (`/api` and `/api/v1`) returned `403 PROJECT_SCOPE_FORBIDDEN` despite
the real membership/authorization service accepting the actor's project
`domain.read` grant. An initial `GET /exports` probe instead encountered the
separate existing middleware `501 COLLABORATION_ROUTE_NOT_ENABLED` boundary;
this repair does not change that route allowlist.

The only runtime change removes the premature branch-only validation in
`_authorize_novel_project`. Its existing `MembershipAuthorizationService.require`
still checks current membership and invokes the original `AuthorizationService`,
whose `_validate_scope` validates the declared project/branch level and parent
relations. No new grant, client role, authority service, or bypass is added.

## Preserved contracts

- Current project-to-workspace mapping and trusted actor workspace must agree.
- Requested permission and NOVEL domain remain server-checked on every request.
- Asset access still checks project authority and a valid branch context.
  A branch-only role cannot satisfy the project check.
- Existing downward scope inheritance remains intact: a project read grant
  covers descendant branch reads. A missing branch header still returns
  `400 BRANCH_SCOPE_REQUIRED`; a cross-project branch remains forbidden.
- Revoked project permissions/roles, revoked membership, invalid sessions,
  mismatched projects/workspaces, and invalid storyline parents stay denied.
- Branch-partitioned asset lookup cannot expose another branch's selected asset.
  Branch manuscript support, original review authority, and export boundaries
  are unchanged.

## Verification on 2026-10-05

`tests/test_project_authority_validation.py` uses the original mounted R3
fixture, real repositories, trusted sessions, memberships, roles, and direct
permissions. Both route aliases and File/real-PostgreSQL parameters are retained;
no allow-all authorization mocks are used. It includes experimental-off and
V1-acceptance-mode shared-route checks.

The combined isolated run passed **148 tests**, with **58 PostgreSQL cases
skipped locally**, across the new authority tests plus authorization foundation,
identity membership, collaboration scope/API, phase-one media project authority,
asset lifecycle, adaptation authority, industry export queue/history, and B08
Writer Room mounted contracts. The new file contributes 34 File passes and
34 PostgreSQL skips. Skips are not passes; actual PostgreSQL remains a hosted
exact-commit gate. `git diff --check` passed for the owned source/tests.

This is deterministic implementation verification, not an independent review,
real-model/GPU test, user acceptance, release, merge, or production deployment.
