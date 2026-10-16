# Post-V1 R3 verification boundaries

This directory records evidence for the new branch, not PR #37 acceptance.

- Baseline: `1ad947e458a1ebb4b0f74e06b4e0e3fb3322bab0`.
- New branch: `work/post-v1-feature-forward-r3`.
- New stacked Draft PR: [#38](https://github.com/1785235376-blip/AI-Novel-Studio/pull/38).
- Actual implementation and independent review used the requested Astra model.
- No merge, release, deployment, paid API or executable plugin runtime was authorized or performed.

Local Linux unit/API tests exercise synthetic File fixtures. Real PostgreSQL parity is executed in the hosted PostgreSQL lane with migration 019 and a no-silent-skip gate. Locally authored browser tests are not browser PASS evidence: local Chromium could not launch because its process-singleton socket was denied by the environment, including the permitted escalated attempt. The added hosted Chromium step must execute those journeys before they are reported passed.

The inherited Windows Host/package lanes continue to run against R3 to detect regressions. Their new artifacts are **R3 engineering artifacts**, never replacements for the frozen PR #37 V1 acceptance package. Interactive Windows, GPU/model runtime, literary/image/voice quality, installer/upgrade/uninstall and production acceptance remain NOT_RUN.

Status terms are separate: IMPLEMENTED describes a concrete service/route/UI; CONTRACT_VERIFIED describes tested interfaces and deterministic mechanics; MOCK_ONLY describes intentionally synthetic generation; REAL_VERIFIED applies only to the specific real engine/storage/browser operation actually executed. None implies real-model quality.
