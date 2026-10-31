// @vitest-environment jsdom
import { StrictMode } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { PortableProjectsPanel } from './PortableProjectsPanel';
import { experimentalClient } from './api';
import { readPortableFile } from './portableProjectsClient';
const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const catalog = { chapters: [{ id: 'c1', title: '合成海港', version: 2 }], missing: [], restore_available: true, limitations: [] };
const imported = { id: 'import', version: 1, kind: 'IMPORT', status: 'PREFLIGHT', snapshot_digest: 'a'.repeat(64), title: '便携副本', chapter_count: 1, media: [{ ref: 'a0001', state: 'MISSING' }] };
const storage = { categories: [{ kind: 'HISTORY', bytes: null, cleanable: false }, { kind: 'REPRODUCIBLE_CACHE', bytes: 100, cleanable: true }], eligible: [{ id: 'export', version: 1, bytes: 100, sha256: 'b'.repeat(64) }], preview_digest: 'c'.repeat(64) };
const client = (nid = 'n1') => experimentalClient(nid, { sessionToken: 'host', scope: { branchId: 'branch' } as any });
function requests(items: unknown[] = [imported], mutation?: (url: string, init: RequestInit) => Response | Promise<Response>) {
  return vi.fn(async (url: string, init: RequestInit) => {
    if (init.method !== 'GET') return mutation ? mutation(url, init) : reply(imported);
    if (url.endsWith('/catalog')) return reply(catalog);
    if (url.endsWith('/storage')) return reply(storage);
    return reply({ items });
  });
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
it('StrictMode does not upload or restore, missing assets are declared and explicit restore binds exact snapshot', async () => {
  const fetch = requests(); vi.stubGlobal('fetch', fetch); render(<StrictMode><PortableProjectsPanel client={client()} /></StrictMode>);
  await screen.findByText('便携副本'); expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  expect(screen.getByText(/缺失媒体 1 项/)).toBeTruthy(); const button = screen.getByRole('button', { name: '确认恢复到新项目' }) as HTMLButtonElement;
  expect(button.disabled).toBe(true); fireEvent.click(screen.getByLabelText('已核对本记录与缺失项，确认创建新项目副本')); fireEvent.click(button);
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/restore'))).toBe(true));
  const [, init] = fetch.mock.calls.find(([url]) => url.endsWith('/restore'))!;
  expect(JSON.parse(String(init.body))).toEqual({ expected_version: 1, snapshot_digest: imported.snapshot_digest, confirmed: true });
  expect(init.headers).toMatchObject({ 'X-Session-Token': 'host', 'X-Branch-Id': 'branch' });
});
it('reads only selected ZIP after explicit preflight, does not start restore and retains file after conflict', async () => {
  const fetch = requests([], () => reply({ detail: { code: 'EXPERIMENTAL_SOURCE_STALE' } }, 409)); vi.stubGlobal('fetch', fetch);
  render(<PortableProjectsPanel client={client()} />); await screen.findByLabelText('合成海港 · v2');
  fireEvent.change(screen.getByLabelText('选择便携 ZIP 文件'), { target: { files: [new File(['synthetic bytes'], 'keep.zip')] } });
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '仅预检便携包' })); await screen.findByText(/EXPERIMENTAL_SOURCE_STALE/);
  const call = fetch.mock.calls.find(([url]) => url.endsWith('/import-preflight'))!;
  expect(JSON.parse(String(call[1].body))).toEqual({ filename: 'keep.zip', content_base64: btoa('synthetic bytes') });
  expect(screen.getByText(/已选择：keep.zip/)).toBeTruthy(); expect(fetch.mock.calls.some(([url]) => url.endsWith('/restore'))).toBe(false);
  await expect(readPortableFile(new File([], 'empty.zip'))).rejects.toThrow();
});
it('cleanup is preview-confirmed and carries no arbitrary path; refresh clears confirmation', async () => {
  const fetch = requests([]); vi.stubGlobal('fetch', fetch); render(<PortableProjectsPanel client={client()} />);
  const button = await screen.findByRole('button', { name: '确认清理预览中的缓存' }) as HTMLButtonElement; expect(button.disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('已核对当前预览，只清理列出的可重建缓存')); fireEvent.click(button);
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/cleanup'))).toBe(true));
  expect(JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/cleanup'))![1].body))).toEqual({ record_ids: ['export'], preview_digest: storage.preview_digest, confirmed: true });
});
it('relink mismatch requires explicit replacement and scope switch removes old file and confirmation', async () => {
  const row = { ...imported, kind: 'RELINK', title: undefined, digest_matches: false }; const fetch = requests([row]); vi.stubGlobal('fetch', fetch);
  const view = render(<PortableProjectsPanel client={client()} />); await screen.findByText(/内容摘要不同或原摘要未知/);
  fireEvent.click(screen.getByLabelText('已核对本记录与缺失项，确认重连所列章节引用'));
  expect((screen.getByRole('button', { name: '确认重连当前引用' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('明确使用内容不同或摘要未知的替代文件'));
  expect((screen.getByRole('button', { name: '确认重连当前引用' }) as HTMLButtonElement).disabled).toBe(false);
  fireEvent.change(screen.getByLabelText('选择便携 ZIP 文件'), { target: { files: [new File(['x'], 'old.zip')] } });
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(() => {}))); view.rerender(<PortableProjectsPanel client={client('other')} />);
  expect(screen.queryByText(/old.zip/)).toBeNull(); expect(screen.queryByText(/内容摘要不同或原摘要未知/)).toBeNull();
});
it('late file read cannot issue a mutation after scope unmount', async () => {
  const fetch = requests([]); vi.stubGlobal('fetch', fetch); const view = render(<PortableProjectsPanel client={client()} />); await screen.findByLabelText('合成海港 · v2');
  let reader: any; vi.stubGlobal('FileReader', class { result = 'data:application/zip;base64,eA=='; onload?: () => void; constructor() { reader = this; } readAsDataURL() {} });
  fireEvent.change(screen.getByLabelText('选择便携 ZIP 文件'), { target: { files: [new File(['x'], 'old.zip')] } }); fireEvent.click(screen.getByRole('button', { name: '仅预检便携包' }));
  view.unmount(); reader.onload(); await Promise.resolve(); expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
});
