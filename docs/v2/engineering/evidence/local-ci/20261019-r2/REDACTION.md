# Evidence redaction note

Run `20261019-r2` (Git HEAD `7e1ea003c975f585a26201e007f8e4a7872c7ee2`).
Absolute host paths were replaced with XML-safe, markdown-safe placeholders before commit:

- repository worktree path -> `[repo]`
- workspace root -> `[workspace]`
- user profile path -> `[userprofile]`

The redactor re-parsed every XML file after rewriting; `xml_valid=True`.
Unredacted originals remain outside the source tree under `Engineering-Runs/local-ci-round2-20261019/`.
Redaction only rewrites path text; results, counts, timings and assertions are unchanged.

| file | SHA256 before (prefix) | SHA256 committed (prefix) |
| --- | --- | --- |
| LOCAL-01-backend.log | 2a53865e893423fb | 54a81c39d189e9e2 |
| LOCAL-02-junit.xml | 360da5ab55c0ba43 | d5db9a070f1c09bf |
| LOCAL-02-pytest.log | 2dc0cf246d5f0085 | 957edcd4bfecc1f4 |
| LOCAL-03-build.log | e021cff081102f52 | 403b53545ac2dbd1 |
| LOCAL-03-design-tokens.log | deabdbd287235201 | 674e9dac6bc3536b |
| LOCAL-03-vitest.log | a1fcfa9875bfd066 | add1764e9c4b45f4 |
| LOCAL_CI_RESULTS.json | c73ec85821251367 | 1309ea7a8c88a457 |
| results.json | daeee4e27d8e5007 | db1f25d518d13fa6 |
