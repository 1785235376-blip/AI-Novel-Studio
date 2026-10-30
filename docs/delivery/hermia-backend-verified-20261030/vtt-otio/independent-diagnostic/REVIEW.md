# Independent conservative OTIO precision-diagnostic review

Scope: existing Studio transfer-preview error boundary only. Strict importer/attachment behavior is not relaxed. No reparse, ignored precision metadata, compatibility mode, media fetch, new endpoint or persisted records.

Existing HTTP422 already provided EXPERIMENTAL_INVALID / OTIO_EXACT_TIME_METADATA_MISMATCH; it lacked location and conflicting field's native-ms representability. This is a diagnostic enhancement, not permission to import edited files.

Independent review found one intermediate implementation regression: using seconds(fallback) to classify diagnostics revalidated large native fraction denominators and replaced the original mismatch error with OTIO_RATIONAL_LIMIT for native 0.3333333333333333 frames at25fps. Reported before freeze; implementer changed the classifier to arithmetic over already-computed fractions without invoking new validation. Regression fixtures cover the original error string and strict write response.

Independent cases: both API prefixes, start/duration conflicts, integer/fractional native milliseconds, high-denominator floating-point representation; unchanged strict import422 body and full File-store snapshots; value-free diagnostics with no title/clip/source values. Native parser cases cover root absent global-start, media available-range start, transition in-offset and high-denominator clip start. All paths originate from parser indices, not client names.

Native-time status describes only the first conflict's field, never whole-file importability. Source and remaining timeline validation explicitly NOT_EVALUATED. Transition first-conflict fixture intentionally has unvalidated remainder, checking that no success/compatibility inference is emitted.

## Final result
Frozen651aa1a5ef7fbff3866f920216baa975f8ffea54 extracted independently with git archive. Corrected independent suite93 passed, no skips (12 diagnostics + prior81). Source app/tests before/after manifests identical. Exact parser/API module provenance and SHA256 captured.

Baseline frozen94 same12 diagnostic cases fail solely for absent diagnostic fields/attributes. The eight HTTP fixtures first assert original strict import422 detail and no diagnostic, including high-denominator native time, before requesting the new diagnostic. This confirms preserved refusal on both baseline and fixed source.

Test correction: first final-source run showed8 failures because reviewer expected a minimal full HTTP body, while the existing global error handler returns an enhanced envelope plus request_id. Stable detail/code/status were already correct. Reviewer corrected the expectation to exact legacy detail and no diagnostic anywhere; did not change production. Both first and corrected logs retained. Seven warnings are existing field-name shadowing and unregistered marker warnings from running external tests with original conftest loaded as a plugin; not skips.

Final review: no outstanding findings. Auxiliary classifier errors are narrowly caught and yield NOT_EVALUATED, preserving the primary mismatch. The implementation does not make an unsafe file importable or continue validating after the first conflict.
