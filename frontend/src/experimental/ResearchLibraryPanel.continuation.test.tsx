// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ResearchLibraryPanel } from './ResearchLibraryPanel';
import { experimentalClient } from './api';
const source = { id: 'source', version: 2, status: 'ACTIVE', title: 'Synthetic source', author: '', source: '', source_version: '', usage_notes: '', access: 'PROJECT', format: 'TXT', origin: 'LOCAL_IMPORT', filename: 'source.txt', accessed_at: '2026-10-06', extraction_status: 'TEXT_EXTRACTED', paragraph_count: 1, warnings: [], paragraphs: [], content_sha256: 'a'.repeat(64) };
const ref = { source_id: 'source', source_version: 2, paragraph: 1, quote_sha256: 'a'.repeat(64) };
const note = { id: 'note', version: 4, title: 'My note', text: 'Original note text', citations: [ref], evidence: [] };
const reply = (v: unknown, status = 200) => new Response(JSON.stringify(v), { status });
function setup() {
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (init.method !== 'GET') return reply({ ...source, version: 3 });
    if (url.endsWith('/sources/source/history')) return reply({ items: [{ ...source, version: 1 }, source], current_version: 2 });
    if (url.endsWith('/sources/source')) return reply(source);
    if (url.endsWith('/sources')) return reply({ items: [source] });
    if (url.endsWith('/notes')) return reply({ items: [note] });
    return reply({ items: [] });
  });
  vi.stubGlobal('fetch', fetch); render(<ResearchLibraryPanel client={experimentalClient('novel', { sessionToken: 'token' })} />); return fetch;
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('replaces original file bytes against the selected source version', async () => {
  const fetch = setup();
  fireEvent.click(await screen.findByRole('button', { name: '打开来源 Synthetic source' }));
  fireEvent.click(await screen.findByRole('button', { name: '编辑来源元数据' }));
  fireEvent.change(screen.getByLabelText('选择本地资料文件'), { target: { files: [new File(['replacement'], 'new.txt', { type: 'text/plain' })] } });
  fireEvent.click(screen.getByRole('button', { name: '保存资料新文件版本' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url, init]) => url.endsWith('/sources/source/file') && init.method === 'PUT')).toBe(true));
  const sent = JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/sources/source/file'))![1].body));
  expect(sent).toMatchObject({ filename: 'new.txt', content_base64: 'cmVwbGFjZW1lbnQ=', expected_version: 2 });
});

it('requires explicit review to restore a historical source as a new private version', async () => {
  const fetch = setup();
  fireEvent.click(await screen.findByRole('button', { name: '打开来源 Synthetic source' }));
  fireEvent.click(await screen.findByRole('button', { name: '核对来源历史版本' }));
  const restore = await screen.findByRole('button', { name: '恢复来源版本 1' }) as HTMLButtonElement;
  expect(restore.disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('已核对版本，恢复为新的私有来源版本并使旧引用失效'));
  fireEvent.click(restore);
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/source/restore'))).toBe(true));
  expect(JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/source/restore'))![1].body))).toEqual({ expected_version: 2, restore_version: 1 });
});

it('edits a cited note with exact revision and supports abandoning unsent edits', async () => {
  const fetch = setup();
  fireEvent.click(await screen.findByRole('button', { name: '编辑研究笔记 My note' }));
  fireEvent.change(screen.getByLabelText('研究笔记内容'), { target: { value: 'Revised original note' } });
  fireEvent.click(screen.getByRole('button', { name: '保存研究笔记新版本' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url, init]) => url.endsWith('/notes/note') && init.method === 'PUT')).toBe(true));
  expect(JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/notes/note'))![1].body))).toMatchObject({ expected_version: 4, text: 'Revised original note', citations: [ref] });
});
