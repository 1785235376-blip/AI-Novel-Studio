# Evidence redaction note

This directory retains the local minimum CI evidence for run `20261019-final`
(Git HEAD `d73423c79a4c0a5fe5c8bf9e696c5ae91565197a`).

The committed copies had absolute host paths replaced before commit:

- repository worktree path -> `<repo>`
- workspace root -> `<workspace>`
- user profile path -> `%USERPROFILE%`
- interpreter path -> `python`

Redaction only rewrites path text; test results, counts, timings and assertions are unchanged.
The unredacted originals stay outside the source tree on the run host under
`Engineering-Runs/local-ci-20261019/evidence-20261019-final-venv`.

| file | SHA256 before redaction (prefix) | SHA256 committed (prefix) |
| --- | --- | --- |
| LOCAL-01-backend.log | c5627586a1ea6ad6 | 039417edcceea618 |
| LOCAL-02-junit.xml | 81acfba51d46ed78 | 9eeb2dc90d6bfb57 |
| LOCAL-02-pytest.log | 4b62662d7100c526 | 41d45998fcd3e6a7 |
| LOCAL-03-build.log | c06e39b4495c1ab6 | 8ee4a35264b25d04 |
| LOCAL-03-design-tokens.log | deabdbd287235201 | 4799b455bb823700 |
| LOCAL-03-vitest.log | 4702e7b956dc05b8 | 142d9592c5787527 |
| LOCAL_CI_RESULTS.json | 929fe1c0de531ce1 | 3a5e45c236699607 |
| results.json | 9fb7767594bfcbd4 | 9ab113fb3deaaff6 |
