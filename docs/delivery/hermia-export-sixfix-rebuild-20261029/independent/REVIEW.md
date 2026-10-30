# Independent NEW remaining export fixes review

This is newly executed verification, not recovery or reuse of missing original evidence. No production edits or external writes were performed by this reviewer.

- Exact baseline: bb427114f0573d2532e1900b96155efc47b58fe3, immutable `git archive`.
- Exact fixed commit: c3a5cc6e3450a331733c92c06dd5eedbfd5b317a, tree b3ec647fbeee27cac30b2058a0b54e01975693c2, separate immutable `git archive`.
- Interpreter: existing `studio-overnight/.venv/bin/python`; no packages installed. XDG_DATA_HOME and NOVEL_DATA_PATH point to separate synthetic /tmp roots.
- Same final 24 cases: baseline **15 failed / 9 passed**, exit 1; fixed **24 passed**, exit 0. Fixed 601 Python application files have identical before/after SHA256 manifests.

## Coverage and findings

Four actual DOCX/EPUB ZIP XML parsing cases reject the original illegal U+FFFE/U+FFFF output while preserving Chinese, emoji, markup-escaped prose and XML-legal higher-plane U+1FFFE. Every XML/rels/opf/xhtml part is parsed independently with ElementTree.

Seven actual service queue/download cases exercise payload sizes 1 through 7 bytes at exact decoded caps. All three representations (raw bytes, named content_base64, legacy content+base64 encoding) must succeed with identical bytes. Original legacy representation fails even while equivalent raw/named succeed.

Service idempotency tests prove changed-format rejection does not write or recapture, concurrent conflicting requests produce one queue row and one explicit error, canonical aliases retain snapshot identity, different novel/actor scopes remain independent, and expired keys remain reusable. Actual mounted FastAPI routers at both /api and /api/v1 return HTTP 400 with EXPORT_IDEMPOTENCY_FORMAT_CONFLICT; normalized aliases still return 202 with the original ID.

Four guard controls verify existing predecode admission and actual decoded over-limit rejection. These pass in the baseline and are not new defect claims. Failed cases are not distinct bug counts. Concurrent baseline returned the same row twice, not duplicate execution.

## Evidence

Use baseline-final24.log/xml/exit and fixed-final24.log/xml/exit with the included exact final test file. Earlier baseline.log and baseline-final.log were exploratory smaller suites (18 and 22 cases); they are not the final comparison and not additive. One interim exception-class assertion was corrected before the final 24-case comparison, because _result_bytes raises ExportJobResultInvalid (RuntimeError), not ValueError. This was a test expectation issue, not a production defect.

A Starlette testclient deprecation warning was present; no new dependency was installed to silence it. No Windows, PostgreSQL, browser/Office-reader, external model, or full Studio claim is made. Source diff is confined to app/export_formats.py and app/services/export_job_service.py; industry exporters are untouched. No issue found requiring another production edit.
