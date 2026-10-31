import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { createAssetBrowserClient, ASSET_BROWSER_CLIENT_FACTS } from './assetBrowserClient';
import { ASSET_BROWSER_ERROR_CODES } from './assetBrowserTypes';
import { FIXTURE_PROJECT, assetRow, listEnvelope, relationshipGraph } from './assetBrowserFixtures';

/** 记录到的：每个 `json` / `blob` 调用的第一个参数（URL）。 */
type Recorder = { transport: StudioGraphTransport; jsonCalls: [string, (string | undefined)?][]; blobCalls: string[] };

/**
 * 假传输：与 `studioGraphClient.ts::StudioGraphTransport` 同一个形状。
 * 只记录 URL 并返回固定载荷，因此测试能断言"到底请求了哪个 owner 端点"。
 */
function fakeTransport(payload: unknown | (() => unknown), blobValue?: Blob): Recorder {
  const jsonCalls: [string, (string | undefined)?][] = [];
  const blobCalls: string[] = [];
  const resolve = () => typeof payload === 'function' ? (payload as () => unknown)() : payload;
  const json = (url: string, method?: string) => { jsonCalls.push([url, method]); return Promise.resolve(resolve()); };
  const blob = blobValue
    ? (url: string) => { blobCalls.push(url); return Promise.resolve(blobValue); }
    : undefined;
  const transport: StudioGraphTransport = {
    // 保留传输的泛型形状（`json<T>`），与 `studioGraphClient.ts` 完全一致。
    json: <T,>(url: string, method?: string): Promise<T> => json(url, method) as Promise<T>,
    ...(blob ? { blob } : {}),
  };
  return { transport, jsonCalls, blobCalls };
}
const client = (payload: unknown | (() => unknown), blobValue?: Blob) => {
  const fake = fakeTransport(payload, blobValue);
  return { ...fake, client: createAssetBrowserClient(FIXTURE_PROJECT, fake.transport) };
};
const url = (recorder: Recorder) => recorder.jsonCalls[0]?.[0];
const method = (recorder: Recorder) => recorder.jsonCalls[0]?.[1];
function codeOf(reason: unknown): string | undefined {
  return reason instanceof ApiError ? reason.problem.code : `NOT_API_ERROR:${String(reason)}`;
}
async function failure(run: () => Promise<unknown>): Promise<ApiError> {
  try {
    await run();
  } catch (reason) {
    if (reason instanceof ApiError) return reason;
    throw reason;
  }
  throw new Error('expected the read to fail');
}

describe('asset browser client', () => {
  it('reads the existing owner list endpoint and decodes it strictly', async () => {
    const subject = client(listEnvelope([assetRow()]));
    const items = await subject.client.listAssets();
    expect(subject.jsonCalls).toHaveLength(1);
    expect(url(subject)).toBe(`/api/projects/${FIXTURE_PROJECT}/studio/assets`);
    expect(method(subject)).toBe('GET');
    expect(items).toHaveLength(1);
    expect(items[0].id).toBe('asset-a');
  });

  it('reads one asset and the relationship projection from the same owner base', async () => {
    let call = 0;
    const subject = client(() => (call++ === 0 ? assetRow() : relationshipGraph()));
    await subject.client.readAsset('asset-a');
    expect(subject.jsonCalls[0]?.[0]).toBe(`/api/projects/${FIXTURE_PROJECT}/studio/assets/asset-a`);
    const decoded = await subject.client.readRelationships();
    expect(subject.jsonCalls[1]?.[0]).toBe(`/api/projects/${FIXTURE_PROJECT}/studio/relationships`);
    expect(decoded.graph_kind).toBe('ASSET_RELATIONSHIPS');
    expect(decoded.nodes).toHaveLength(3);
    expect(decoded.edges).toHaveLength(4);
    expect(decoded.executable).toBe(false);
    expect(decoded.knowledge_graph).toBe(false);
    expect(decoded.automatic_regeneration).toBe(false);
  });

  it('reads the original bytes only when asked', async () => {
    const blob = new Blob(['png'], { type: 'image/png' });
    const subject = client(assetRow(), blob);
    const value = await subject.client.downloadAsset!('asset-a');
    expect(value).toBe(blob);
    expect(subject.jsonCalls).toHaveLength(0);
    expect(subject.blobCalls[0]).toBe(`/api/projects/${FIXTURE_PROJECT}/studio/assets/asset-a/download`);
  });

  it('refuses an unusable asset id locally, without any request', async () => {
    const subject = client(listEnvelope([assetRow()]), new Blob(['x']));
    expect(codeOf(await failure(() => subject.client.readAsset('../etc/passwd'))))
      .toBe(ASSET_BROWSER_ERROR_CODES.readLocalInvalid);
    expect(subject.jsonCalls).toHaveLength(0);
    expect(codeOf(await failure(() => subject.client.downloadAsset!('a/b'))))
      .toBe(ASSET_BROWSER_ERROR_CODES.readLocalInvalid);
    expect(subject.blobCalls).toHaveLength(0);
  });

  it('rejects a foreign scope before sending anything', async () => {
    const recorder = fakeTransport(listEnvelope([]));
    const subject = createAssetBrowserClient(FIXTURE_PROJECT, recorder.transport,
      { workspaceId: 'w', projectId: 'other-project', storylineId: 's', branchId: 'b' });
    expect(codeOf(await failure(() => subject.listAssets()))).toBe(ASSET_BROWSER_ERROR_CODES.scopeMismatch);
    expect(recorder.jsonCalls).toHaveLength(0);
  });

  it('maps a denied read to a stable code and never to an empty library', async () => {
    const transport: StudioGraphTransport = {
      json: () => Promise.reject(new ApiError({ status: 403, code: 'CREATIVE_AUTHORITY_CHANGED', message: 'raw server text' })),
    };
    const subject = createAssetBrowserClient(FIXTURE_PROJECT, transport);
    const reason = await failure(() => subject.listAssets());
    // 拒绝读取**不是**空素材库：客户端只会抛出，绝不会返回 []。
    expect(reason.problem.code).toBe(ASSET_BROWSER_ERROR_CODES.authorityChanged);
    expect(reason.problem.message).toContain('身份或项目范围已经变化');
  });

  it('rejects an unauthorized read with the owner code and the denied wording', async () => {
    const transport: StudioGraphTransport = {
      json: () => Promise.reject(new ApiError({ status: 403, code: 'CREATIVE_AUTHORITY_INVALID', message: 'raw' })),
    };
    const reason = await failure(() => createAssetBrowserClient(FIXTURE_PROJECT, transport).listAssets());
    expect(reason.problem.code).toBe(ASSET_BROWSER_ERROR_CODES.authorityInvalid);
    expect(reason.problem.message).toContain('身份不可用');
  });

  it('keeps an owner bounded Chinese message for a 507 capacity refusal', async () => {
    const transport: StudioGraphTransport = {
      json: () => Promise.reject(new ApiError({ status: 507, code: 'CREATIVE_STORAGE_LOW_SPACE',
        message: '资产所在磁盘的可用空间不足。请释放空间后重试导入。' })),
    };
    const reason = await failure(() => createAssetBrowserClient(FIXTURE_PROJECT, transport).listAssets());
    expect(reason.problem.code).toBe(ASSET_BROWSER_ERROR_CODES.storageLowSpace);
    expect(reason.problem.message).toContain('磁盘');
  });

  it('explains a 404 as unavailable rather than empty', async () => {
    const transport: StudioGraphTransport = {
      json: () => Promise.reject(new ApiError({ status: 404, code: 'STUDIO_REQUEST_FAILED',
        message: '记录不可用，或此功能尚未启用。' })),
    };
    const reason = await failure(() => createAssetBrowserClient(FIXTURE_PROJECT, transport).listAssets());
    expect(reason.problem.code).toBe('STUDIO_REQUEST_FAILED');
    expect(reason.problem.message).toContain('不是"暂无素材"');
  });

  it('maps an invalid response shape to its own machine code', async () => {
    const subject = client(listEnvelope([{ id: 'asset-a' }]));
    expect(codeOf(await failure(() => subject.client.listAssets())))
      .toBe(ASSET_BROWSER_ERROR_CODES.listInvalid);
  });

  it('explains that this transport cannot read bytes instead of silently failing', async () => {
    const subject = client(listEnvelope([]));
    expect(codeOf(await failure(() => subject.client.downloadAsset!('asset-a'))))
      .toBe(ASSET_BROWSER_ERROR_CODES.studioResponseInvalid);
  });

  it('exposes only read-only facts and never claims an execution or a disk scan', () => {
    expect(ASSET_BROWSER_CLIENT_FACTS.read_only).toBe(true);
    expect(ASSET_BROWSER_CLIENT_FACTS.downloads_content).toBe(false);
    expect(ASSET_BROWSER_CLIENT_FACTS.scans_disk).toBe(false);
    expect(ASSET_BROWSER_CLIENT_FACTS.executes_work).toBe(false);
    expect(ASSET_BROWSER_CLIENT_FACTS.list_limit).toBe(500);
  });
});
