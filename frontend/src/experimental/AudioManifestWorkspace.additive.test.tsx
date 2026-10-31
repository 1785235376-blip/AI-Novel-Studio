// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ProductionLineagePanel } from './ProductionLineagePanel';
import { AudioManifestWorkspace } from './AudioManifestWorkspace';
import { audioManifestClient, checkedAudioPreview, checkedAudioManifest, type AudioPreview, type AudioManifest } from './audioManifestClient';
import type { ExperimentalClient } from './api';

const retained = vi.hoisted(() => ({ record: undefined as undefined | (() => void) }));
vi.mock('../ui/primitives', async importOriginal => {
  const actual = await importOriginal<typeof import('../ui/primitives')>();
  return { ...actual, Button: (props: Parameters<typeof actual.Button>[0]) => {
    if (props.children === '明确记录所选音频清单') retained.record = props.onClick as () => void;
    return <actual.Button {...props} />;
  } };
});
const root = '/production/audio-manifests', clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value));
const preview = (): AudioPreview => ({ capture_digest: 'e'.repeat(64), capture: {
  contract: 'studio-audio-manifest-capture/1', job: { id: 'audio-job', version: 5, operation_id: 'm8.audio.trim', request_id: 'original-audio-request', request_digest: 'a'.repeat(64), receipt_digest: 'b'.repeat(64) },
  result: { review_state: 'ORIGINAL_OWNER_REVIEWED', output_digest: 'c'.repeat(64) }, asset: { id: 'formal-audio', version: 2, digest: 'c'.repeat(64), kind: 'audio' },
  sources: [{ id: 'source-audio', kind: 'ASSET', asset_kind: 'audio', version: 1, digest: 'd'.repeat(64) }],
  environment: { state: 'UNKNOWN', model_hash: null, runtime: null, hardware: null }, replay: { supported: false, reason: 'NOT_IN_THIS_SLICE' } } });
const manifest = (requestId = 'manual-request'): AudioManifest => ({ ...preview(), contract: 'studio-audio-manifest/1', id: 'manifest-one', version: 1,
  created_at: '2026-10-20T00:00:00+00:00', request_id: requestId, replayable: false, manifest_digest: 'f'.repeat(64) });
function setup() {
  let saved: AudioManifest[] = [];
  const get = vi.fn<(path: string) => Promise<unknown>>(async (path: string) => {
    if (path === '/production/assets') return { items: [] };
    if (path === root + '/results') return { contract: 'studio-audio-manifest-results/1', items: [preview().capture.job].map(({ id, version, operation_id }) => ({ id, version, operation_id })), replayable: false };
    if (path === root) return { contract: 'studio-audio-manifest-list/1', items: clone(saved) };
    if (path === root + '/results/audio-job') return preview();
    if (path.startsWith(root + '/manifest-one')) return clone(saved[0]);
    throw new Error('Unexpected path ' + path);
  });
  const post = vi.fn(async (_path: string, body: { request_id: string }) => { const value = manifest(body.request_id); saved = [value]; return clone(value); });
  const client = { get, post, put: vi.fn(), blob: vi.fn() } as unknown as ExperimentalClient;
  return { get, post, client, persist: (requestId: string) => { saved = [manifest(requestId)]; } };
}
const region = () => screen.getByRole('region', { name: '现代 Studio Audio 结果清单' });
const click = (name: string) => fireEvent.click(within(region()).getByRole('button', { name }));
async function inspect() {
  click('读取已审核音频与清单'); await screen.findByRole('option', { name: /m8.audio.trim.*audio-job/ });
  fireEvent.change(screen.getByLabelText('已审核的现代音频结果'), { target: { value: 'audio-job' } });
  click('核对所选音频结果与正式资产'); await screen.findByRole('region', { name: '音频清单记录前核对' });
}
const confirm = () => fireEvent.click(screen.getByLabelText('已核对原任务版本、请求与输出摘要、正式资产版本，明确记录此次清单'));
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('modern Audio manifests beside preserved legacy lineage', () => {
  it('is independent of old manifest flag and does no Audio reads until explicit action', async () => {
    const state = setup(); render(<ProductionLineagePanel client={state.client} manifestsEnabled={false} />);
    await waitFor(() => expect(state.get).toHaveBeenCalledWith('/production/assets', expect.any(AbortSignal)));
    expect(region()).toBeTruthy(); expect(state.get.mock.calls.filter(([path]) => path.startsWith(root))).toHaveLength(0);
    expect(within(region()).getByText(/模型哈希、运行环境与硬件证据：未知/)).toBeTruthy();
    await inspect(); expect((within(region()).getByRole('button', { name: '明确记录所选音频清单' }) as HTMLButtonElement).disabled).toBe(true);
    expect(state.post).not.toHaveBeenCalled();
  });
  it('records only after explicit binding confirmation, once; reopens and exports through dedicated routes', async () => {
    const state = setup(); render(<AudioManifestWorkspace client={state.client} />); await inspect(); confirm();
    click('明确记录所选音频清单'); click('明确记录所选音频清单');
    await screen.findByRole('region', { name: '已核对的现代音频清单' });
    expect(state.post).toHaveBeenCalledTimes(1); expect(state.post).toHaveBeenCalledWith(root, expect.objectContaining({ job_id: 'audio-job', expected_job_version: 5, reviewed_capture_digest: 'e'.repeat(64), confirmed: true }));
    click('重开音频清单 audio-job · manifest-one'); await waitFor(() => expect(state.get).toHaveBeenCalledWith(root + '/manifest-one', expect.any(AbortSignal)));
    await screen.findByRole('region', { name: '已核对的现代音频清单' });
    const createObjectURL = vi.fn((_blob: Blob) => 'blob:synthetic-local-export'), revokeObjectURL = vi.fn();
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL }); vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    click('导出已核对音频清单 JSON'); await waitFor(() => expect(revokeObjectURL).toHaveBeenCalledWith('blob:synthetic-local-export'));
    expect(createObjectURL.mock.calls[0][0]).toBeInstanceOf(Blob);
    expect(state.get.mock.calls.some(([path]) => path === root + '/manifest-one/export')).toBe(true);
    expect(state.post.mock.calls.every(([path]) => path === root)).toBe(true); expect(state.client.put).not.toHaveBeenCalled();
  });
  it('rejects retained confirmation ABA callbacks before allocating a new request', async () => {
    const state = setup(); render(<AudioManifestWorkspace client={state.client} />); await inspect(); confirm(); const old = retained.record!;
    confirm(); confirm(); const uuid = vi.spyOn(crypto, 'randomUUID'); act(() => old()); expect(uuid).not.toHaveBeenCalled(); expect(state.post).not.toHaveBeenCalled();
    click('明确记录所选音频清单'); await screen.findByRole('region', { name: '已核对的现代音频清单' }); expect(uuid).toHaveBeenCalledTimes(1);
  });
  it('clears private details on revoked export instead of reusing cached JSON', async () => {
    const state = setup(); render(<AudioManifestWorkspace client={state.client} />); await inspect(); confirm(); click('明确记录所选音频清单');
    await screen.findByRole('region', { name: '已核对的现代音频清单' }); state.get.mockRejectedValueOnce(new Error('Synthetic denied read'));
    click('导出已核对音频清单 JSON'); await screen.findByText(/音频清单不可用或当前来源、权限已改变/);
    expect(screen.queryByRole('region', { name: '已核对的现代音频清单' })).toBeNull(); expect(within(region()).queryByText(/formal-audio/)).toBeNull();
    expect(state.post).toHaveBeenCalledTimes(1);
  });
  it('keeps uncertain record identity and recovers by read without another POST', async () => {
    const state = setup(); state.post.mockImplementationOnce(async (_path, body) => { state.persist(body.request_id); throw new TypeError('Synthetic lost response'); });
    render(<AudioManifestWorkspace client={state.client} />); await inspect(); confirm(); click('明确记录所选音频清单');
    await screen.findByText(/原记录仍待核对/); expect(screen.queryByRole('region', { name: '音频清单记录前核对' })).toBeNull();
    click('读取已审核音频与清单'); await screen.findByText(/已通过授权读取核对原记录/);
    expect(screen.getByRole('region', { name: '已核对的现代音频清单' })).toBeTruthy(); expect(state.post).toHaveBeenCalledTimes(1);
  });
  it('retires late preview after client ABA without showing old private bindings', async () => {
    const state = setup(); let resolve!: (value: unknown) => void;
    const original = state.get.getMockImplementation()!;
    state.get.mockImplementation(async path => path === root + '/results/audio-job' ? new Promise(done => { resolve = done; }) : original(path));
    const view = render(<AudioManifestWorkspace client={state.client} />); click('读取已审核音频与清单'); await screen.findByRole('option', { name: /m8.audio.trim/ });
    fireEvent.change(screen.getByLabelText('已审核的现代音频结果'), { target: { value: 'audio-job' } }); click('核对所选音频结果与正式资产');
    view.rerender(<AudioManifestWorkspace client={setup().client} />); view.rerender(<AudioManifestWorkspace client={state.client} />);
    await act(async () => resolve(preview())); expect(screen.queryByRole('region', { name: '音频清单记录前核对' })).toBeNull(); expect(state.post).not.toHaveBeenCalled();
  });
  it('rejects changed job version and malformed receipts rather than enabling recording', async () => {
    const state = setup(), original = state.get.getMockImplementation()!;
    state.get.mockImplementation(async path => path === root + '/results/audio-job' ? { ...preview(), capture: { ...preview().capture, job: { ...preview().capture.job, version: 6 } } } : original(path));
    render(<AudioManifestWorkspace client={state.client} />); click('读取已审核音频与清单'); await screen.findByRole('option', { name: /m8.audio.trim/ });
    fireEvent.change(screen.getByLabelText('已审核的现代音频结果'), { target: { value: 'audio-job' } }); click('核对所选音频结果与正式资产');
    await screen.findByText(/音频清单不可用/); expect(screen.queryByRole('region', { name: '音频清单记录前核对' })).toBeNull(); expect(state.post).not.toHaveBeenCalled();
  });
  it('adapter rejects raw private fields, false reproducibility claims and asset/output mismatch', async () => {
    expect(checkedAudioPreview(preview())).toEqual(preview()); expect(checkedAudioManifest(manifest())).toEqual(manifest());
    expect(() => checkedAudioPreview({ ...preview(), prompt: 'private' })).toThrow();
    const unsupported = clone(preview()); (unsupported.capture.environment as unknown as { state: string }).state = 'VERIFIED'; expect(() => checkedAudioPreview(unsupported)).toThrow();
    const forged = clone(preview()); forged.capture.asset.digest = '0'.repeat(64); expect(() => checkedAudioPreview(forged)).toThrow();
    const state = setup(); state.get.mockResolvedValueOnce({ ...manifest(), raw_prompt: 'private' });
    await expect(audioManifestClient(state.client).export('manifest-one')).rejects.toThrow();
  });
});
