# Saved screenplay EPUB contract

The existing GET `/api/novels/{nid}/experimental/creative/documents/{rid}/screenplay-export`
(and `/api/v1` alias) accepts `format=epub` with the same required saved
`expected_version`. Successful bytes have `application/epub+zip`, a safe generated
filename, no-store/nosniff and the existing version/document-digest/content-SHA256
headers. Authorization, stale source/version and feature-gate error models are
unchanged. Encoding cannot mutate a document, its history, manuscript or Canon.

The existing saved SCREENPLAY selector gains “EPUB 电子书”. Unsaved/uncertain state
remains blocked. The same authenticated download client validates the response
before creating a Blob, and the same keyed component discards late results when
the originating saved document changes. Generic Script EPUB is not enabled.

EPUB3 contains one shared content/spine document with one navigable section per
scene, not one spine document per scene. Headings, context, action, speaker,
delivery and dialogue are text projections. Existing export provenance remains
allowlisted; JSON is required for complete structured metadata. The existing
encoder uses zh-CN package language, trims headings and normalizes line endings
into paragraphs. It does not translate text or claim a professional page layout.

XML-invalid authored/provenance text returns an explicit unrepresentable-text
error before the shared encoder can remove characters. No external media/font,
network access, model, package install or additional export queue is involved.
No reader-specific or EPUBCheck certification is implied by ZIP/XML tests.
