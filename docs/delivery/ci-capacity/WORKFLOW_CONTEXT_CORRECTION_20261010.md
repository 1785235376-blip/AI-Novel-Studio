# Correct backend cache initialization context

## Confirmed defect and preserved failure

The initial cache implementation put `${{ runner.temp }}` under job-level
`env` twice. This is invalid GitHub Actions syntax: `runner` is available in
step contexts, but not `jobs.<job_id>.env`. This defect was introduced by B's
cache change. The earlier 320 passing infrastructure tests did not validate
Actions expression-context legality and were not workflow-loader evidence.

[Official context availability](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#context-availability)
confirms the restriction. The actual published source
`c491d1b0227a877eaa5bad7651ed22ba67463439` produced
[run 38078421006](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38078421006):
failure at 19:05:39 UTC, zero jobs returned, no Cloud test execution. This
failure remains recorded in `initial-workflow-loader-failure.json` and is not
relabeled after correction. Other workflows continued naturally; none was
cancelled or rerun by B.

The connector did not permit the check-suite annotation endpoint. Its exact
server annotation was not read, and no alternate route was attempted after
that rejection. The invalid expression itself was independently reproduced
with the actual published workflow and a real Actions-specific validator.

## Minimal correction

Only the two newly introduced cache initializations change. Each now has a
shell step before setup-python which expands the runner-provided
`RUNNER_TEMP` and writes the fixed pip cache path to `GITHUB_ENV` for subsequent
steps and action post-processing. The path continues to survive the existing
HOME/XDG isolation steps. No runner expression is evaluated at job level.

The installed environment is never restored, and installation, `pip check`,
dependency freeze, original suite commands, hashes, shard assignments, caps,
join dependencies and all old assertions remain unchanged. A still owns the
explicit final V2 manifest regeneration and publication.

## Verification

The official [actionlint 1.7.12 release](https://github.com/rhysd/actionlint/releases/tag/v1.7.12)
was downloaded into B's isolated runtime. Its Linux archive SHA256 was checked
against the GitHub release asset digest before execution:
`8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8`.

- Original c491d1b workflow: **actionlint exit 1**, exactly two expression
  errors at **33:26** and **179:26**, both rejecting the unavailable context.
- Corrected complete Cloud workflow: **actionlint exit 0**, no diagnostics.
  Default checks were used; none was disabled or ignored.
- Focused infrastructure: **113 passed**, including eight cache regressions.
- Full infrastructure: **324 passed**. Existing frozen gate/job/command hash
  tests are unchanged and pass.
- The new regressions execute the real initialization shell with a spaced
  runner path, load its emitted environment value into a later pip process,
  verify the stable cache location, and reject runner context at job level.
- `git diff --check`: passed. Frozen V1 manifest hash is unchanged.

Original actionlint output, empty successful output, validator/input digests
and original pytest receipts accompany this report. These local results fix
the known parse defect; GitHub acceptance and actual cache behavior on the
next integrated source remain pending until observed.

Before publishing future workflow changes, run an Actions-aware validator on
the exact final workflow, in addition to shell and infrastructure tests:

    actionlint -oneline .github/workflows/cloud-ci.yml

Do not treat ordinary YAML parsing, string assertions or pytest success as a
replacement for expression-context validation or actual hosted execution.
