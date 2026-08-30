# Plugin Trust / Signing Foundation

Status: **contracts + pure policy**. This is not a signature verifier, not a
certificate authority, and not a plugin executor.

| Claim | Value |
|---|---|
| Plugin Trust Foundation | IMPLEMENTED (contracts + fail-closed policy) |
| Real cryptographic signing / verification | **NOT IMPLEMENTED** |
| Publisher key registry | NOT IMPLEMENTED |
| Online revocation / CRL / OCSP | NOT IMPLEMENTED |
| Marketplace | NOT IMPLEMENTED |
| Plugin installation / update | NOT IMPLEMENTED |
| Plugin code execution | DISABLED |
| `execution_supported` | `false` |
| OS sandbox ready | `false` |
| Capability Broker runtime | NOT IMPLEMENTED |
| Worker ready | `false` |
| Windows AppContainer / LPAC | NOT IMPLEMENTED (out of scope; independent of PR #26) |
| Model Center / Provider Runtime | NOT IMPLEMENTED (out of scope; independent of PR #28) |
| Database schema / migrations | 0 |
| Frontend production changes | 0 |
| Network / filesystem / Vault access by policy | 0 |

This phase freezes Host-owned vocabulary so a future verifier, publisher
registry, and revocation distributor do not invent a second trust model.
Shipping these modules does not enable execution.

Related: [plugin_security_model.md](plugin_security_model.md),
[plugin_runtime_foundation_phase1.md](plugin_runtime_foundation_phase1.md),
[plugin_sdk_v1.md](plugin_sdk_v1.md).

## Invariants

```
TRUST != AUTHORIZATION
SIGNATURE != EXECUTION
VERIFIED != SANDBOX READY
```

- A signature field existing is **metadata present**, never trust.
- `PluginTrustState.VERIFIED` does **not** grant capabilities, does **not**
  start a worker, and does **not** mark the OS sandbox ready.
- `UNVERIFIED` and `INVALID` are different states. Missing evidence is not a
  failed signature.
- `execution_supported` is structurally `false` on every `PluginTrustDecision`.

## Implemented in this phase

| Surface | Module |
|---|---|
| Publisher identity | `PluginPublisherIdentity` in `app/plugin_trust_contracts.py` |
| Signature metadata | `PluginSignatureDescriptor` (present ≠ verified) |
| Closed trust states | `PluginTrustState` (`UNVERIFIED`, `VERIFIED`, `REVOKED`, `INVALID`, `UNSUPPORTED`, `EXPIRED`, `UNKNOWN`) |
| Immutable decision | `PluginTrustDecision` |
| Host-owned verification facts | `PluginVerificationEvidence` |
| Revocation records | `PluginRevocationRecord` (publisher / key / package) |
| Verification provenance | `VerificationProvenance` |
| Digest contract | canonical `sha256:<hex>` only |
| Pure trust policy | `evaluate_plugin_trust` in `app/plugin_signature_policy.py` |

These types are serializable, `extra=forbid`, and frozen. They reject secret
fields, raw signature bytes, certificates, command fields, and plugin-controlled
logs.

## Trust states

| State | Meaning |
|---|---|
| `UNVERIFIED` | No signature, or signature metadata without host verification evidence |
| `VERIFIED` | Supported scheme + known publisher + bound MATCH evidence. **Not executable** |
| `REVOKED` | Host-owned revocation of publisher, key, or package/version/digest |
| `INVALID` | Bound evidence does not match (wrong plugin, wrong digest, MISMATCH outcome) |
| `UNSUPPORTED` | Signature scheme is not in the host allowlist |
| `EXPIRED` | Otherwise-matching evidence is past `expires_at` |
| `UNKNOWN` | Publisher is not in the host-owned known-publisher set |

## Fail-closed policy (pure)

Inputs are already parsed facts. The evaluator never calls the network,
filesystem, database, Vault, Provider, or a subprocess, and never runs
hashlib / HMAC / Ed25519.

| Input | Result |
|---|---|
| Missing signature | `UNVERIFIED` / `SIGNATURE_MISSING` |
| Unsupported scheme | `UNSUPPORTED` |
| Unknown publisher | `UNKNOWN` |
| Signature metadata, no evidence | `UNVERIFIED` / `EVIDENCE_MISSING` |
| Evidence bound to the wrong plugin id or version | `INVALID` |
| Claimed digest ≠ evidence digest | `INVALID` / `DIGEST_MISMATCH` |
| Evidence `outcome=MISMATCH` | `INVALID` / `SIGNATURE_MISMATCH` |
| Revoked publisher / key / package | `REVOKED` |
| Matching evidence past `expires_at` | `EXPIRED` |
| Valid supported verification evidence | `VERIFIED` and `execution_supported=false` |

Revocation is Host-owned policy input. This phase does not fetch a CRL or OCSP
response. A future-dated `effective_at` is not yet active.

`PluginVerificationEvidence.outcome` is a **host-owned assertion** that a
future verifier would produce. This module does not compute it.

The allowlisted scheme id `ed25519-detached-v1` is vocabulary for that future
verifier. It is not an Ed25519 implementation.

## Digest contract

Accepted form:

```
sha256:<64 lowercase hex>
```

- Algorithm names are allowlisted. Only `sha256` is accepted.
- Weak algorithms (`md5`, `sha1`, …) and unknown algorithms are rejected.
- Unprefixed hex is rejected. The algorithm must be explicit.
- Malformed values fail at contract parse time (`PLUGIN_DIGEST_MALFORMED`).

## Provenance

`VerificationProvenance` records:

- what was examined (`manifest_digest`, `package_digest`)
- which policy version evaluated it
- which verification scheme was named (`none` when no signature)

It must not contain private keys, credentials, API keys, or arbitrary
plugin-controlled logs.

## Execution safety

The following remain true for every decision, including `VERIFIED`:

| Flag | Value |
|---|---|
| `execution_supported` | `false` |
| `sandbox_ready` | `false` |
| `broker_ready` | `false` |
| `worker_ready` | `false` |

No code path in this phase loads Python, JavaScript, a native DLL, a shell,
PowerShell, or a plugin executable.

## Not implemented / future layers

Keep these as separate layers. This branch does not start them.

1. **Real signature verifier** — host-owned Ed25519 (or reviewed equivalent) that *produces* `PluginVerificationEvidence`.
2. **Publisher key registry** — durable mapping of `publisher_id` → `key_id` material, still without putting secrets on these contracts.
3. **Revocation distribution** — signed revocation lists, CRL/OCSP, or an online lookup service that *feeds* `PluginRevocationRecord`.
4. **Capability Broker** — request ≠ authorization; see [plugin_runtime_foundation_phase1.md](plugin_runtime_foundation_phase1.md).
5. **OS Sandbox** — AppContainer / LPAC / independently reviewed equivalent. Windows Job Object is not a sandbox.
6. **Executable Plugin SDK** — still disabled. `execution_supported` stays false until broker + sandbox + worker are ready **and** a later authorization decision says so.

Trust verification must never automatically authorize execution.

## Ownership

| Allowed new production | `app/plugin_trust_contracts.py`, `app/plugin_signature_policy.py` |
|---|---|
| Tests | `tests/test_plugin_trust_contracts.py`, `tests/test_plugin_signature_policy.py` |
| Docs | `docs/plugin_trust_signing_foundation.md` |

This work is independent of Windows AppContainer (PR #26), Model Center runtime
control (PR #28), Provider Runtime 2.0, DesktopHost, and third-party plugin
execution.
