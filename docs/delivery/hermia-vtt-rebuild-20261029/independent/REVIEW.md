# Independent NEW VTT literal review

This is new evidence, not recovery of the lost earlier VTT package. No production edits by this reviewer.

## Fixed source
- Baseline: faede394ee2891d69851022f000ae4b66276de62.
- Fixed: f007fb4ea5096c3904e02f1f521600defa1f83ce.
- Separate git archives, actual test cwd each archive, installed OTIO 0.18.1 venv.
- Baseline exact same 13 tests: 9 failed, 4 passed, exit 1.
- Fixed: 13 passed, exit 0.
- Fixed 601 app Python file hashes identical before/after. Baseline 601 app Python files checked byte-for-byte against git baseline after test.

## Tests
Four authored text samples decoded by external installed FFmpeg: three entity-bearing cases failed before fix; Chinese/emoji/raw amp control passed. Three single-pass six-reference cases failed before fix. Encoded markup must be rejected by original owner normalizer; raw markup remains rejected. SRT exact bytes unchanged. Unknown/numeric/HTML references stay unchanged as the selected bounded importer subset, not a full-spec claim. Both actual HTTP prefixes import literal entity spellings, validate preview readonly, commit, replay without write, export to external decoder, and restore historical version.

## Scope
Current WebVTT draft supports a broader HTML reference set. This implementation intentionally covers six supported named references and safe authored-literal export, not full external VTT entity import conformance. No real browser/NLE, Windows, PG, GPU or full product claim. No install, upload or source change here.

## Excluded exploratory runs
The initial run from the mutable worktree cwd is not used as evidence. The first immutable archive omitted local_interop_desktop and failed collection; that startup failure is not counted as a production defect. baseline-final.log/xml is the valid clean control. fixed.log/xml is the fixed terminal run.

A post-test provenance probe initially used system Python and could not import sqlalchemy. The pytest command itself had printed EXIT:0 and completed13passed. Provenance was rerun with the exact installed test interpreter and passed (provenance.log); this diagnostic setup error is not a test or product failure.
