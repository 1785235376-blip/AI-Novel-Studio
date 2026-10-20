import { afterEach, expect, it, vi } from 'vitest';
import { enabled, experimentalFeatures } from './api';
afterEach(() => vi.unstubAllGlobals());
const respond = (value: unknown) => vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(value), { status: 200 })));

it('current clients use the complete explicit runtime map including disabled new surfaces', async () => {
  respond({ schema_version: 2, experimental: true, default_enabled: false,
    features: { 'experimental.workspace_tools_v2': true },
    surface_features: { 'experimental.workspace_interaction_v1': true },
    runtime_features: { 'experimental.workspace_tools_v2': true, 'experimental.workspace_interaction_v1': true, 'experimental.branch_manuscript_v1': false } });
  const result = await experimentalFeatures();
  expect(enabled(result, 'workspace_interaction_v1')).toBe(true);
  expect(enabled(result, 'branch_manuscript_v1')).toBe(false);
  expect(Object.keys(result.features)).toHaveLength(3);
});

it('complete runtime map is authoritative over incompatible convenience maps', async () => {
  respond({ features: { 'experimental.branch_manuscript_v1': true }, surface_features: { 'experimental.branch_manuscript_v1': true }, runtime_features: { 'experimental.branch_manuscript_v1': false } });
  expect(enabled(await experimentalFeatures(), 'branch_manuscript_v1')).toBe(false);
});

it('older servers remain compatible without inventing new capability grants', async () => {
  respond({ experimental: true, default_enabled: false, features: { 'experimental.workspace_tools_v2': true } });
  const result = await experimentalFeatures();
  expect(enabled(result, 'workspace_tools_v2')).toBe(true);
  expect(enabled(result, 'workspace_interaction_v1')).toBe(false);
});

it('an explicit empty runtime inventory never falls back to legacy grants', async () => {
  respond({ features: { 'experimental.workspace_tools_v2': true }, runtime_features: {} });
  expect(enabled(await experimentalFeatures(), 'workspace_tools_v2')).toBe(false);
});
