// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { EmbeddingPanel } from './EmbeddingPanel';
import { experimentalClient } from './api';
const client = (id = 'n') => experimentalClient(id, { sessionToken: 'session' });
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const source = { entity: { entity_type: 'RESEARCH', entity_id: 'saved-source', screenplay_id: null }, title: '合成资料', source_version: 2, input_type: 'TEXT', available: true };
const row = { id: 'index', version: 3, title: 'Existing index', entities: [source.entity], status: 'ACTIVE', provider_status: 'CONFIGURED', model: { verification: 'MOCK_ONLY' } };
function fixture(indexes: any[] = [], post?: (url: string, init: RequestInit) => Promise<Response>) {
  return vi.fn(async (url: string, init: RequestInit) => {
    if (init.method !== 'GET') return post ? post(url, init) : response({ ...row, status: 'NOT_CONFIGURED' }, 201);
    if (url.endsWith('/status')) return response({ status: 'NOT_CONFIGURED', capability: null });
    if (url.endsWith('/sources')) return response({ items: [source] });
    if (url.endsWith('/providers')) return response({ items: [] });
    return response({ items: indexes });
  });
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('picks a scoped real research source without raw IDs and does not simulate embeddings', async () => {
  const fetch = fixture(); vi.stubGlobal('fetch', fetch);
  render(<EmbeddingPanel client={client()} />);
  await screen.findByText('NOT_CONFIGURED', { exact: true });
  fireEvent.change(screen.getByLabelText('索引实体类型'), { target: { value: 'RESEARCH' } });
  const option = await screen.findByRole('option', { name: /合成资料 · saved-source · v2/ });
  fireEvent.change(screen.getByLabelText('选择当前范围中的索引来源'), { target: { value: (option as HTMLOptionElement).value } });
  fireEvent.change(screen.getByLabelText('向量索引标题'), { target: { value: 'My reference index' } });
  expect((screen.getByRole('button', { name: '查询向量' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '保存索引定义' }));
  await waitFor(() => expect(fetch.mock.calls.some(([, init]) => init.method === 'POST')).toBe(true));
  const [url, init] = fetch.mock.calls.find(([, init]) => init.method === 'POST')!;
  expect(url.endsWith('/embeddings/indexes')).toBe(true);
  expect(JSON.parse(String(init.body))).toEqual({ title: 'My reference index', entities: [{ entity_type: 'RESEARCH', entity_id: 'saved-source' }], registration_id: null, dimensions: null });
  expect(fetch.mock.calls.some(([url]) => /rebuild|query/.test(url))).toBe(false);
});

it('source-version conflict preserves index editing input and sends captured expected version', async () => {
  const fetch = fixture([row], async () => response({ detail: { code: 'EXPERIMENTAL_VERSION_CONFLICT' } }, 409)); vi.stubGlobal('fetch', fetch);
  render(<EmbeddingPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: '编辑索引定义' }));
  fireEvent.change(screen.getByLabelText('向量索引标题'), { target: { value: 'Retained title' } });
  fireEvent.click(screen.getByRole('button', { name: '保存索引定义新版本' }));
  await screen.findByRole('alert');
  expect((screen.getByLabelText('向量索引标题') as HTMLInputElement).value).toBe('Retained title');
  expect(JSON.parse(String(fetch.mock.calls.find(([, init]) => init.method === 'PUT')![1].body)).expected_version).toBe(3);
});

it('supports explicit cancellation of a persisted interrupted BUILDING index', async () => {
  const fetch = fixture([{ ...row, status: 'BUILDING' }]); vi.stubGlobal('fetch', fetch);
  render(<EmbeddingPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: '取消索引构建' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/index/cancel'))).toBe(true));
  expect(JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/index/cancel'))![1].body))).toEqual({ expected_version: 3 });
});

it('rejects stale index query in the UI and clears prior scope results', async () => {
  const fetch = fixture([{ ...row, stale: true }]); vi.stubGlobal('fetch', fetch);
  const view = render(<EmbeddingPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: '选用此索引' }));
  fireEvent.change(screen.getByLabelText('视觉向量查询'), { target: { value: 'Synthetic query' } });
  expect((screen.getByRole('button', { name: '查询向量' }) as HTMLButtonElement).disabled).toBe(true);
  view.rerender(<EmbeddingPanel client={client('other')} />);
  expect((screen.getByLabelText('视觉向量查询') as HTMLInputElement).value).toBe('');
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
});
