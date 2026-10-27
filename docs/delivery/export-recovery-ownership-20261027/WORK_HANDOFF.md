# Original Export owner execution ownership

This slice is based on published backend `048fe2a12212df85c272cdc0741659498378d334`. It is independent of the three later TaskCenter TTL/single-reader slices; do not replace their work or frontend code. Port the two production files plus applicable tests from the eventual fixed publication commit, then run the affected owner/TaskCenter consumers on the combined source.

Production scope:
- `app/services/export_job_service.py`: acquire a per-job execution claim before startup recovery mutation or local executor submission; retain original short workspace mutation locks and all original permission-context projections.
- `app/services/export_execution_claim.py`: private nonblocking, same-host File claim with canonical root/job identity, process-local registry, OS lock and idempotent release. No API, permission or durable job schema changes.

Do not hold the whole queue's mutation lock across exporter calls. Do not replace OS ownership with PID checks or a guessed TTL. Do not remove callback release for a cancelled queued Future, or release before artifact/final state persistence. Do not unlink lock files as cleanup: another holder can still have the old inode.

The create-commit to submit interval permits another recovering owner to claim and execute that queued job first. Only one cooperating owner executes it; creator-process affinity is not promised. A later startup is still needed to recover an executor that dies after another process has already scanned and skipped it. This is not a polling recovery coordinator.

The filesystem coordination directory `.export-execution-locks` is created only by execution/recovery paths, not get/list. Empty/terminal-only startup does not add execution locks. Individual lock files remain on disk after release by design.

Limits: POSIX same-host tests only; Windows and network/distributed filesystems are NOT_RUN. Live fork-without-exec while claims are held, mixed old/new worker versions, and external replacement/deletion of coordination facilities while a claim is held are outside this guarantee. Acquisition-time path checks are not a full-lifetime anti-tamper guarantee. A process crash after an exporter external effect can cause replay: no exactly-once external-effect claim.

Do not infer that this fixes the separate asset pagination 409, F37 observations, old Windows asset-list 503, frontend browser integration, real models, PG or CI. No main merge, force push, Release, deployment or hosted CI run is included.
