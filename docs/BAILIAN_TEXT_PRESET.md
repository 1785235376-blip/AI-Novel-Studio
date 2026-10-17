# Alibaba Model Studio text preset

Status: host-configured typed text-runtime integration. Live provider calls, model quality, billing, settings UI and packaged Windows acceptance are NOT_RUN. No actual key, paid call or account modification was used for development.

## Configuration boundary

The original Runtime registers this preset only when the host explicitly supplies ALIYUN_BAILIAN_MODEL. There is no default model, automatic discovery, cloud enablement or replacement of the local route. ALIYUN_BAILIAN_REGION selects one of cn-beijing (default), ap-southeast-1, us-east-1 or cn-hongkong. Unknown regions and arbitrary URLs are refused.

Credentials remain with the existing aliyun-bailian vault entry. The existing transport can use DASHSCOPE_API_KEY only in development; packaged mode does not use that environment fallback. This change does not create, enter, save, transmit or test a real credential. Existing cloud authorization, cost, context-sharing and route-admission owners still apply.

This preset uses the existing typed GenerationRuntime/ProviderRegistry and OpenAI-compatible text transport. It does not add the provider to the old legacy ModelRouter, or promise that every surface supports every cloud route. It does not register image, audio, vision, tool execution or arbitrary plugin capabilities.

## Protocol scope

The four fixed shared regional endpoints follow the [official Base URL reference](https://www.alibabacloud.com/help/en/model-studio/base-url), checked 2026-10-17. Keys and endpoint regions must match. Workspace-dedicated domains are recommended by the provider for production but are not configurable through this bounded preset yet. Coding Plan and Token Plan endpoints are excluded; the official reference limits them to interactive coding tools rather than backend services.

The preset requests ordinary text output with enable_thinking=false, following the provider's [hybrid-thinking parameter documentation](https://www.alibabacloud.com/help/en/model-studio/deep-thinking). Thinking-only models and model-specific protocols are not covered. The host must choose a compatible model ID; a model ID is not a quality, availability or cost guarantee.

## Focused development checks

bailian-text-preset-focused-r2: 12 new tests plus 11 original native-provider cases passed. Coverage includes fixed regional paths, synthetic chat/SSE payloads and usage, header-only synthetic keys, rejected nonpreset URLs, no network on explicit registration, original cloud-disabled refusal, and packaged environment-key refusal.

r1 retained: the new test initially attempted to mutate frozen Settings; the test now uses a replaced immutable settings instance in its own module scope. Product settings, original tests and original guard behavior were not weakened. Full inventory/build/provider acceptance remains deferred under the user's feature-first cadence.
