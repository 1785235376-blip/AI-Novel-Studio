# Alibaba Bailian text preset in the original Model Center

The existing host-selected Bailian text adapter and region mapping are reused, not reimplemented. A new read-only constant catalog at GET /api/model-center/provider-presets/bailian-text (also /api/v1) exposes only preset region endpoints, non-secret host-variable names and explicit non-execution flags. It reads no host environment, vault value/state, current model configuration or inventory; it performs no probe, registration or provider request. In collaboration mode the exact GET retains the trusted-session gate; unknown suffixes and POST are not admitted. Packaged mode still requires its original bootstrap-issued session, never a development token fallback.

The original Model Center panel adds an explicit preset-read entry. It prepares a selectable region/model-ID host configuration hint in a read-only text area. It does not apply configuration, save settings, accept keys, register or validate a model, select cloud over local, buy a plan, or call an API provider. Region changes are local UI only. Invalid project context disables the entry. Captured scope/client/identity retirement aborts and discards late responses. The closed decoder rejects unexpected fields, URLs and region pairings. Model identifiers reject whitespace, quotes, control characters and shell punctuation; displayed text is not executed.

The narrow adapter remains standard shared DashScope pay-as-you-go text with non-thinking request mode. A typed model ID is not a guarantee that the user's account/model supports it. Credentials, actual host setup, original cloud/data/cost consent and real model acceptance remain separate existing owners. No new credential path or execution authority is introduced.

The four shared regional endpoints were rechecked against [Alibaba's official Base URL overview](https://www.alibabacloud.com/help/en/model-studio/base-url) on 2026-10-18. That page also describes workspace-dedicated endpoints and recommends them for production; those are not configured by this narrow existing shared-domain preset. Coding/Token Plan endpoints are intentionally excluded because this is a backend Studio service. No agreement, billing or account changes were made.

Evidence:
- bailian-preset-catalog-r1: 14 targeted catalog/router plus existing synthetic adapter/host-registration tests PASS, no paid provider call.
- bailian-preset-panel-r2: 32 focused new/original Model Center component tests and TypeScript PASS.
- panel-r1 reported 31 assertions passing but an unhandled exception, so its result is FAIL and retained. The new mounted test supplied an incomplete injected catalog; the fixture was replaced with the original decoder's valid empty catalog. The runtime validator and original tests were not weakened.
- bailian-preset-application-r1: 4 cases PASS including actual app /api and /api/v1 collaboration-session gates, method/path rejection and packaged rejection of a development token. This is in-process actual middleware, not desktop/browser acceptance.
- No real provider/model quality, remote billing, Windows/GPU, browser screenshot, full suite/build or global V2 completion claim.
