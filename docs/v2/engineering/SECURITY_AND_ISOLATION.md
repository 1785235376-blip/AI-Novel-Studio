# Security, privacy, and edition isolation contracts (V2)

Version: `ENG-2026.10.19-r1`. This document binds existing security owners to explicit
requirements. It distinguishes **existing implemented controls** from **requirements that remain
PLANNED**, and it never upgrades a contract test into a security acceptance.

## 1. Trust boundaries

| Boundary | Existing control | Evidence in tree |
| --- | --- | --- |
| Local host vs remote/collaboration caller | Host authority binds the current registry/bootstrap instance and token binding generation, not a bare token; forwarded headers cannot impersonate the local host; a remote collaboration-only session has no host authority | `app/runtime.py`, `app/packaging/*`, V0.5.x authorization tests |
| Studio vs QingJian (Local Interop) | Stable v1 protocol contracts under `contracts/local-interop/v1/*`; explicit session/permission grants; no shared global read/write token | `app/local_interop/*`, `local_interop_protocol/*`, `docs@LOCAL_INTEROP_SECURITY.md` |
| App vs network | Outbound URL validation rejects non-http(s), non-allowlisted loopback, private/reserved/link-local/multicast targets, redirects are not followed; response size bounded | `app/net_safety.py` |
| Packaged desktop app | Packaged runtime behind explicit launch profile; control pipe/credential store are process-local; packaged mode disables insecure memory-vault fallback by default | `app/packaging/control_pipe.py`, `packaging/launch_profiles.py` |
| Model/provider boundary | Model Center discovery is read-only and never starts a runtime; provider dispatch is guarded by exact route identity, budget, license and consent; graph model execution is a separate opt-in | `app/model_center/*`, `app/experimental/model_broker.py`, `app/creative/ai_execution.py` |

Host re-registration does not revive old consent or a running job. Losing scope, host identity or
permission clears private previews and suppresses late UI responses.

## 2. Project scope, roles, and content authority

- Every content write is checked against project incarnation, scope, actor/session and branch
  authority. Scope keys are explicit and bounded (`PUBLIC_SCOPE_KEYS` in
  `app/creative/production_contracts.py`); an unknown scope field cannot widen access.
- Permissions are domain-scoped: `domain.read` / `domain.write` / `domain.review`.
  Review is a distinct authority; review does not apply text to manuscript/canon/assets.
- Cross-project reads are rejected. The asset owner stores scope on every asset; relationships
  cannot cross project boundaries.
- Versioned writes use CAS (`{version, digest}`); stale writes fail closed. A deleted and
  recreated project receives a new incarnation so late jobs cannot attach to it.
- Collaboration scopes/roles/collaboration runtime are preserved as V0.5.7 behavior; V2 work must
  not weaken conflict, revocation or fail-closed behavior.

## 3. Privacy levels and manuscript egress

Existing privacy model (`app/privacy.py`):

- Levels: `CLOUD_ALLOWED`, `REDACT_BEFORE_CLOUD`, `LOCAL_ONLY`.
- Unknown/malformed/missing policies normalize to `LOCAL_ONLY` (fail closed), and restrictions
  merge with the strictest value; a permissive copy cannot override a stricter source.
- Cloud-bound context builders replace protected facts with a redaction constraint; `LOCAL_ONLY`
  children are removed entirely.
- Manuscript egress review (`app/source_privacy.py`) is **hash/version/branch bound**: it permits
  future sends of exactly one chapter revision in one branch; editing, branch change or revocation
  invalidates the permission; already-transmitted content cannot be recalled by changing the record.
- Provider credentials are separate from source-privacy consent; a configured API key is not consent
  to send a chapter.

Requirements that remain enforced for all V2 work:

1. No cloud/paid provider call without explicit user consent, budget/price display and hard limit.
2. No hidden fallback from local to cloud, and no cloud dispatch from a generic generation URL.
3. Request/response logs must not contain API keys, raw manuscript, absolute personal paths or
   provider payloads; receipts store digests/bounded facts.
4. Deleting/relinking sources must invalidate stale egress permissions, not silently keep them.

## 4. Secret handling

- Provider keys live in the credential vault (`app/credential_vault*`; `keyring` optional
  extra). Tests use `CREDENTIAL_VAULT_BACKEND=memory` plus an isolated profile; the real OS
  keyring is never touched by the baseline.
- Committed evidence may contain only: command, environment variable **names**, tool versions,
  hashes, bounded reason codes and non-sensitive log tails. Never keys, tokens, cookies, user
  novel text, personal project paths or browser profiles.
- `.gitignore` excludes `.env`, data dirs, logs, runtime and test outputs; backup dumps are kept
  out of Git.

## 5. Path, filesystem, and download boundaries

- `PROJECT_ROOT` (code/runtime root) and `NOVEL_DATA_PATH` (project data) are independent
  settings; tests must isolate both.
- Local AI discovery is bounded: fixed common roots, configured roots, 32 roots / 5,000 entries /
  2,000 files / three levels / 256 KiB metadata; no home recursion, drive scan, PATH search,
  symlink/junction follow or model-code import. Discovery never starts inference or installs.
- Imported media is size/type bounded; unsupported/oversized inputs are rejected with explicit
  codes. Assets are stored under the project asset root; external model directories are never moved
  or cleaned.
- Disk cleanup only ever targets the run's own directory. The repo worktree, RC1 checkout, models
  and user data are never deletion targets.

## 6. Public version vs internal research version — CURRENT STATUS: NOT ISOLATED (PLANNED)

The user requirement is that a public version and an internal research version are separated at the
**backend, data, runtime-policy and authorization levels**, not only hidden in the frontend.

Actual state at `a072cf90`:

| Element | Status | Evidence |
| --- | --- | --- |
| Public GitHub repo contains all product code, including experimental surfaces | EXISTS | Single repository/tree; no separate public backend source set |
| Experimental/research capabilities flag-gated, default-off, dependency-checked | EXISTS | `app/experimental/flags.py` (no wildcard; V1 acceptance mode overrides all off) |
| Package/release identity and launch profiles for packaged runtime | EXISTS | `app/packaging/runtime_identity.py`, `launch_profiles.py`, `app/release_readiness.py` |
| Separate public/internal **backend service** with its own data store | **MISSING (PLANNED)** | No edition selector, second deployment profile, or edition-scoped storage/authz layer found |
| Edition-scoped authorization (internal-only APIs unavailable in public build) | **MISSING (PLANNED)** | Flags are runtime opt-in, not build-time edition separation |
| Privacy redaction and egress controls (used by both editions) | EXISTS | `privacy.py`, `source_privacy.py`, `net_safety.py` |
| Documented data-subject/retention policy and audit export | **PARTIAL** | Some diagnostics/backups exist; no edition-wide retention policy |

Therefore: **do not claim public/internal research backend isolation as implemented.** The
requirement is recorded in the traceability matrix as `PLANNED` with release-blocking level HIGH
until an edition manifest, separate backend profile, edition-scoped authz, separate data root and
redaction audit are implemented and tested in an isolated acceptance.

## 7. Third-party dependencies, models, and licenses

- Python dependencies are constrained by `.github/ci/python-constraints.txt` and `pyproject.toml`;
  CI runs `pip check`. Frontend uses the checked-in `pnpm-lock.yaml` with
  `--frozen-lockfile`.
- Model weights are never committed or bundled; model discovery verifies metadata only, and model
  licenses are reviewed before any dispatch. Model downloads require explicit user approval and are
  out of this baseline.
- Bundled PDF font flow uses an OFL-licensed font prepared by
  `scripts/prepare_pdf_font.py` (CI receipt), not an arbitrary system font.
- External tool execution (ComfyUI custom nodes, plugins, unknown scripts) is not auto-installed or
  auto-run; plugin packs have declarative contracts and trust/signing foundations in their own
  branches and are not part of this baseline.

## 8. C2PA / content provenance claims — NOT IMPLEMENTED

No C2PA signing, manifest embedding or verifier exists in the tree (no C2PA matches in source or
docs). What exists is **internal provenance**: asset digests, revisions, source version pinning and
lineage relationships. That is not C2PA and must not be described as C2PA or as a certified
content credential. If content credentials are required for release, they are `PLANNED` work with
an explicit signing-key and verification design, and remain release-blocking for the corresponding
delivery claim.

## 9. Logging, diagnostics, and incident handling

- Errors returned to clients carry bounded machine codes and never raw exception text or personal
  paths.
- Diagnostic export is private, size-bounded and redacted; it excludes credentials and manuscript
  content.
- Security failures (scope loss, host revocation, permission denial) fail closed and clear private
  UI state.
- Any suspected key/data leak: stop, preserve bounded evidence, rotate credentials outside the repo,
  and record the incident without committing the secret.
