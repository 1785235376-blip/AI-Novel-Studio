# Public distribution vs internal research edition — boundaries and build checks

SPEC-2026.10.19-r1 release gate 10 requires the public edition and the internal research
edition to be separated (product, data, models, backend policy). This page records what
the repository actually enforces today, what was added in round 3, and what remains
blocked. It does not claim a separate internal deployment exists.

## 1. Declarations

- [edition_manifest.json](edition_manifest.json): declarative editions, public-build
  invariants and the honest `internal_research_boundary.status = BLOCKED`.
- `app/edition.py`: `PUBLIC` / `INTERNAL_RESEARCH` constants and a fail-closed
  `current_edition()` (unknown value -> PUBLIC). It contains **no** authz/routing logic;
  the existing project/session/CAS owners stay the single runtime authority.

## 2. Enforced public-build invariants (executed)

`scripts/verify_public_edition.py` (24 checks, exit 0 PASS / 1 FAIL / 2 BLOCKED):

1. Experimental flags default OFF; `V1_ACCEPTANCE_MODE` denies all experimental flags;
   wildcard enable is forbidden in the registry; dependency closure only shrinks a request.
2. Packaged launch environment is explicit: `ENABLE_CLOUD=false`, `MOCK_PROVIDER=false`,
   `ENABLE_PROVIDER_FALLBACK=false`, `ENABLE_PACKAGED_RUNTIME=true`,
   `ENABLE_COLLABORATION_RUNTIME=true`, and an explicit closed `EXPERIMENTAL_FEATURES` list
   (never `*`). Static settings defaults keep packaged/collaboration runtime off.
3. The portable launcher runs the bundled Python with `-B -I`, fixes the staged
   `--application-root`, and reads no dotenv/credentials.
4. Tracked build inputs contain no credential files or model weights; `.env.example` is
   limited to placeholders and is scanned for live-token patterns.
5. The internal-research boundary must be declared `BLOCKED` while it is unimplemented;
   asking the verifier for `INTERNAL_RESEARCH` returns exit 2, never PASS.

Runtime tests in `tests/test_public_edition_boundary.py` additionally prove: default app
exposes no enabled experimental feature; experimental owner routes return
`EXPERIMENTAL_FEATURE_DISABLED`; the versioned `/api/v1` prefix applies the same gate;
`/api/health`, `/api/providers`, `/api/models` contain no credential/token material;
`V1_ACCEPTANCE_MODE` keeps experimental surfaces closed; edition parsing fails closed.

## 3. Remaining BLOCKED internal-research work (not implemented)

- Separate internal-research deployment/compose and its host controls.
- A research-only backend namespace with its own authorization and data namespace.
- A packaging manifest that excludes research-only modules/assets from the public build.
- Different egress/model-upload policy between the two editions.
- Cross-edition access tests on a real deployment: no-permission call, cross-version
  access, disabled route, configuration leak, residual-resource cleanup.

These are the SPEC gate-10 acceptance items; the build invariants above reduce the risk
of internal-only surfaces silently entering a public artifact but are not a substitute.

## 4. Evidence

- [evidence/20261019-r3/public-edition-boundary.md](evidence/20261019-r3/public-edition-boundary.md)
- `python scripts/verify_public_edition.py` -> PASS (24/24 checks)
- `python -m pytest -q tests/test_public_edition_boundary.py` -> 9 passed (with the
  engineering traceability guard)
