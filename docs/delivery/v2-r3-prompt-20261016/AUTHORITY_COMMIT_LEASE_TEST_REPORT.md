# Original authority commit lease regression probes

Additive source: `tests/test_v2_authority_commit_leases.py`. The initial seven probes changed no application source or frozen tests. The later resolver deadlock correction below changes only `app/trusted_sessions.py` among application files.

Pinned isolated File verification: **7 passed in 4.45s**, pytest 8.4.2, runner label `r3-authority-leases-file-r1`. Original runner receipts are retained in `docs/delivery/v2-development` and copied exactly beside this report. This is a focused contract result, not PostgreSQL or browser acceptance.

All seven child logs and PID/exit receipts are also copied under `authority-lease-child-receipts-r1`; every retained child receipt records return code 0, no timeout and `child_stopped=true`. The runner's full source receipt reports `sources_changed_during_check=false`.

Four probes use the real `TrustedSessionResolver` and thread event barriers: concurrent original `revoke` / `register` calls wait for `binding_lease` to exit, `binding_generation` and the resolved actor remain unchanged inside, then resolve fails after revoke or returns the new actor/session and a newer generation after rebinding. Both normal and exceptional callback exits release the lease.

Three probes use original File repositories to exercise workspace rename, creation and initial provisioning. A bounded authority holder takes the original authorization lease; a competing original workspace operation reaches its real authorization acquisition boundary. The holder must still acquire the workspace lease and exit, after which the operation must finish. Persisted workspace, active membership, admin role and audit entries are read back through their original owners. This catches the previous workspace-before-authorization inversion by behavior rather than source-text assertions.

All threaded races run inside separately launched, owned child processes. Child threads have bounded joins; a child with blocked threads exits with an explicit deadlock receipt. The parent also has a 22-second deadline and terminates/kills only its exact launched child on timeout, recording the PID, return code and stopped state with its retained child log. No hung probe thread remains inside pytest. The probes create no model jobs, change no production adoption gate and use no external service.

The tests are frozen for the security agent's final combined snapshot. No PG cluster or browser process was started by this slice.

## Owner-held session read regression and correction

Final read-only review found a concrete lock cycle: a normal graph/storage guard can hold the original asset/project lease and call `TrustedSessionResolver.resolve`, while a Prompt commit held the resolver's global registry lock through `binding_lease` and waited for that same asset lease. This affected same and different session tokens in the same API process.

Four additive probes now use the actual `AssetLibraryService.project_scope` and `CreativeProjectStore.owner_lease`, with barriers set only after each original lease is held. They cover same/different tokens and normal/exceptional callback exits, including subsequent session mutation and asset-owner reacquisition. They use no replacement asset lock.

- **RED, `r3-authority-asset-red-r1`:** all four probes fail against the original resolver. Each child retained `deadlock=true`, `asset_held=true`, `binding_held=true` and exited 2 after bounded joins. Pytest returned 4 failed / 7 deselected. All four child logs and PID/exit receipts are preserved under `authority-asset-red-child-receipts`.
- **Correction:** the original resolver now uses a separate reentrant `_binding_mutation` mutex for `register`, `revoke` and `binding_lease`. `_lock` remains a brief registry read/update lock and is not held across storage callbacks. The same original registry, generations, actors and public methods remain in use.
- **GREEN, `r3-authority-asset-green-r1`:** all eleven lease probes pass in 6.59s. The full runner source receipt is stable. All eleven child logs and PID/exit receipts are preserved under `authority-asset-green-child-receipts`; every child returned 0 and stopped.

RED's global `sources_changed_during_check` is true solely because the unrelated `tests/test_v2_prompt_process_revocation.py` changed during that run; it was not selected. Both the resolver and this additive lease test were individually unchanged during RED. RED's final source snapshot and GREEN's snapshot differ at exactly `app/trusted_sessions.py`; its SHA-256 changed from `ab2fcd0266310cb9a6fbbf5d642066aed8d6a767a706b7f19bdc118511717c34` to `11f2520cade262fae3317e23c4379b0d376359faecc1df33160a4f1ba80c67bd`. The complete RED receipts remain intact rather than being represented as globally stable.

Security confirmed its earlier API/Vite/PostgreSQL processes were stopped before these source changes. This slice did not restart them. Final integrated File/PostgreSQL/browser acceptance after the resolver correction belongs to the security agent's later receipts; these focused probes do not replace it. Production Prompt adoption remains closed.
