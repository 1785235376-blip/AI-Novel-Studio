// @vitest-environment jsdom
// Extracted additions and migrated variants; protected baseline suite stays byte-identical.
// Migrated variants preserve newer assertions and are not counted as unique new capabilities.

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ResearchLibraryPanel } from './ResearchLibraryPanel';
import { experimentalClient } from './api';

const ref = { source_id: 'source', source_version: 1, paragraph: 1, quote_sha256: 'a'.repeat(64) };
const source = { id: 'source', version: 1, title: '潮汐参考', author: '合成作者', source: '合成来源', source_version: '第一版', usage_notes: '写作参考', access: 'PRIVATE', format: 'TXT', origin: 'LOCAL_IMPORT', filename: 'tide.txt', accessed_at: '2026-10-05', extraction_status: 'TEXT_EXTRACTED', paragraph_count: 1, warnings: [], paragraphs: [{ paragraph: 1, page: null, text: '暮色中的港口关闭潮门。', citation: ref }] };
const evidence = { citation: ref, title: source.title, text: source.paragraphs[0].text, paragraph: 1, page: null, source: source.source, author: source.author };
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const client = (id = 'novel') => experimentalClient(id, { sessionToken: 'trusted-session' });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('locates page-only evidence in the original source without claiming extracted text', async () => {
  const pageRef = { ...ref, paragraph: 0, page: 2 };
  const image = { ...source, format: 'IMAGE', paragraphs: [], paragraph_count: 0, page_citations: [pageRef] };
  vi.stubGlobal('fetch', vi.fn(async (url: string) => reply(url.endsWith('/sources/source') ? image : url.endsWith('/sources') ? { items: [image] } : url.endsWith('/citation') ? { ...evidence, citation: pageRef, paragraph: 0, page: 2, text: '', not_understood: true } : { items: [] })));
  render(<ResearchLibraryPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: '打开来源 潮汐参考' }));
  fireEvent.click(await screen.findByRole('button', { name: '核对页面引用 2' }));
  fireEvent.click(await screen.findByRole('button', { name: '在原来源中定位此引用' }));
  const located = await screen.findByRole('region', { name: '已定位的原始页面引用' });
  await waitFor(() => expect(document.activeElement).toBe(located));
  expect(screen.getByText(/未解析页面引用；没有原文理解证明/)).toBeTruthy();
  expect(screen.getByText('已选择 0 段引用。')).toBeTruthy();
});

it('scopes unavailable analysis to this literal-search entry without denying the separate embedding panel', async () => {
  const fetch = vi.fn(async (_url: string, _options: RequestInit) => reply({ items: [], total: 0, adapters: { vector: 'NOT_CONFIGURED', ocr: 'NOT_CONFIGURED', vision: 'NOT_CONFIGURED' } }));
  vi.stubGlobal('fetch', fetch); render(<ResearchLibraryPanel client={client()} />);
  await screen.findByText(/本入口的向量、OCR 与视觉解析当前未配置/);
  expect(screen.getByText(/Embedding \/ Hybrid Search 在独立面板配置/)).toBeTruthy();
  expect(fetch.mock.calls.every(([, options]) => options?.method === 'GET')).toBe(true);
});
