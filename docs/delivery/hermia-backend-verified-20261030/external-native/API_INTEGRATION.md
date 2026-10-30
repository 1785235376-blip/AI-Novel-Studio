# Backend API integration handoff (frontend not implemented)

Endpoint prefix can be `/api` or `/api/v1`.

Example preview request to
`POST /api/projects/{project_id}/studio/production/timelines/{timeline_id}/transfer-preview`:

```json
{
  "expected_version": 1,
  "reviewed_timeline_digest": "<current target digest: 64 lowercase hex>",
  "direction": "IMPORT",
  "format": "OTIO",
  "content": "<original unmodified UTF-8 OTIO JSON text>",
  "media_bindings": [
    {
      "reference": "<exact opaque media reference in OTIO>",
      "source_snapshot": {
        "kind": "ASSET",
        "id": "<formal asset id>",
        "version": 1,
        "digest": "<current asset SHA256: 64 lowercase hex>",
        "asset_kind": "video"
      }
    }
  ],
  "otio_edit_mode": "EXTERNAL_NATIVE"
}
```

Use actual current versions/digests, not these placeholders. Existing Host and
session authorization headers remain required. Import to the corresponding
`transfer-import` endpoint with precisely the same preview input fields plus:

```json
{
  "request_id": "native-edit-confirmation-001",
  "reviewed_preview_digest": "<preview response preview_digest>",
  "acknowledge_losses": true
}
```

A preview is not authorization to import a mutated file. Do not normalize JSON,
strip metadata, change mode or bindings, or auto-submit after409/422. Require a
new explicit review when current sources/target/context change. Preserve exact
request for idempotent retry after an uncertain successful submission.

## Consumer contract

| Surface | Strict/default | EXTERNAL_NATIVE |
|---|---|---|
| Successful preview shape | Existing fields unchanged | Adds `otio_edit_mode`, `input_sha256` |
| Input canonical digest | Existing six input fields; omit default mode | Include explicit mode with all existing fields |
| Preview digest | Existing context+result binding | Also binds new mode/hash fields, loss report and normalized output |
| Confirmation | Existing loss acknowledgement rule | Explicit acknowledgement required even if no losses |
| Persisted transfer receipt | Existing shape retained | Existing digests cryptographically bind mode/hash/report; no new visible receipt fields |
| Existing frontend parser | Supported unchanged | Not integrated; closed parser currently rejects additive fields |
| Global/transition/reference hint mismatch | Reject | Reject (not eligible) |
| Malformed or out-of-bounds hint | Reject as applicable | Reject, never a repair bypass |
| Native fractional ms/unsupported speed | Existing bounded contract | Reject; never round to fit |

Frontend owner must separately implement explicit selection, capability-aware
response decoding and full loss review. No silently changed default, automatic
compatibility retry, or inferred permission from `EXPLICIT_OPT_IN_AVAILABLE`.
The diagnostic only describes one conflicting hint; source/remainder validation
is NOT_EVALUATED. Application integration and UI activation are not delivered.
