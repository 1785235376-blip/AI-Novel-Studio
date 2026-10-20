// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor, cleanup } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { SafeBatchesPanel } from './SafeBatchesPanel';
import { experimentalClient } from './api';
import captured from './SafeBatchesPanel.studioImage.file-api.json';

const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const legacy = { chapters: [], briefs: [], presets: [], formats: ['txt'], unsupported: [], concurrency: 1, known_cost_microusd: 0 };
function setup(rows: unknown[] = [], mutation?: (url: string, init: RequestInit) => Promise<Response> | Response) {
  const state = { rows, catalog: structuredClone(captured.catalog) };
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (init.method !== 'GET') return mutation ? mutation(url, init) : reply(captured.preflight);
    if (url.endsWith('/studio-image/catalog')) return reply(state.catalog);
    if (url.endsWith('/catalog')) return reply(legacy);
    if (url.endsWith('/image')) return new Response(new Uint8Array([137, 80, 78, 71]), { headers: { 'Content-Type': 'image/png' } });
    return reply({ items: state.rows });
  });
  vi.stubGlobal('fetch', fetch);
  const NativeURL = URL;
  vi.stubGlobal('URL', class extends NativeURL { static createObjectURL = vi.fn(() => 'blob:synthetic-u16'); static revokeObjectURL = vi.fn(); });
  const client = experimentalClient('u16-fixture', { sessionToken: 'synthetic-host' });
  return { state, fetch, client, ...render(<SafeBatchesPanel client={client} />) };
}
async function addSelection() {
  const image = screen.getByLabelText('批次抠图图像') as HTMLSelectElement;
  await waitFor(() => expect(image.disabled).toBe(false));
  fireEvent.change(image, { target: { value: captured.selection.studio_image.image.id } });
  fireEvent.change(screen.getByLabelText('批次抠图遮罩'), { target: { value: captured.selection.studio_image.mask.id } });
  fireEvent.click(screen.getByRole('button', { name: '添加此图像与遮罩到批次' }));
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it('mount only reads; explicit image/mask snapshots preflight once with hard zero and no create/execute', async () => {
  let release!: (response: Response) => void;
  const e = setup([], () => new Promise<Response>(resolve => { release = resolve; }));
  await addSelection();
  expect(e.fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  const button = screen.getByRole('button', { name: '仅预检所选批次' });
  fireEvent.click(button); fireEvent.click(button);
  await waitFor(() => expect(e.fetch.mock.calls.filter(([url]) => url.endsWith('/preflight'))).toHaveLength(1));
  const body = JSON.parse(String(e.fetch.mock.calls.find(([url]) => url.endsWith('/preflight'))![1].body));
  expect(body).toMatchObject({ concurrency: 1, budget_microusd: 0, skip_satisfied: true, items: [{ kind: 'STUDIO_IMAGE', studio_image: {
    image: captured.selection.studio_image.image, mask: captured.selection.studio_image.mask, license_note: '' } }] });
  expect(body.items).toHaveLength(1); expect(body.items[0].studio_image.request_id).toMatch(/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/);
  expect(e.fetch.mock.calls.some(([url]) => /dispatch|execute|\/jobs/.test(url))).toBe(false);
  release(reply(captured.preflight));
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
});

it('source refresh retains old explicit pins and disables preflight instead of silently replacing them', async () => {
  const e = setup(); await addSelection();
  e.state.catalog.assets[0].snapshot.version++;
  fireEvent.click(screen.getByRole('button', { name: '刷新批次状态' }));
  await screen.findByText('此项来源版本或授权已变化，未自动替换。请移除后重新明确选择。');
  expect((screen.getByRole('button', { name: '仅预检所选批次' }) as HTMLButtonElement).disabled).toBe(true);
  expect(e.fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  expect(screen.getByText(new RegExp(`图像 ${captured.selection.studio_image.image.id} · v1`))).toBeTruthy();
});

it('original CPU candidate requires its own preview and confirmation; review binds exact job/version/request/output', async () => {
  const e = setup([captured.executed], () => reply(captured.approved));
  const accept = await screen.findByRole('button', { name: '确认接受阶段 1 抠图候选' }) as HTMLButtonElement;
  expect(accept.disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('已预览并核对阶段 1 抠图候选'));
  expect(accept.disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '预览阶段 1 抠图候选' }));
  await screen.findByAltText('阶段 1 原 CPU 抠图候选');
  await waitFor(() => expect(accept.disabled).toBe(false));
  fireEvent.click(accept); fireEvent.click(accept);
  await waitFor(() => expect(e.fetch.mock.calls.filter(([url]) => url.endsWith('/approve-image'))).toHaveLength(1));
  const body = JSON.parse(String(e.fetch.mock.calls.find(([url]) => url.endsWith('/approve-image'))![1].body));
  const job = captured.executed.items[0].image_result;
  expect(body).toEqual({ expected_version: captured.executed.version, snapshot_digest: captured.executed.snapshot_digest,
    confirmed: true, budget_microusd: 0, item_index: 0, job_id: job.id, expected_job_version: job.version,
    expected_request_digest: job.request_digest, reviewed_output_digest: job.output_candidate.digest });
  expect(e.fetch.mock.calls.some(([url]) => /dispatch-next|\/execute/.test(url))).toBe(false);
});

it.each(['UNKNOWN', 'PARTIAL'])('does not offer image replay for %s and never creates a replacement key', async status => {
  const row = { ...captured.ready, status, items: [{ ...captured.ready.items[0], status: status === 'UNKNOWN' ? 'UNKNOWN' : 'FAILED', attempts: 1 }] };
  const e = setup([row]);
  await screen.findByLabelText(`批次 ${row.id}`);
  expect(screen.queryByRole('button', { name: '执行下一阶段' })).toBeNull();
  expect(screen.queryByRole('button', { name: '仅预检失败项重试' })).toBeNull();
  if (status === 'UNKNOWN') {
    fireEvent.click(screen.getByRole('button', { name: '仅查询原任务终态回执' }));
    await waitFor(() => expect(e.fetch.mock.calls.filter(([url]) => url.endsWith('/reconcile'))).toHaveLength(1));
  }
  expect(e.fetch.mock.calls.some(([url]) => /preflight|dispatch-next|retry-failed|approve-image/.test(url))).toBe(false);
});

it('scope replacement retires image selections and late old catalog data', async () => {
  const e = setup(); await addSelection();
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(() => {})));
  e.rerender(<SafeBatchesPanel client={experimentalClient('other-scope', { sessionToken: 'other-host' })} />);
  expect(screen.queryByRole('button', { name: '移除抠图项 1' })).toBeNull();
  expect((screen.getByLabelText('批次抠图图像') as HTMLSelectElement).value).toBe('');
});
