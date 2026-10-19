import { describe, expect, it } from 'vitest';
import { ApiError } from '../api';
import wire from './bailianPresetWire.testFixture.json';
import { bailianHostPreview, bailianPresetReadProblem, checkBailianConfiguration, checkedBailianPresets } from './bailianPresetContract';

describe('local-only Bailian configuration preflight', () => {
  it('uses each original regional endpoint and never infers model availability', () => {
    const catalog = checkedBailianPresets(wire); const before = structuredClone(catalog);
    for (const region of catalog.regions) {
      expect(checkBailianConfiguration(catalog, region.id, 'synthetic-model')).toEqual({ valid: true,
        code: 'FORMAT_VALID', message: '本地格式预检通过（未连接）', base_url: region.base_url });
      expect(bailianHostPreview(catalog, region.id, 'synthetic-model')).toContain(`ALIYUN_BAILIAN_REGION=${region.id}`);
    }
    expect(catalog).toEqual(before);
  });
  it.each(['', 'unknown-region'])('requires a supported region: %j', region => {
    expect(checkBailianConfiguration(checkedBailianPresets(wire), region, 'synthetic').code).toBe('REGION_REQUIRED');
  });
  it.each(['bad model', 'line\nOTHER=value', '$(run)', 'x;run', 'x"quoted', '-prefix', 'x'.repeat(201), null, {}])('refuses malformed model %j without preparing host text', model => {
    const catalog = checkedBailianPresets(wire);
    expect(checkBailianConfiguration(catalog, 'cn-beijing', model as string).valid).toBe(false);
    expect(bailianHostPreview(catalog, 'cn-beijing', model as string)).toBeUndefined();
  });
  it('keeps endpoint and response-field fences, even before a local check', () => {
    for (const base_url of ['http://dashscope.aliyuncs.com/compatible-mode/v1', 'https://untrusted.invalid/v1', 'https://coding-intl.dashscope.aliyuncs.com/v1', 'https://user:synthetic@dashscope.aliyuncs.com/compatible-mode/v1']) {
      const bad = structuredClone(wire); bad.regions[0].base_url = base_url;
      expect(() => checkBailianConfiguration(bad as never, 'cn-beijing', 'synthetic')).toThrow();
    }
    expect(() => checkBailianConfiguration({ ...wire, api_key: 'SYNTHETIC_ONLY' } as never, 'cn-beijing', 'synthetic')).toThrow();
  });
});

it.each(['STUDIO_RESPONSE_INVALID', 'MODEL_CENTER_SECRET_VALUE_REJECTED'])('maps controlled response failure %s without echoing payload', code => {
  const problem = bailianPresetReadProblem(new ApiError({ status: 200, code, message: 'SYNTHETIC_PRIVATE_BODY', details: { private: 'SYNTHETIC_ONLY' } }));
  expect(problem.code).toBe('PRESET_RESPONSE_INVALID');
  expect(JSON.stringify(problem)).not.toMatch(/SYNTHETIC_PRIVATE_BODY|SYNTHETIC_ONLY/);
});
it('maps only controlled context codes and host status; unknown exception text stays private', () => {
  expect(bailianPresetReadProblem(new ApiError({ status: 403, code: 'MODEL_CENTER_CATALOG_SCOPE_MISMATCH', message: 'hidden' })).code).toBe('PRESET_CONTEXT_CHANGED');
  expect(bailianPresetReadProblem(new ApiError({ status: 418, code: 'SYNTHETIC_UNKNOWN', message: 'SYNTHETIC_PRIVATE' })).code).toBe('PRESET_READ_INCOMPLETE');
  expect(bailianPresetReadProblem({ status: 401, message: 'SYNTHETIC_PRIVATE' }).code).toBe('PRESET_READ_INCOMPLETE');
});
