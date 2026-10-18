# Model Center controlled transfers: partial M3 infrastructure

## Delivery boundary

The original `ModelCenterService` now owns a bounded single-file GGUF transfer
lifecycle. Its production instance has **no reviewed sources and no destination**.
The existing catalog therefore has **no newly downloadable models**. This change
does not complete M3, Windows support, model installation, repair, or runtime
readiness. Existing discovery, registration, enablement and runtime diagnostics
retain their separate owners.

The mechanism can be verified independently using synthetic bytes and injected
transport, disk-capacity and clock boundaries. Making a real model downloadable
still requires genuine, independently reviewed publisher/license/model-card
evidence, an immutable artifact URL and revision, an exact byte size and SHA-256,
and an explicitly selected private destination. Legacy catalog hashes, Ollama
names and historical local validation are not a download manifest. No production
URL, digest or license has been invented or populated. There is no browser-facing
manifest import, arbitrary URL, destination-path or credential input. The only
configuration seam is trusted server composition with `ReviewedTransferSource`
objects and an existing destination directory; this slice does not expose a
production provisioning UI or configuration loader.

## Original ownership and admission

- `app/model_center/transfers.py`: the Model Center single-artifact lifecycle.
- `transfer_types.py`: closed source, confirmation and version contracts.
- `transfer_files.py`: descriptor-confined storage of this owner's files only.
- `transfer_transport.py`: pinned public-address HTTPS transport.
- `transfer_api.py`: the original host-authorized API composition, mounted at
  `/api/model-center/transfers` and `/api/v1/model-center/transfers`.
- `frontend/src/modelcenter/ModelTransferPanel.tsx`, its client and decoder:
  additive controls in the existing Model Center panel.

All routes reuse the current Host/session authority, binding generation, direct
origin/forwarded-header restrictions and `narrative_production_v2` feature gate.
The same captured authority is checked throughout a running transfer. `main.py`
classifies these host-global routes alongside local discovery before the
project-only collaboration allowlist. This classification does not remove any
Host, session, origin, forwarded-header or feature checks. Private/no-store
headers also cover rejection responses. There is no role-string fallback or
invented project task.

The filesystem helper reuses the existing mutation coordinator's in-process
lock. Descriptor-based `flock` coordinates short metadata mutations and a
separate held-directory lease permits only one transfer worker across instances
and cooperating processes. It does not expand asset-store admission, project
storage quota, the task scheduler or runtime loading ownership.

## Transfer and recovery contract

1. Reading or opening the UI does not start a transfer. The UI requires an
   explicit read, source selection, preview and confirmation. A preview binds
   the exact source, destination, principal, expiry and digest. It expires after
   120 seconds. Repeating its confirmed start returns the original task while
   that preview is still valid; unknown write results are not automatically
   retried.
2. Transfers require a reviewed single `.gguf` artifact, 8 bytes through 64 GiB.
   The private owned layout is `.studio-model-transfers/<task-id>/`, containing
   a journal, `partial.gguf` and, after verification, `model.gguf`. No existing
   destination is overwritten. At most 16 source entries, 16 live previews and
   16 retained task records are admitted. Cleaned records still count toward
   that bounded record limit; receipt pruning is not implemented.
3. Capacity admission uses free bytes on the selected filesystem, a 64 MiB
   reserve and the configured owner-local byte quota (64 GiB by default). The
   quota includes this task's existing partial bytes, uncheckpointed tails,
   other retained artifacts and active reservations. Resume requires only net
   additional growth; streaming checks current capacity again after a blocking
   read and before writing. Capacity is not a physical filesystem reservation:
   unrelated disk consumers can still cause ENOSPC, which pauses the task.
4. Pause/cancel are versioned cooperative requests. `PAUSING`/`CANCELLING` mean
   the stream has not stopped yet. A terminal paused/cancelled status is written
   after the stream context closes; cancellation retains owned partial bytes.
   Shutdown requests a cooperative stop and does not claim all workers have
   already stopped. Transport timeouts bound waiting network phases.
5. Resume requires explicit confirmation of the original task, current source
   identity and task version. Existing prefix bytes are rehashed before any
   network use. Only verified, exclusively owned uncheckpointed tail bytes may
   be truncated. A nonempty partial requires a matching strong ETag and exact
   range response. A fully received artifact can be reverified without network.
6. Completion requires a fresh full SHA-256 pass, exact byte count, unchanged
   file identity/signature and a minimal GGUF magic/version check. Publication
   uses a non-overwriting same-directory link, verifies the actual published
   leaf and then removes the owned partial name. This proves verified bytes,
   not model compatibility, architecture validity, safe inference or readiness.
   No artifact is executed, loaded, registered, enabled or selected by transfer.
7. No worker lease after a restart converts an active journal to `INTERRUPTED`
   during an authorized read. No transfer automatically resumes. A publication
   whose completion journal was lost can be explicitly resumed and reverified
   without downloading again. Stable failure codes exclude raw paths, URLs,
   response bodies, headers and credentials.
8. Cleanup requires a separate, expiring preview and confirmation bound to the
   exact task version and partial-file signature. It only removes that stopped
   task's verified owned partial name. Completed artifacts, external files,
   arbitrary directories and task journals are never deleted by this API.
   Durable cleanup intent allows a later read to acknowledge an already removed
   partial if the final metadata write was interrupted.

Crash recovery is deliberately bounded. An interruption before `owner.json` or
the initial task journal exists fails closed; the owner does not infer ownership
or delete the unknown directory. Other valid task records remain visible when
an incomplete task is encountered, while new start/resume admission is blocked.
Up to two regular, bounded interrupted journal temporaries inside an otherwise
valid task are retained and do not prevent binary verification. Unknown layouts
or further metadata debris require explicit operator review outside this slice;
there is no automatic recursive cleanup or general crash-repair claim.

## Network and filesystem safety boundary

The production transport resolves once, rejects the response if **any** DNS
answer is non-public, and connects to one validated numeric address. TLS verifies
the original hostname with the platform's verified certificate context. It has
no private-host exception, proxy, cookie jar, authentication, redirect follow,
reconnect or automatic retry. Compressed/chunked and inconsistent-length
responses are rejected. Resume requires exact 206 range/total bytes and the same
strong validator; 200 fallback cannot overwrite a prefix. DNS, connect, I/O and
overall time limits are bounded. Offline tests replace DNS/socket/TLS seams and
do not contact a real host.

The initial filesystem implementation is POSIX-only, requiring descriptor-relative
operations, no-follow opens, stable inode/device identity, regular files and
owned non-group/world-writable directories. Root identity and all child handles
are revalidated; symlinks, hardlink ambiguity, special files, unknown layout and
unexpected replacement fail closed. Publication and cleanup recheck the actual
leaf at the relevant operation boundary, including after caller callbacks.

**Concurrency/threat limit:** supported writers are this owner and cooperating
processes using its locks. Hostile concurrent processes running as the same OS
user, a privileged administrator, compromised filesystem semantics and remote
filesystems are outside the accepted threat boundary. POSIX cannot atomically
compare an inode and unlink a pathname. A held descriptor and an earlier inode
check are not a proof against an adversarial same-UID swap between the final
check and link/unlink. Private directory permissions exclude other ordinary OS
users; descriptor-relative operations prevent symlink/ancestor redirection to
external targets. Fault-injection tests verify observed replacement rejection
and no false completion, not arbitrary-race immunity.

Windows is explicitly unsupported and fails closed. Native Windows acceptance
requires handle-based volume/file identity, reparse-point rejection, share-mode
and atomic publication/removal guarantees, low-disk/cancel/restart fault tests,
and target-device integration verification. This POSIX implementation must not
be represented as Windows-ready controlled download support.

## Verification and acceptance

All transfer checks use deterministic synthetic GGUF-shaped bytes in temporary
owned directories with injected transport, disk and clock. They cover complete,
paused, cancelled, interrupted and failed states; preview/authority/version
retirement; malformed/mismatched content; resume prefix/validator integrity;
quota and post-read disk pressure; source/path/leaf changes; bounded restart and
cleanup recovery; and both API mounts. HTTPS tests use fake DNS/socket/TLS
objects for public-address pinning, private/rebinding rejection, no redirect,
header/range/size limits, timeout/cancel and close behavior. Additive UI tests
cover explicit operations, empty defaults, strict decoders and stale/unknown
results without mount-triggered work.

Source-bound receipts and logs are retained under
`docs/delivery/v2-development/model-transfer-*`. Earlier failed development
receipts remain visible; later passes do not erase them. Existing Model Center,
discovery authority and storage-admission regressions are included in the final
focused backend check. Shared build/PUBLIC checks are coordinated separately.

Real upstream transfer, actual model integrity, Windows, GPU/inference,
production source provisioning and browser visual acceptance are **NOT_RUN**.
The browser launch restriction was respected. No actual model, credential or
account was used during implementation or verification.
