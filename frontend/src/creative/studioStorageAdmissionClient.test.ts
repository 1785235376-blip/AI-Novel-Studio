import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { studioClient, type StudioStorage, type StudioStorageAdmission } from './studioClient';

const projectId = 'storage-project';
const client = () => studioClient(projectId, { sessionToken: '', localHostToken: '' });
const storage = (): StudioStorage => ({ assets: { count: 1, bytes: 42 }, trash: { count: 0, bytes: 0 }, limits: { asset_bytes: 25 * 1024 * 1024, project_asset_bytes: 512 * 1024 * 1024, project_assets: 1000 }, model_storage: 'EXTERNAL_READ_ONLY', cache_storage: 'SEPARATE_OWNER', export_storage: 'CLIENT_SELECTED_DOWNLOAD', physical_cleanup_available: false });
const admission = (): StudioStorageAdmission => ({ state: 'READY', available_import_bytes: 1024, reserve_bytes: 64 * 1024 * 1024, measurement: 'CURRENT_ORIGINAL_ASSET_FILESYSTEM_AND_PROJECT_QUOTA', paths: { project: 'EXISTING_PROJECT_OWNER', assets: 'EXISTING_ASSET_LIBRARY', models: 'MODEL_CENTER_REFERENCES_ONLY', cache: 'EXISTING_CACHE_OWNER', exports: 'USER_SELECTED_DOWNLOAD' }, external_model_scan: false, automatic_cleanup: false, automatic_migration: false });
const importBody = { filename: 'image.png', kind: 'image' as const, content_base64: 'YWJj', idempotency_key: 'stable-storage-retry' };
const reply = (value: unknown, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => value });
let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => { fetchMock = vi.fn(); vi.stubGlobal('fetch', fetchMock); });
afterEach(() => { vi.unstubAllGlobals(); });

describe('studio safe storage admission errors', () => {
  it.each(['CREATIVE_STORAGE_LOW_SPACE', 'CREATIVE_STORAGE_UNAVAILABLE'])('maps HTTP 507 %s without leaking server paths or operational details', async code => {
    fetchMock.mockResolvedValue(reply({ code, message: 'private storage /home/person/secret-project', details: { path: '/mnt/private-disk', provider: 'private-provider', token: 'private-token' } }, 507));
    const failure = await client().importAsset(importBody).catch(error => error);
    expect(failure).toBeInstanceOf(ApiError);
    expect(failure.status).toBe(507);
    expect(failure.problem.code).toBe(code);
    expect(failure.message).toBe(code === 'CREATIVE_STORAGE_LOW_SPACE'
      ? '资产所在磁盘的可用空间不足。请释放空间后重试导入。'
      : '暂时无法确认资产存储的可用空间。请检查存储位置是否可访问后重试。');
    expect(JSON.stringify(failure.problem)).not.toMatch(/private|\/home\/|\/mnt\/|token|provider/);
    expect(failure.problem).not.toHaveProperty('details');
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it('recognizes the nested error code without displaying nested response content', async () => {
    fetchMock.mockResolvedValue(reply({ detail: { code: 'CREATIVE_STORAGE_UNAVAILABLE', message: 'OSError at C:\\Private\\Assets', path: 'C:\\Private\\Assets' } }, 507));
    const failure = await client().storage().catch(error => error);
    expect(failure.message).toBe('暂时无法确认资产存储的可用空间。请检查存储位置是否可访问后重试。');
    expect(JSON.stringify(failure.problem)).not.toMatch(/Private|OSError|Assets|path/);
  });

  it('does not infer low disk space from unrelated status or an unrecognized 507 response', async () => {
    fetchMock.mockResolvedValueOnce(reply({ code: 'CREATIVE_STORAGE_LOW_SPACE' }, 403))
      .mockResolvedValueOnce(reply({ code: 'UNKNOWN_STORAGE_CONDITION', message: 'private-volume' }, 507));
    const denied = await client().importAsset(importBody).catch(error => error);
    expect(denied.message).toBe('当前会话无权访问此内容。请重新核对身份和分支。');
    const unknown = await client().importAsset(importBody).catch(error => error);
    expect(unknown.message).toBe('请求未完成。请核对输入与连接状态。');
    expect(unknown.message).not.toContain('private-volume');
  });

  it('keeps a stable upload key available for an explicit retry without automatically retrying or cleaning storage', async () => {
    fetchMock.mockResolvedValue(reply({ code: 'CREATIVE_STORAGE_LOW_SPACE' }, 507));
    const captured = client();
    await expect(captured.importAsset(importBody)).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledOnce();
    await expect(captured.importAsset(importBody)).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    for (const [url, init] of fetchMock.mock.calls) {
      expect(url).toBe(`/api/projects/${projectId}/studio/assets`);
      expect(init.method).toBe('POST');
      expect(init.headers['Idempotency-Key']).toBe(importBody.idempotency_key);
      expect(JSON.parse(init.body)).toEqual(importBody);
    }
  });
});

describe('backward-compatible studio storage projections', () => {
  it('preserves the earlier storage shape when admission is absent without inventing readiness', async () => {
    fetchMock.mockResolvedValue(reply(storage()));
    const signal = new AbortController().signal;
    const value = await client().storage(signal);
    expect(value).toEqual(storage());
    expect(value).not.toHaveProperty('admission');
    expect(fetchMock.mock.calls[0][0]).toBe(`/api/projects/${projectId}/studio/storage`);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'GET', signal });
    expect(fetchMock.mock.calls[0][1].headers).not.toHaveProperty('Idempotency-Key');
  });

  it('returns the current admitted bytes and symbolic owners without implying external scans or cleanup', async () => {
    const value: StudioStorage = { ...storage(), admission: admission() };
    fetchMock.mockResolvedValue(reply(value));
    expect(await client().storage()).toEqual(value);
    expect(value.admission?.paths).toEqual({ project: 'EXISTING_PROJECT_OWNER', assets: 'EXISTING_ASSET_LIBRARY', models: 'MODEL_CENTER_REFERENCES_ONLY', cache: 'EXISTING_CACHE_OWNER', exports: 'USER_SELECTED_DOWNLOAD' });
    expect(value.admission?.automatic_cleanup).toBe(false);
    expect(value.admission?.automatic_migration).toBe(false);
    expect(value.admission?.external_model_scan).toBe(false);
  });

  it('distinguishes zero capacity from an unavailable measurement', async () => {
    const low: StudioStorage = { ...storage(), admission: { ...admission(), state: 'LOW_SPACE_OR_QUOTA', available_import_bytes: 0 } };
    const unavailable: StudioStorage = { ...storage(), admission: { ...admission(), state: 'UNAVAILABLE', available_import_bytes: null } };
    fetchMock.mockResolvedValueOnce(reply(low)).mockResolvedValueOnce(reply(unavailable));
    expect((await client().storage()).admission).toMatchObject({ state: 'LOW_SPACE_OR_QUOTA', available_import_bytes: 0 });
    expect((await client().storage()).admission).toMatchObject({ state: 'UNAVAILABLE', available_import_bytes: null });
  });

  it('returns only public admission fields while preserving existing counts and limits', async () => {
    const expected = { ...storage(), admission: admission() };
    fetchMock.mockResolvedValue(reply({ ...expected, admission: { ...admission(), raw_path: '/private/project', reason: 'private-system-message', paths: { ...admission().paths, actual_directory: '/private/asset-library' } } }));
    const result = await client().storage();
    expect(result).toEqual(expected);
    expect(result.assets).toEqual(storage().assets);
    expect(result.limits).toEqual(storage().limits);
    expect(JSON.stringify(result.admission)).not.toMatch(/private|raw_path|actual_directory/);
  });

  it.each([null, [], 'private-path', { state: 'UNKNOWN' }, { state: '/private/project' },
    { available_import_bytes: '/private/disk' }, { available_import_bytes: '123' }, { available_import_bytes: true },
    { available_import_bytes: -1 }, { available_import_bytes: 1.5 }, { available_import_bytes: NaN },
    { available_import_bytes: Infinity }, { available_import_bytes: Number.MAX_SAFE_INTEGER + 1 },
    { reserve_bytes: '/private/reserve' }, { reserve_bytes: -1 }, { reserve_bytes: 0.5 },
    { reserve_bytes: Infinity }, { reserve_bytes: Number.MAX_SAFE_INTEGER + 1 },
    { state: 'READY', available_import_bytes: null }, { state: 'LOW_SPACE_OR_QUOTA', available_import_bytes: null },
    { state: 'UNAVAILABLE', available_import_bytes: 0 },
    { external_model_scan: true }, { automatic_cleanup: true }, { automatic_migration: true },
    { external_model_scan: undefined }, { automatic_cleanup: 'false' }, { automatic_migration: 0 },
    { measurement: '/private/filesystem' }, { paths: null }, { paths: [] },
  ].map(change => [change] as const))('rejects invalid admission data without reflecting it: %j', async change => {
    const value = change && typeof change === 'object' && !Array.isArray(change) ? { ...admission(), ...change } : change;
    fetchMock.mockResolvedValue(reply({ ...storage(), admission: value }));
    const failure = await client().storage().catch(error => error);
    expect(failure).toBeInstanceOf(ApiError);
    expect(failure.problem).toEqual({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '服务返回的存储信息不可用，请重新读取。' });
    expect(JSON.stringify(failure.problem)).not.toContain('private');
  });

  it.each(['project', 'assets', 'models', 'cache', 'exports'])('rejects an unexpected %s owner label or raw path', async key => {
    fetchMock.mockResolvedValue(reply({ ...storage(), admission: { ...admission(), paths: { ...admission().paths, [key]: '/private/storage' } } }));
    await expect(client().storage()).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_INVALID' } });
  });
});
