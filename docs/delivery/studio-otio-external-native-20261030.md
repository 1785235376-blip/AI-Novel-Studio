# Explicit external-native OTIO import (backend only)

`POST .../studio/production/timelines/{tid}/transfer-preview` and `transfer-import`
accept optional `otio_edit_mode`: `STRICT` (default) or `EXTERNAL_NATIVE`.
Nondefault mode is valid only for OTIO IMPORT. Both existing API prefixes apply.
There is no frontend toggle or NLE integration claim in this delivery.

## Review protocol

1. Supply original OTIO content, explicit current formal media bindings, current
   target version/digest and `otio_edit_mode: EXTERNAL_NATIVE` to preview.
2. Review **all** `loss_report` entries and the normalized timeline. Opt-in results
   include `otio_edit_mode` and SHA256 of the original content UTF-8 bytes as
   `input_sha256`. The existing input digest binds all request options, including
   mode; preview digest additionally binds target, sources and project context.
3. Import the same content/options/mode with reviewed preview digest, unique
   request ID and `acknowledge_losses: true` (required even without actual loss).
   Existing final source/auth/lock checks and transactional CAS still apply.
   Changed content (including whitespace), options, target, source pins or
   project context require a newly reviewed preview; no automatic write/replay
   is authorized by a stale digest. Exact accepted request replay retains the
   existing idempotent result and revalidates sources and authorization.

## Deliberately bounded compatibility

Only valid-but-stale `ai_novel_studio_exchange_v1` Clip/Gap `start`/`duration`
precision hints and Clip `speed` hints may be discarded. Each discarded hint
produces a stable indexed LOSS entry, with no source paths, names or values.
Changed or removed native linear speed effects are read from native OTIO.
Native fractional milliseconds and rounded/unsupported speed values reject.
All recognized precision payloads are structurally/rationally validated first;
malformed, out-of-range and invalid hints are not repairable by opting in.

Global-start, transition-offset and media-reference available-range hint
mismatches remain strict. Other existing unsupported features retain their
existing loss or rejection behavior. This mode does **not** promise arbitrary
external edits are representable. Declared available-range checking remains
unchanged; it is not proof of probe-derived actual media duration.

The separate `ai_novel_studio_timeline_v1` extension is never blindly stripped:
its schema is validated, and restoration requires both matching native
projection digest and re-derived projection/source bindings. Stale valid Studio
metadata follows the existing native conversion plus explicit loss receipt.
Source references never grant authority: formal source identity, project and
incarnation, current source version/hash, target locks, final authorization and
CAS continue through the original owners.

Default strict input digests and successful response shape remain unchanged
(including explicitly supplying STRICT). Strict conflict422/code/message remain.
The prior read-only diagnostic's capability status is now truthful:
`EXPLICIT_OPT_IN_AVAILABLE` only for eligible integer-ms Clip/Gap conflicts,
otherwise `NOT_AVAILABLE_FOR_THIS_CONFLICT`. This is not whole-file validation
or frontend capability discovery; source/remainder status remains NOT_EVALUATED.

No frontend, audio capacity/history owner, external GitHub branch, merge,
Release, blocked publication primitive or Windows ACL/junction probes touched.
