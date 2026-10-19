# Evidence redaction note

This directory retains the local minimum CI evidence for run `20261019-final`
(Git HEAD `6afae9cae82430f09c547257528adccdf945dc0c`).

The committed copies had absolute host paths replaced before commit:

- repository worktree path -> `<repo>`
- workspace root -> `<workspace>`
- user profile path -> `%USERPROFILE%`
- interpreter path -> `python`

Redaction only rewrites path text; results, counts, timings and assertions are unchanged.
The unredacted originals stay outside the source tree on the run host under
`Engineering-Runs/local-ci-20261019/`.

| file | SHA256 before redaction (prefix) | SHA256 committed (prefix) |
| --- | --- | --- |
| LOCAL-01-backend.log | 655ef9e426cec468 | 323bf3831c4a4a15 |
| LOCAL-02-junit.xml | 7d8a2e8d65e20bb6 | 937df0bfd736ced0 |
| LOCAL-02-pytest.log | daad53c8aee1fd14 | 048448a048a0ab41 |
| LOCAL-03-build.log | b08a89aaedf868d7 | f005febf7c06d1cc |
| LOCAL-03-design-tokens.log | deabdbd287235201 | 4799b455bb823700 |
| LOCAL-03-vitest.log | 7d0d9d8de92c99cd | be82ad95cdb2147a |
| LOCAL_CI_RESULTS.json | 2c0fe003d2c389c1 | 3c325d4341af32be |
| results.json | bb4f211fc959d3eb | 4e7be4453809146f |
