# Two-image portable reference recovery

This bounded extension uses the existing Portable Projects panel and service.
Select chapters containing exactly two available formal Studio images and choose
one current `REFERENCES` relation. The opt-in format is
`AI_NOVEL_PORTABLE_IMAGE_REFERENCE_1`; the ordinary export request and
`AI_NOVEL_PORTABLE_1` manifest/ZIP encoding retain their original semantics.

The new manifest carries two media aliases and one descriptive relation only.
Its selection digest binds the current source snapshot without exporting project,
asset, relationship or actor identities. It does not copy derivation, approval,
grants, provenance history, Graph or Timeline documents. Images are byte-verified
and imported as new incarnation-bound Studio assets through AssetLibraryService.
The manuscript subset is still restored through the original ChapterService;
this does not bridge Studio assets into legacy unbound media endpoints.

Restore the media into a new local project first. Open that project through the
existing Studio entry, then return to the portable record and request a relation
preview. The preview resolves aliases exclusively through that record's saved
new asset map and checks both original project authorities, source/destination
incarnations, exact local scope, asset kind, formal visibility, version and SHA.
The author then separately confirms that exact preview. No navigation, activation,
relation write or job dispatch occurs automatically.

`reference-preview` and `reference-confirm` are under the existing
`/novels/{nid}/experimental/portable-projects/records/{rid}` API. They require
the existing trusted local Host session and both existing feature flags.
The target comes from the owned restore record, never from a request-supplied
project or asset ID. Both API prefixes reuse the original authorization stack.

The single original `AssetRelationshipAdapter.add` call performs source CAS,
target version/digest checks, duplicate denial and the actual metadata write.
It creates a fresh author declaration, identity and timestamp. The existing
portable record is durably changed to `APPLYING` before the call. Readback checks
the original relationship record and current target before recording `RESTORED`.
Any interrupted/uncertain attempt is retained as `UNKNOWN` (or `APPLYING` if the
process died); neither state admits preview/confirmation replay. Inspect the new
project through its original asset relation entry. Nothing automatically deletes
the new project, image bytes, alias map or recovery input.

Owners changed: `portable_projects.py`, `portable_projects_api.py`, the existing
Panel/client, and one dependency assignment in backend `experimental/api.py`.
`workspace_relationships.py`, the asset owner, App routing, global locks, flags,
Graph/Image execution, DSH/Ink and dependencies are unchanged.

Validation is scoped to File, API and frontend tests. A frozen legacy ZIP vector
was measured against the actual df07 codec (SHA256
`bbc13f452e9545161c3c9073aeca6f29a833a4fab4b2dde54bf16c201182d188`).
The delivery evidence retains failed attempts, the final test logs and real React
component screenshots at 1366x768, 1440x900 and 1920x1080. Browser replies and Host
sessions are synthetic. PostgreSQL, a native real Host and the full installed
Windows journey remain unverified. The existing native symlink case is blocked
by Windows error 1314; its failed original log is preserved, not counted as pass.
This closes one portable image reference slice, not all U14 or a full project
backup/restore product gate.
