// @vitest-environment jsdom
import { StrictMode } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { TimelineExchangePanel } from './TimelineExchangePanel';
import { experimentalClient } from './api';
import { readOtioFile } from './timelineExchangeClient';
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const record = { id: 'exchange', version: 1, status: 'DRAFT', origin: 'IMPORTED_EXCHANGE_COPY', stale: false, filename: 'timeline-exchange.otio', summary: { name: 'Synthetic edits', tracks: [{ name: 'V1', kind: 'Video', duration_seconds: { numerator: 1001, denominator: 30000 }, cuts: [] }] }, loss_report: [{ path: 'track[0]', code: 'MISSING_MEDIA', severity: 'WARNING' }], media: [{ name: 'a', state: 'MISSING', target_url: null }] };
const client = (nid = 'novel') => experimentalClient(nid, { sessionToken: 'trusted' });
function fetcher(available = true, mutation?: (url: string, init: RequestInit) => Response | Promise<Response>) {
  return vi.fn(async (url: string, init: RequestInit) => {
    if (init.method !== 'GET') return mutation ? mutation(url, init) : reply(record, 201);
    if (url.endsWith('/catalog')) return reply({ screenplays: [], assets: [], parser: { available, required_version: '0.18.1' }, limitations: [] });
    if (url.includes('/file?')) return new Response('{"OTIO_SCHEMA":"Timeline.1"}', { headers: { 'Content-Type': 'application/json' } });
    return reply({ items: [record] });
  });
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it('reads catalog on mount, exposes exact rational duration and missing parser without auto install', async () => {
  const fetch = fetcher(false); vi.stubGlobal('fetch', fetch);
  render(<StrictMode><TimelineExchangePanel client={client()} /></StrictMode>);
  await screen.findByText(/缺少已验证的 OpenTimelineIO/);
  expect(screen.getByText(/1001\/30000 秒/)).toBeTruthy();
  expect((screen.getByRole('button', { name: '检查并保存 OTIO 交换副本' }) as HTMLButtonElement).disabled).toBe(true);
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
});

it('reads actual selected File only on import and keeps UTF-8 bytes in captured request', async () => {
  const fetch = fetcher(); vi.stubGlobal('fetch', fetch); render(<TimelineExchangePanel client={client()} />);
  await screen.findByText('Synthetic edits');
  const text = '{"name":"合成剪辑"}'; fireEvent.change(screen.getByLabelText('选择本地 OTIO 文件'), { target: { files: [new File([text], 'sample.otio')] } });
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '检查并保存 OTIO 交换副本' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/import'))).toBe(true));
  expect(JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/import'))![1].body))).toEqual({ filename: 'sample.otio', content: text });
  expect(await readOtioFile(new File(['中文'], 'x.otio'))).toBe('中文');
  await expect(readOtioFile(new File(['x'], 'x.xml'))).rejects.toThrow();
  await expect(readOtioFile(new File([new Uint8Array([0xff, 0xfe])], 'bad.otio'))).rejects.toThrow(/UTF-8/);
});

it('requires loss review before download and clears approval on refresh', async () => {
  const fetch = fetcher(); vi.stubGlobal('fetch', fetch); render(<TimelineExchangePanel client={client()} />);
  const button = await screen.findByRole('button', { name: '下载新的 OTIO 文件' }) as HTMLButtonElement;
  expect(button.disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('已核对本记录的损失、媒体引用和目标软件未验证边界')); expect(button.disabled).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: '刷新交换来源与记录' }));
  await waitFor(() => expect((screen.getByRole('button', { name: '下载新的 OTIO 文件' }) as HTMLButtonElement).disabled).toBe(true));
  expect(fetch.mock.calls.some(([url]) => url.includes('/file?'))).toBe(false);
});

it('permission error retains selected file; changed scope clears references immediately', async () => {
  const fetch = fetcher(true, () => reply({ detail: { code: 'FORBIDDEN' } }, 403)); vi.stubGlobal('fetch', fetch);
  const view = render(<TimelineExchangePanel client={client()} />); await screen.findByText('Synthetic edits');
  fireEvent.change(screen.getByLabelText('选择本地 OTIO 文件'), { target: { files: [new File(['{}'], 'keep.otio')] } }); fireEvent.click(screen.getByRole('button', { name: '检查并保存 OTIO 交换副本' }));
  await screen.findByText(/FORBIDDEN/); expect(screen.getByText(/已选择：keep.otio/)).toBeTruthy();
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(() => {}))); view.rerender(<TimelineExchangePanel client={client('other')} />);
  expect(screen.queryByText('Synthetic edits')).toBeNull(); expect(screen.queryByText(/keep.otio/)).toBeNull();
});
