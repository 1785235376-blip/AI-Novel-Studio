# Reviewed video-only Storyboard Timeline creation

Contract: `studio-storyboard-video-timeline/1`. This additive path uses the existing StoryboardWorkspace, reviewed Video job / formal Asset provenance, ProductionExecutionService and original Timeline storage. It requires no image binding. Existing image-first creation and mapped-video replacement remain independent contracts.

## Explicit selection and preview

Select 1–4 unique shots from one saved, approved Storyboard, in the intended edit order. Supply the document version/content digest and exact shot version/digest, plus `in_ms`, nullable `out_ms` and explicit `include_audio` (default false). A null out point means the actual decoded full duration, rather than the authored shot estimate. The UI uses a 1280×720 / 24fps canvas; all sources remain pinned formal videos.

`POST /documents/{id}/storyboard/video-timeline/preview` is read-only under the original trusted Host, scope, domain.read and Asset owner guards. It resolves only the stored reviewed video results; callers cannot inject job/asset identities. It decodes the real bytes through the existing inspector, reports duration, dimensions, format and codec, validates trim bounds and the original total-byte/ten-minute limits, then rechecks source and authority. It never calls a provider.

The preview includes the normalized original Timeline, selected shot/job/Asset pins, measured metadata, ordered contiguous clip starts and a scope/actor-bound preview digest. The optional inspector dimensions do not change default responses of existing callers.

## One human-confirmed Save

`POST .../create` requires the exact preview digest and a fresh request_id. The UI presents order, trims and pins, then requires a separate confirmation. The original writable scope/Asset/project phase rechecks metadata and calls original Timeline Save once. The initial origin and independent `storyboard_video_create_receipt` are attached inside that same transaction; authority/capacity failures roll back the complete Timeline. No Storyboard edits, model calls, render requests, Graph changes or partial jobs/assets are created.

The old `storyboard_origin` mapping is retained for original replacement compatibility. This path does not reuse or reinterpret `storyboard_create_receipt` from image-first creation. Original Timeline history remains the owner of later edits. The persisted proof binds the initial v1 timeline, original source, full creation intent and exact shown preview.

## UNKNOWN and reopen

`GET .../creations/{request_id}` reads the original durable receipt and current Timeline under the original current Host/permission/incarnation guards. It remains read-only. The same key and identical full payload replay the prior result before attempting new source work; a changed payload conflicts. Later Timeline edits preserve the original creation proof.

The UI retains an uncertain create intent and request key. It permits an explicit lookup or explicit same-key retry, never automatic repetition or a new key. Source/client/permission/active ABA, stale consent/form callbacks, duplicate apply and late results are fenced; unresolved request identity is carried by the original leave-risk boundary. Dirty or busy author forms cannot admit a new operation.

## Verification scope

Targeted tests use tiny CPU-generated WEBM bytes and synthetic HTTP responses through original reviewed job/Asset owners, including original mounted `/api` and `/api/v1` Host/File routes. They are not GPU/model-quality, PostgreSQL, live-provider or whole-V2 acceptance. Browser component evidence uses fixed real CPU captures and mocked transport; authenticated live-Host browser Save is a separate outstanding acceptance.
