# Reviewed request receipt forwarding repair

Hosted source `9bdae526df25eaeef254c6992ddab5240d69fadc` passed 43 of 45 R4 browser journeys, including the six new registered-model/media/audio journeys. The remaining U08 journey exposed an actual App integration defect after successful per-source exclusion preview: AiWritingPanel passed its reviewed receipt as the fourth onGenerate argument, but App's three-argument wrapper discarded it. That selected the legacy generation call and lost the reviewed request scope. Earlier green tests did not cover this exact single-request App path.

The successor forwards the receipt unchanged and refuses legacy fallback from App when the request inspector is enabled but the receipt is absent. A real App regression now verifies the original author-context/generate endpoint receives exact source exclusion identities/digests and the reviewed preview/request IDs, and that api.generate is never called. A separate missing-receipt case verifies no request is sent. Existing server preview/source/version/actor/privacy/final-dispatch checks remain unchanged; the browser journey now explicitly asserts that no legacy generation endpoint was called.

Local successor frontend aggregate: 1045 passed, six optional HTTP skips; TypeScript/build/token guard pass. The retained browser journey still requires exact hosted verification. The separate U03 failure was an incorrect assumption that chapter creation returns a version: it now retrieves the original saved document and checks its positive version before later search/stale assertions. No stale-source or exclusion assertion was removed.

Only disposable synthetic manuscripts/providers were used. There is no claim that any real user's source was transmitted. This is ordinary correction of observed integration behavior, not closure of the platform-blocked independent review.

## Evidence transport

The full 9bdae frontend artifact is 34,808,465 bytes, exceeding the supported local file downloader's 32 MiB maximum. A direct fetch of its generated URL returned HTTP 403 and was stopped without retry or alternate access to that resource. Its full trace bytes were NOT inspected. The independently available compact artifact, hosted failure logs and current source were inspected.

The authorized successor CI produces separate source-labelled PNG groups, each at most24MiB of original image bytes plus a small manifest, without editing images. The original full trace/receipt artifact and its history remain intact. Capacity/oversize errors are explicit rather than dropping evidence; compact reports exclude only the newly prepared duplicate PNG directory. This provides a supported connector route for future newly produced evidence, not a retry of the denied URL.
