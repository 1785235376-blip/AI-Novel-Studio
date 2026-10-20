// @vitest-environment jsdom
import { StrictMode } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { PortableProjectsPanel } from './PortableProjectsPanel';
import { experimentalClient } from './api';
const sha = 'a'.repeat(64), secondSha = 'b'.repeat(64);
const row = { id: 'import', version: 8, kind: 'IMPORT', status: 'RESTORED', snapshot_digest: 'c'.repeat(64), title: '两正式图片', target_id: 'portable-target',
  image_reference: { type: 'REFERENCES', source: 'a0001', target: 'a0002', selection_digest: 'd'.repeat(64) }, reference_state: 'PENDING',
  id_map: { chapters: { c0001: 'new-chapter' }, media: { a0001: 'new-source', a0002: 'new-target' } },
  media: [{ ref: 'a0001', state: 'AVAILABLE', sha256: sha }, { ref: 'a0002', state: 'AVAILABLE', sha256: secondSha }] };
const review = { target_id: row.target_id, incarnation: 'file:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', type: 'REFERENCES', preview_digest: 'e'.repeat(64),
  semantics: 'NEW_AUTHOR_DECLARATION_NOT_DERIVATION_APPROVAL_OR_EXECUTION', source: { ref: 'a0001', id: 'new-source', version: 2, sha256: sha },
  target: { ref: 'a0002', id: 'new-target', version: 2, sha256: secondSha } };
const reviewed = { ...row, version: 9, reference_state: 'PREVIEW', reference_review: review };
const receipt = { ...row, version: 11, reference_state: 'RESTORED', reference_receipt: { relationship_id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', type: 'REFERENCES', source_id: 'new-source', source_version: 3, target_id: 'new-target' } };
const catalog = { chapters: [{ id: 'chapter', title: '两图片正文', version: 1 }], missing: [], restore_available: true, limitations: [], image_references: [{ id: 'relation', source_id: 'old-source', target_id: 'old-target', selection_digest: 'd'.repeat(64) }] };
const storage = { categories: [], eligible: [], preview_digest: 'f'.repeat(64) };
const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const client = (id = 'source-project') => experimentalClient(id, { sessionToken: 'synthetic-host' });
function fixture(mutation: (url: string, init: RequestInit) => Response | Promise<Response> = url => reply(url.endsWith('reference-confirm') ? receipt : reviewed), stored = row) {
  let current = stored;
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (init.method !== 'GET') return mutation(url, init);
    if (url.endsWith('/catalog')) return reply(catalog);
    if (url.endsWith('/storage')) return reply(storage);
    return reply({ items: [current] });
  });
  vi.stubGlobal('fetch', fetch);
  return { fetch, saved: (value: typeof row) => { current = value; } };
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
const previewButton = () => screen.getByRole('button', { name: '仅预览两图片新身份与参考关系' });
const confirmButton = () => screen.getByRole('button', { name: '确认添加这一条 REFERENCES' }) as HTMLButtonElement;
const consent = () => screen.getByLabelText('已核对两图片新身份、版本和摘要，确认添加这一条 REFERENCES 作者声明');

it('StrictMode only reads; exact mapping preview never adds a relation until separate consent', async () => {
  const f = fixture((url) => { if (url.endsWith('reference-confirm')) { f.saved(receipt); return reply(receipt); } return reply(reviewed); });
  render(<StrictMode><PortableProjectsPanel client={client()} /></StrictMode>);
  await screen.findByText('关系状态：PENDING'); expect(f.fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  fireEvent.click(previewButton()); await screen.findByLabelText('新关系来源图片');
  expect((screen.getByLabelText('来源图片 SHA-256') as HTMLInputElement).value).toBe(sha);
  expect(confirmButton().disabled).toBe(true); expect(f.fetch.mock.calls.filter(([url]) => url.endsWith('reference-confirm'))).toHaveLength(0);
  fireEvent.click(consent()); fireEvent.click(confirmButton()); fireEvent.click(confirmButton());
  await screen.findByText(/参考关系已保存/);
  const confirms = f.fetch.mock.calls.filter(([url]) => url.endsWith('reference-confirm')); expect(confirms).toHaveLength(1);
  expect(JSON.parse(String(confirms[0][1].body))).toEqual({ expected_version: 9, snapshot_digest: row.snapshot_digest, preview_digest: review.preview_digest, confirmed: true });
  expect(confirms[0][1].headers).toMatchObject({ 'X-Session-Token': 'synthetic-host' });
});

it.each(['target-project', 'asset-map', 'hash', 'wrong-kind', 'duplicate'])('rejects forged %s preview without enabling confirmation', async mode => {
  const changed = structuredClone(reviewed);
  if (mode === 'target-project') changed.target_id = 'foreign';
  if (mode === 'asset-map') { changed.id_map.media.a0001 = 'foreign-asset'; changed.reference_review.source.id = 'foreign-asset'; }
  if (mode === 'hash') changed.reference_review.source.sha256 = '0'.repeat(64);
  if (mode === 'wrong-kind') changed.reference_review.type = 'APPROVED_FOR';
  if (mode === 'duplicate') changed.reference_review.source.id = changed.reference_review.target.id;
  const f = fixture(() => reply(changed)); render(<PortableProjectsPanel client={client()} />);
  await screen.findByText('关系状态：PENDING'); fireEvent.click(previewButton()); await screen.findByText(/关系预览响应无法核实/);
  expect(screen.queryByRole('button', { name: '确认添加这一条 REFERENCES' })).toBeNull();
  expect(f.fetch.mock.calls.filter(([url]) => url.endsWith('reference-confirm'))).toHaveLength(0);
});

it('lost confirmation stays locked, refresh with UNKNOWN never resends', async () => {
  const f = fixture(url => { if (url.endsWith('reference-confirm')) { f.saved({ ...row, version: 10, reference_state: 'UNKNOWN' }); return Promise.reject(new TypeError('synthetic lost response')); } return reply(reviewed); });
  render(<PortableProjectsPanel client={client()} />); await screen.findByText('关系状态：PENDING');
  fireEvent.click(previewButton()); await screen.findByLabelText('新关系来源图片'); fireEvent.click(consent()); fireEvent.click(confirmButton());
  await screen.findByText(/关系写入结果未确认，禁止重发/); expect(confirmButton().disabled).toBe(true);
  fireEvent.click(confirmButton()); fireEvent.click(screen.getByRole('button', { name: '刷新便携与存储状态' }));
  await screen.findByText('关系状态：UNKNOWN'); expect((previewButton() as HTMLButtonElement).disabled).toBe(true);
  expect(f.fetch.mock.calls.filter(([url]) => url.endsWith('reference-confirm'))).toHaveLength(1);
});

it('scope change retires late preview and consent without auto mutation', async () => {
  let resolve!: (response: Response) => void;
  const f = fixture(() => new Promise<Response>(done => { resolve = done; }));
  const view = render(<PortableProjectsPanel client={client()} />); await screen.findByText('关系状态：PENDING'); fireEvent.click(previewButton());
  const other = client('other-project'); view.rerender(<PortableProjectsPanel client={other} />);
  resolve(reply(reviewed)); await screen.findByText('关系状态：PENDING'); await Promise.resolve();
  expect(screen.queryByLabelText('新关系来源图片')).toBeNull(); expect(f.fetch.mock.calls.filter(([url]) => url.endsWith('reference-confirm'))).toHaveLength(0);
});

it('relation export is explicit and the default request retains legacy bytes/fields', async () => {
  const f = fixture(() => reply(row)); render(<PortableProjectsPanel client={client()} />); await screen.findByLabelText('两图片正文 · v1');
  fireEvent.click(screen.getByLabelText('两图片正文 · v1'));
  fireEvent.click(screen.getByRole('button', { name: '创建所选章节便携包' })); await waitFor(() => expect(f.fetch.mock.calls.some(([url]) => url.endsWith('/export'))).toBe(true));
  expect(JSON.parse(String(f.fetch.mock.calls.find(([url]) => url.endsWith('/export'))![1].body))).toEqual({ chapter_ids: ['chapter'] });
  await screen.findByText(/已生成带摘要校验的便携包/);
  fireEvent.change(screen.getByLabelText('可选：两正式图片的当前参考关系'), { target: { value: 'relation' } });
  fireEvent.click(screen.getByRole('button', { name: '创建所选章节便携包' }));
  await waitFor(() => expect(f.fetch.mock.calls.filter(([url]) => url.endsWith('/export'))).toHaveLength(2));
  expect(JSON.parse(String(f.fetch.mock.calls.filter(([url]) => url.endsWith('/export'))[1][1].body))).toEqual({ chapter_ids: ['chapter'], image_reference_id: 'relation' });
});
