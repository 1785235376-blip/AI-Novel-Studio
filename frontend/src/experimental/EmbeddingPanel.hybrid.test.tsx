// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { EmbeddingPanel } from './EmbeddingPanel';
import { experimentalClient } from './api';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it('uses the hybrid endpoint with captured index version and preserves conflict input', async () => {
  const row = { id: 'index', title: 'Story sources', version: 3, index_version: 2, status: 'ACTIVE', provider_status: 'CONFIGURED', entities: [{ entity_type: 'STORY', entity_id: 'chapter' }] };
  const fetch = vi.fn(async (url: string, init: RequestInit) => new Response(JSON.stringify(init.method === 'POST' ? { detail: { code: 'EMBEDDING_INDEX_CHANGED' } } : url.endsWith('/status') ? { status: 'CONFIGURED', capability: { verification: 'MOCK_ONLY' } } : { items: url.endsWith('/indexes') ? [row] : [] }), { status: init.method === 'POST' ? 409 : 200 }));
  vi.stubGlobal('fetch', fetch);
  render(<EmbeddingPanel client={experimentalClient('n', { sessionToken: 'session' })} />);
  fireEvent.click(await screen.findByRole('button', { name: '选用此索引' }));
  fireEvent.change(screen.getByLabelText('检索方式'), { target: { value: 'HYBRID' } });
  fireEvent.change(screen.getByLabelText('视觉向量查询'), { target: { value: 'healer' } });
  fireEvent.click(screen.getByRole('button', { name: '查询向量' }));
  await screen.findByRole('alert');
  const call = fetch.mock.calls.find(([, init]) => init.method === 'POST')!;
  expect(call[0].endsWith('/embeddings/hybrid-query')).toBe(true);
  expect(JSON.parse(String(call[1].body))).toEqual({ index_id: 'index', text: 'healer', limit: 10, expected_index_version: 2 });
  expect((screen.getByLabelText('视觉向量查询') as HTMLInputElement).value).toBe('healer');
  expect(screen.getByText(/未验证语义质量/)).toBeTruthy();
});
it('never enables hybrid retrieval without a configured current index', async () => {
  const fetch = vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith('/status') ? { status: 'NOT_CONFIGURED', capability: null } : { items: [] }), { status: 200 }));
  vi.stubGlobal('fetch', fetch);
  render(<EmbeddingPanel client={experimentalClient('n', { sessionToken: '' })} />);
  await screen.findByText('NOT_CONFIGURED');
  fireEvent.change(screen.getByLabelText('检索方式'), { target: { value: 'HYBRID' } });
  fireEvent.change(screen.getByLabelText('视觉向量查询'), { target: { value: 'healer' } });
  expect((screen.getByRole('button', { name: '查询向量' }) as HTMLButtonElement).disabled).toBe(true);
  await waitFor(() => expect(fetch.mock.calls.every(([url]) => !url.endsWith('/hybrid-query'))).toBe(true));
});
