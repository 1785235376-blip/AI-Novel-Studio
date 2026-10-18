// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import type { ExperimentalClient } from './api';
import { ProductionLineagePanel } from './ProductionLineagePanel';
import { ProductionPassportSidecar } from './ProductionPassportSidecar';

const outputs = [{ proposal_id: 'original/with space', candidate_index: 0, digest: 'a'.repeat(64) }, { proposal_id: 'second-output', candidate_index: 1, digest: 'b'.repeat(64) }];
const original = { manifestId: 'manifest/with space', manifestVersion: 3, receiptIdentity: 'original-receipt', outputs };
const zip = () => new Blob(['PK\u0003\u0004original-output-and-report'], { type: 'application/zip' });
const create = vi.fn(), revoke = vi.fn();
const originalCreate = Object.getOwnPropertyDescriptor(URL, 'createObjectURL');
const originalRevoke = Object.getOwnPropertyDescriptor(URL, 'revokeObjectURL');
function client() {
  return { get: vi.fn(), post: vi.fn(), put: vi.fn(), blob: vi.fn(async () => zip()) } as unknown as ExperimentalClient;
}
function pending() {
  let resolve!: (value: Blob) => void, reject!: (value: unknown) => void;
  const promise = new Promise<Blob>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function select(id = outputs[0].proposal_id) { fireEvent.change(screen.getByLabelText('Passport 原始输出候选'), { target: { value: id } }); }
function download() { fireEvent.click(screen.getByRole('button', { name: /^(重试|重新)?下载未签名 Passport ZIP$/ })); }
const notice = () => screen.queryByText('已发起未签名 Passport ZIP 下载。请以浏览器实际保存结果为准。');
beforeEach(() => {
  create.mockReset().mockReturnValue('blob:passport'); revoke.mockReset();
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: create });
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revoke });
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
});
afterEach(() => {
  cleanup(); vi.restoreAllMocks();
  if (originalCreate) Object.defineProperty(URL, 'createObjectURL', originalCreate); else Reflect.deleteProperty(URL, 'createObjectURL');
  if (originalRevoke) Object.defineProperty(URL, 'revokeObjectURL', originalRevoke); else Reflect.deleteProperty(URL, 'revokeObjectURL');
});

describe('ProductionPassportSidecar bounded unsigned download', () => {
  it('requires explicit selection and downloads the exact versioned output through the captured blob client', async () => {
    const api = client(); render(<StrictMode><ProductionPassportSidecar client={api} {...original} /></StrictMode>);
    expect(api.blob).not.toHaveBeenCalled();
    expect((screen.getByRole('button', { name: '下载未签名 Passport ZIP' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/候选列表本身不表示已批准/)).toBeTruthy();
    expect(screen.getByText(/不是作者身份认证、C2PA 凭证或法律版权认证/)).toBeTruthy();
    expect(screen.getByText(/不代表完整 DIF12 验收/)).toBeTruthy();
    expect(screen.getByText(/若输出与报告同时被替换/)).toBeTruthy();
    select(); download();
    await waitFor(() => expect(notice()).toBeTruthy());
    expect(api.blob).toHaveBeenCalledTimes(1); expect(api.blob).toHaveBeenCalledWith('/production/manifests/manifest%2Fwith%20space/outputs/original%2Fwith%20space/passport?expected_version=3', expect.any(AbortSignal));
    expect(create).toHaveBeenCalledTimes(1); expect(create.mock.calls[0][0].type).toBe('application/zip');
    expect(HTMLAnchorElement.prototype.click).toHaveBeenCalledTimes(1);
    const anchor = vi.mocked(HTMLAnchorElement.prototype.click).mock.instances[0] as unknown as HTMLAnchorElement;
    expect(anchor.download).toBe('production-passport-unsigned.zip'); expect(anchor.href).toBe('blob:passport');
    expect(revoke).toHaveBeenCalledTimes(1); expect(revoke).toHaveBeenCalledWith('blob:passport');
    expect(api.get).not.toHaveBeenCalled(); expect(api.post).not.toHaveBeenCalled(); expect(api.put).not.toHaveBeenCalled();
    select(outputs[1].proposal_id); expect(notice()).toBeNull(); download();
    await waitFor(() => expect(notice()).toBeTruthy());
    expect(api.blob).toHaveBeenLastCalledWith('/production/manifests/manifest%2Fwith%20space/outputs/second-output/passport?expected_version=3', expect.any(AbortSignal));
  });

  it('shows an honest empty state and never requests without an output', () => {
    const api = client(); render(<ProductionPassportSidecar client={api} {...original} outputs={[]} />);
    expect(screen.getByText('没有可选择的原始输出')).toBeTruthy();
    expect((screen.getByLabelText('Passport 原始输出候选') as HTMLSelectElement).disabled).toBe(true);
    download(); expect(api.blob).not.toHaveBeenCalled();
  });

  it.each([
    { manifestId: '' }, { manifestId: 'x'.repeat(241) }, { manifestVersion: 0 }, { manifestVersion: 1.5 }, { manifestVersion: Number.MAX_SAFE_INTEGER + 1 },
    { outputs: [{ proposal_id: '', candidate_index: 0 }] }, { outputs: [{ proposal_id: 'p', candidate_index: -1 }] },
    { outputs: [{ proposal_id: 'p', candidate_index: 0.5 }] }, { outputs: [{ proposal_id: 'p', candidate_index: 8 }] },
    { outputs: [outputs[0], outputs[0]] }, { outputs: [outputs[0], { ...outputs[1], candidate_index: 0 }] },
    { outputs: Array.from({ length: 9 }, (_, candidate_index) => ({ proposal_id: `p-${candidate_index}`, candidate_index })) },
  ])('fails closed before request for malformed manifest/output identity %j', invalid => {
    const api = client(); render(<ProductionPassportSidecar client={api} {...original} {...invalid} />);
    expect(screen.getByRole('alert').textContent).toContain('下载已禁用');
    download(); expect(api.blob).not.toHaveBeenCalled(); expect(create).not.toHaveBeenCalled();
  });

  it('allows only one in-flight request, aborts cancellation and fences late completion before an explicit retry', async () => {
    const api = client(), old = pending(), fresh = pending();
    vi.mocked(api.blob).mockReturnValueOnce(old.promise).mockReturnValueOnce(fresh.promise);
    render(<ProductionPassportSidecar client={api} {...original} />); select(); download();
    fireEvent.click(screen.getByRole('button', { name: '正在准备 Passport…' }));
    expect(api.blob).toHaveBeenCalledTimes(1);
    expect(screen.getByText('正在读取已授权的原始输出与有界报告…')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '取消下载准备' }));
    expect(vi.mocked(api.blob).mock.calls[0][1]?.aborted).toBe(true);
    expect(screen.getByText('已取消下载准备。再次下载需要明确操作。')).toBeTruthy();
    download();
    await act(async () => old.resolve(zip()));
    expect(create).not.toHaveBeenCalled(); expect(notice()).toBeNull();
    expect((screen.getByRole('button', { name: '正在准备 Passport…' }) as HTMLButtonElement).disabled).toBe(true);
    await act(async () => fresh.resolve(zip()));
    expect(create).toHaveBeenCalledTimes(1); expect(notice()).toBeTruthy();
  });

  it('changing the selected output aborts the old request and ignores its late rejection', async () => {
    const api = client(), old = pending(); vi.mocked(api.blob).mockReturnValueOnce(old.promise);
    render(<ProductionPassportSidecar client={api} {...original} />); select(); download(); select(outputs[1].proposal_id);
    expect(vi.mocked(api.blob).mock.calls[0][1]?.aborted).toBe(true);
    expect(api.blob).toHaveBeenCalledTimes(1);
    await act(async () => old.reject(new Error('private old error')));
    expect(screen.queryByRole('alert')).toBeNull(); expect(create).not.toHaveBeenCalled();
    download(); await waitFor(() => expect(notice()).toBeTruthy());
    expect(api.blob).toHaveBeenCalledTimes(2);
  });

  it.each([401, 403, 404, 409, 422, 500])('sanitizes HTTP %s failure, clears prior success, and retries only on request', async status => {
    const api = client(); render(<ProductionPassportSidecar client={api} {...original} />); select(); download();
    await waitFor(() => expect(notice()).toBeTruthy());
    const failure = pending(); vi.mocked(api.blob).mockReturnValueOnce(failure.promise);
    download(); expect(notice()).toBeNull();
    await act(async () => failure.reject(new ApiError({ status, code: 'PRIVATE_SERVER_CODE', message: 'PRIVATE_SERVER_MESSAGE' })));
    expect(screen.getByRole('alert')).toBeTruthy(); expect(screen.queryByText(/PRIVATE_SERVER/)).toBeNull();
    expect(notice()).toBeNull(); expect(create).toHaveBeenCalledTimes(1); expect(api.blob).toHaveBeenCalledTimes(2);
    download(); await waitFor(() => expect(notice()).toBeTruthy());
    expect(api.blob).toHaveBeenCalledTimes(3); expect(api.post).not.toHaveBeenCalled(); expect(api.put).not.toHaveBeenCalled();
  });

  it.each(['non-blob', 'empty', 'wrong MIME', 'oversized'])('rejects %s response without making a URL', async kind => {
    let response: unknown = zip();
    if (kind === 'non-blob') response = { type: 'application/zip', size: 1 };
    if (kind === 'empty') response = new Blob([], { type: 'application/zip' });
    if (kind === 'wrong MIME') response = new Blob(['<html>private</html>'], { type: 'text/html' });
    if (kind === 'oversized') Object.defineProperty(response, 'size', { value: 28 * 1024 * 1024 + 1 });
    const api = client(); vi.mocked(api.blob).mockResolvedValue(response as Blob);
    render(<ProductionPassportSidecar client={api} {...original} />); select(); download();
    expect(await screen.findByRole('alert')).toBeTruthy(); expect(create).not.toHaveBeenCalled(); expect(notice()).toBeNull();
  });

  it('accepts a bounded ZIP with Content-Type parameters and cleans every retry URL', async () => {
    const api = client(), response = new Blob(['PK'], { type: 'application/zip; charset=binary' });
    Object.defineProperty(response, 'size', { value: 28 * 1024 * 1024 });
    vi.mocked(api.blob).mockResolvedValue(response);
    render(<ProductionPassportSidecar client={api} {...original} />); select(); download();
    await waitFor(() => expect(notice()).toBeTruthy()); download();
    await waitFor(() => expect(revoke).toHaveBeenCalledTimes(2));
    expect(create).toHaveBeenCalledTimes(2);
  });

  it('revokes the URL even if the browser refuses the click and exposes explicit retry', async () => {
    const api = client(); vi.mocked(HTMLAnchorElement.prototype.click).mockImplementationOnce(() => { throw new Error('private browser failure'); });
    render(<ProductionPassportSidecar client={api} {...original} />); select(); download();
    expect(await screen.findByRole('alert')).toBeTruthy(); expect(notice()).toBeNull();
    expect(revoke).toHaveBeenCalledTimes(1); expect(revoke).toHaveBeenCalledWith('blob:passport'); expect(screen.queryByText(/private browser failure/)).toBeNull();
    download(); await waitFor(() => expect(notice()).toBeTruthy()); expect(revoke).toHaveBeenCalledTimes(2);
  });

  it.each(['client', 'manifest', 'version', 'receipt identity', 'output digest'])('aborts and fences %s A→B→A, including clients that ignore abort', async change => {
    const api = client(), other = client(), late = pending(); vi.mocked(api.blob).mockReturnValueOnce(late.promise);
    const first = { client: api, ...original };
    const renderPanel = (props: typeof first) => <StrictMode><ProductionPassportSidecar {...props} /></StrictMode>;
    const view = render(renderPanel(first)); select(); download();
    const changed = { ...first, ...(change === 'client' ? { client: other }
      : change === 'manifest' ? { manifestId: 'other' }
        : change === 'version' ? { manifestVersion: 4 }
          : change === 'receipt identity' ? { receiptIdentity: 'changed' }
            : { outputs: [{ ...outputs[0], digest: 'c'.repeat(64) }, outputs[1]] }) };
    view.rerender(renderPanel(changed)); view.rerender(renderPanel(first));
    expect(vi.mocked(api.blob).mock.calls[0][1]?.aborted).toBe(true);
    expect((screen.getByLabelText('Passport 原始输出候选') as HTMLSelectElement).value).toBe('');
    await act(async () => late.resolve(zip()));
    expect(create).not.toHaveBeenCalled(); expect(notice()).toBeNull();
    expect(api.blob).toHaveBeenCalledTimes(1); expect(other.blob).not.toHaveBeenCalled();
    select(); download(); await waitFor(() => expect(notice()).toBeTruthy());
    expect(api.blob).toHaveBeenCalledTimes(2);
  });

  it('clears completed feedback and selection on a version change', async () => {
    const api = client(), view = render(<ProductionPassportSidecar client={api} {...original} />); select(); download();
    await waitFor(() => expect(notice()).toBeTruthy());
    view.rerender(<ProductionPassportSidecar client={api} {...original} manifestVersion={4} />);
    expect(notice()).toBeNull(); expect((screen.getByLabelText('Passport 原始输出候选') as HTMLSelectElement).value).toBe('');
    expect(api.blob).toHaveBeenCalledTimes(1); expect(revoke).toHaveBeenCalledTimes(1);
  });

  it.each(['resolve', 'reject'])('aborts unmount and never creates URLs or feedback on late %s', async outcome => {
    const api = client(), late = pending(); vi.mocked(api.blob).mockReturnValue(late.promise);
    const view = render(<ProductionPassportSidecar client={api} {...original} />); select(); download(); view.unmount();
    expect(vi.mocked(api.blob).mock.calls[0][1]?.aborted).toBe(true);
    await act(async () => { if (outcome === 'resolve') late.resolve(zip()); else late.reject(new Error('late error')); });
    expect(create).not.toHaveBeenCalled(); expect(HTMLAnchorElement.prototype.click).not.toHaveBeenCalled(); expect(notice()).toBeNull();
  });

  it('mounts only in the selected production manifest while keeping the original JSON export', async () => {
    const api = client(), hash = 'a'.repeat(64);
    const manifest = { id: original.manifestId, version: original.manifestVersion, created_at: '2026-10-18', task_id: 'task-original', task_version: 3, operation: 'cover_generation', input_digest: hash, manifest_digest: hash, adapter_id: 'synthetic', model_id: null, parameters: { candidate_count: 2 }, seed: { value: null }, environment: null, outputs, input_versions: [] };
    vi.mocked(api.get).mockImplementation(async path => path === '/production/manifests' ? { items: [manifest] } : { items: [] });
    render(<ProductionLineagePanel client={api} manifestsEnabled />);
    expect(screen.queryByRole('region', { name: '未签名 Production Passport' })).toBeNull();
    fireEvent.click(await screen.findByRole('button', { name: /清单 cover_generation/ }));
    expect(await screen.findByRole('region', { name: '未签名 Production Passport' })).toBeTruthy();
    expect(screen.getByRole('button', { name: '下载脱敏生产清单' })).toBeTruthy();
    expect(api.blob).not.toHaveBeenCalled(); select(); download();
    await waitFor(() => expect(notice()).toBeTruthy());
    expect(api.blob).toHaveBeenCalledWith('/production/manifests/manifest%2Fwith%20space/outputs/original%2Fwith%20space/passport?expected_version=3', expect.any(AbortSignal));
    expect(api.post).not.toHaveBeenCalled(); expect(api.put).not.toHaveBeenCalled();
  });
});
