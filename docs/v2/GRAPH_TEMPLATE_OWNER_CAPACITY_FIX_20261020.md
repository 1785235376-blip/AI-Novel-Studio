# Template review F1: original owner-compatible capacity admission

Finding: new visual-template append at `3300636a` could admit JS JSON of 95,998
bytes that the unchanged Python GraphInput normalizes to 96,032 bytes and
rejects. This finding belongs to the new visual append path; it is independent
of the inherited same-batch confirmation issue (F2), which remains a separate
fix and is not accepted by this commit.

After all target/source nodes, edges, groups and notes are combined, the adapter
now calls the existing `graphNoteDefinitionBytes` admission estimator. This is
the original note owner's conservative reserve for JS/Python numeric spelling,
including Pydantic float coercion. The catalog and backend 96,000-byte limits,
portable file limit and original decoder remain unchanged. No new serializer,
storage owner or execution path was added.

Regression: the exact review shape at 31,223 target Chinese characters is
rejected before confirmation; a real-controller integration verifies that the
target reference and both history stacks remain unchanged. The adjacent valid
control at 31,207 characters has JS 95,950 bytes and conservative admission
95,998 bytes, and remains accepted. Existing template regression stays intact.

Evidence in sibling `template-p2-evidence-20261020`: initial RED (4 failed / 1
passed across both findings), F1 targeted run (34 passed / 3 files), and original
GraphInput validation of the independent review's unchanged payload. Normal
validation rejects the bad payload, accepts the adjacent control at 95,984
canonical bytes, and accepts the node-only control at 94,851 bytes. No
`model_construct`, API, Save, storage, provider/model or GPU execution is used.
The original backend model source SHA256 matches the review's fixed source.

This is targeted capacity/type evidence, not Host/PG/Windows E2E, generated media
or full product acceptance. Original 330 evidence and the independent review
directory were read-only. The pending Storyboard slice remains frozen in its
other worktree; no Storyboard, DSH or public-build file changed in this fix.
