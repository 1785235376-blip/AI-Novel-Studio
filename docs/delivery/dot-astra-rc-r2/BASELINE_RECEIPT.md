# R2 baseline receipt

Verified 2026-10-05 UTC through GitHub connector and a fresh Git clone.

- Repository: https://github.com/1785235376-blip/AI-Novel-Studio
- Main: `fed2404c8e30b44061b7139dced45b7f3301601c`
- Inherited Draft PR: [#36](https://github.com/1785235376-blip/AI-Novel-Studio/pull/36)
- Starting SHA: `f8c141c39a543cc9dbea57647ac91185bc9aecd6`
- Working branch: `work/dot-astra-v1-rc-r2`
- `git merge-base --is-ancestor origin/main origin/cloud/continuation-20261003`: exit 0. No new remote work was discarded.
- PR #26 remains a separate, unmerged Windows AppContainer prototype. Third-party plugin execution must remain disabled without target-platform evidence.
- Actual primary development/audit model: `gpt-6-astra`, selected through the platform model selector, including area workers. This is a development-model record, not a product provider configuration.
- Execution: isolated Linux cloud filesystem, Python 3.12.14 and Node 24.19.0. Frontend package manager pinned to existing CI version pnpm 10.6.5; CI retains Python 3.12.9 and Node 22.14.0. No user desktop, GPU, credentials or user data are used.
- Open issues inspected: #14 clean regression, #15 Windows DH evidence, #16 PostgreSQL recovery, #17 industry export/font, #18 Provider/credentials, #20 frontend toolchain. No issues closed.
- Status: ENGINEERING_IN_PROGRESS. No merge, release or deployment. Final verification has not yet run.
