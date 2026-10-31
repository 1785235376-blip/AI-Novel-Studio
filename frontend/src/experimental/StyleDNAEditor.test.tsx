// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useState } from 'react';
import { StyleDNAEditor } from './StyleDNAEditor';
import { StyleAnalysisPanel } from './StyleAnalysisPanel';
import { ApiError } from '../api';
import { styleReviewClient, type StyleCatalog, type StyleProfile, type StyleResolution } from './styleReviewClient';
const digest = 'a'.repeat(64), pinDigest = 'b'.repeat(64);
const profile = (id = 's1'): StyleProfile => ({ id, version: 1, title: id, instructions: 'Human authored', rules: [], chapter_ids: [], character_ids: [], status: 'APPROVED', style_dna: { schema_version: 1, global_rules: { color: 'Amber' }, overrides: [] }, style_dna_resolution: { stale: false, source_digest: digest, execution_adoption: 'UNSUPPORTED' } });
const catalog = (styles = [profile()]): StyleCatalog => ({ styles, chapters: [{ id: 'c1', title: 'Chapter One', version: 3, content_digest: pinDigest }], characters: [], operations: ['continue'] });
const resolution: StyleResolution = { style_source: { id: 's1', version: 1, digest }, target: { level: 'GLOBAL' }, effective: { color: { value: 'RESULT_AMBER', level: 'GLOBAL', source: {} } }, contributors: [], conflicts: [], uncovered_dimensions: ['sound'], coverage: 'PARTIAL_AUTHORED_RULES_ONLY', semantic_conflicts_verified: false, execution_ready: false, model_called: false, target_mutated: false, limitations: [] };
const raw = () => ({ get: vi.fn(), post: vi.fn(), put: vi.fn(), blob: vi.fn() });
const pick = (id = 's1') => fireEvent.change(screen.getByLabelText('Style DNA 档案'), { target: { value: id } });
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
it('saves original STYLE payload with exact chapter pin, reopens, approves and resolves canonical digest', async () => {
  const client = raw(); let rows: StyleProfile[] = []; let revision = 0;
  client.post.mockImplementation(async (path, body) => {
    if (path.endsWith('/resolve')) return resolution;
    if (path.endsWith('/approve')) { rows = [{ ...rows[0], status: 'APPROVED', version: ++revision }]; return rows[0]; }
    rows = [{ ...body, id: 's1', version: ++revision, status: 'DRAFT', style_dna_resolution: { stale: false, source_digest: digest, execution_adoption: 'UNSUPPORTED' } }]; return rows[0];
  });
  const api = styleReviewClient(client);
  function Host() { const [data, setData] = useState(catalog([])); return <StyleDNAEditor api={api} catalog={data} available onRefresh={() => setData(catalog(rows))} />; }
  render(<Host />); expect(client.post).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText('Style DNA 标题'), { target: { value: 'New style' } }); fireEvent.change(screen.getByLabelText('Style DNA 简短说明'), { target: { value: 'Human rules' } }); fireEvent.change(screen.getByLabelText('全局 · 色彩'), { target: { value: 'Amber' } });
  fireEvent.change(screen.getByLabelText('精确章节覆盖'), { target: { value: 'c1' } }); fireEvent.change(screen.getByLabelText('章节覆盖 · 色彩'), { target: { value: 'Blue' } });
  fireEvent.click(button('保存 Style DNA 草稿')); await waitFor(() => expect(client.post).toHaveBeenCalledTimes(1));
  expect(client.post.mock.calls[0][1].style_dna.overrides[0].target).toEqual({ level: 'CHAPTER', chapter: { id: 'c1', version: 3, digest: pinDigest } });
  pick(); expect((screen.getByLabelText('章节覆盖 · 色彩') as HTMLTextAreaElement).value).toBe('Blue');
  fireEvent.click(button('审核当前 Style DNA 版本')); await waitFor(() => expect(client.post).toHaveBeenCalledTimes(2)); pick();
  fireEvent.change(screen.getByLabelText('只读解析目标'), { target: { value: 'c1' } }); fireEvent.click(button('解析当前已审核风格')); await screen.findByText(/RESULT_AMBER/);
  expect(client.post.mock.calls[2][1]).toEqual({ expected_version: 2, expected_digest: digest, target: { level: 'CHAPTER', chapter: { id: 'c1', version: 3, digest: pinDigest } } });
  expect(client.post.mock.calls.some(([path]) => /analyses|preview|dispatch/.test(path))).toBe(false);
});
it('keeps dirty edits on cancelled navigation and warns before unload', () => {
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false); const api = styleReviewClient(raw()); render(<StyleDNAEditor api={api} catalog={catalog()} available onRefresh={vi.fn()} />); pick();
  fireEvent.change(screen.getByLabelText('全局 · 色彩'), { target: { value: 'Unsaved' } }); pick(''); expect(confirm).toHaveBeenCalledOnce(); expect((screen.getByLabelText('全局 · 色彩') as HTMLTextAreaElement).value).toBe('Unsaved');
  const event = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(event); expect(event.defaultPrevented).toBe(true);
  confirm.mockReturnValue(true); fireEvent.click(button('取消修改并重新打开')); expect((screen.getByLabelText('全局 · 色彩') as HTMLTextAreaElement).value).toBe('Amber');
});
it('suppresses delayed resolution across selection ABA and owner replacement', async () => {
  let finish!: (value: StyleResolution) => void; const client = raw(); client.post.mockImplementation(() => new Promise(resolve => { finish = resolve; })); const api = styleReviewClient(client); const data = catalog([profile(), profile('s2')]);
  const view = render(<StyleDNAEditor api={api} catalog={data} available onRefresh={vi.fn()} />); pick(); fireEvent.click(button('解析当前已审核风格'));
  // Even a retained selection handler moving away and back cannot revive the old request.
  pick('s2'); pick('s1');
  // A refresh changing source availability independently invalidates the request.
  view.rerender(<StyleDNAEditor api={api} catalog={data} available={false} onRefresh={vi.fn()} />); view.rerender(<StyleDNAEditor api={api} catalog={data} available onRefresh={vi.fn()} />);
  await act(async () => finish(resolution)); expect(screen.queryByText(/RESULT_AMBER/)).toBeNull();
  fireEvent.click(button('解析当前已审核风格')); view.rerender(<StyleDNAEditor api={styleReviewClient(raw())} catalog={data} available onRefresh={vi.fn()} />); await act(async () => finish(resolution)); expect(screen.queryByText(/RESULT_AMBER/)).toBeNull(); expect((screen.getByLabelText('Style DNA 档案') as HTMLSelectElement).value).toBe('');
});
it('quarantines removed or forbidden rows immediately and never resurrects drafts', async () => {
  const api = styleReviewClient(raw()); const view = render(<StyleDNAEditor api={api} catalog={catalog()} available onRefresh={vi.fn()} />); pick();
  fireEvent.change(screen.getByLabelText('全局 · 色彩'), { target: { value: 'PRIVATE_CANARY' } }); view.rerender(<StyleDNAEditor api={api} catalog={catalog([])} available onRefresh={vi.fn()} />); expect(screen.queryByDisplayValue('PRIVATE_CANARY')).toBeNull();
  view.rerender(<StyleDNAEditor api={api} catalog={catalog()} available onRefresh={vi.fn()} />); expect(screen.queryByLabelText('全局 · 色彩')).toBeNull(); fireEvent.click(button('重新打开当前档案')); expect((screen.getByLabelText('全局 · 色彩') as HTMLTextAreaElement).value).toBe('Amber');
});
it('preserves draft on CAS failure; denies stale resolution and unsupported hierarchy edits', async () => {
  const client = raw(); client.put.mockRejectedValue(new ApiError({ status: 409, code: 'VERSION_CONFLICT', message: 'Conflict' })); const api = styleReviewClient(client); const view = render(<StyleDNAEditor api={api} catalog={catalog()} available onRefresh={vi.fn()} />); pick();
  fireEvent.change(screen.getByLabelText('全局 · 色彩'), { target: { value: 'New color' } }); fireEvent.click(button('保存 Style DNA 新草稿版本')); await screen.findByText(/VERSION_CONFLICT/); expect(client.put.mock.calls[0][1].expected_version).toBe(1); expect((screen.getByLabelText('全局 · 色彩') as HTMLTextAreaElement).value).toBe('New color');
  const stale = { ...profile(), style_dna_resolution: { ...profile().style_dna_resolution!, stale: true } }; view.rerender(<StyleDNAEditor api={api} catalog={catalog([stale])} available onRefresh={vi.fn()} />); expect(button('解析当前已审核风格').disabled).toBe(true);
});
it('legacy panel excludes bound styles from legacy analysis/edit/execution routes', async () => {
  const client = raw(); client.get.mockImplementation(async path => path.endsWith('/catalog') ? catalog() : { items: [] }); render(<StyleAnalysisPanel client={client} />); await screen.findByRole('option', { name: /s1 · v1/ });
  expect(screen.queryByRole('button', { name: '编辑风格 s1' })).toBeNull(); expect(button('A02 分析不可用').disabled).toBe(true); expect(button('执行采用不可用').disabled).toBe(true); expect(client.post).not.toHaveBeenCalled();
});

it('denies source-drift results and locks unsupported scene overrides without losing their rules', async () => {
  let finish!: (value: StyleResolution) => void; const client = raw(); client.post.mockImplementation(() => new Promise(resolve => { finish = resolve; })); const api = styleReviewClient(client); const data = catalog();
  const view = render(<StyleDNAEditor api={api} catalog={data} available onRefresh={vi.fn()} />); pick(); fireEvent.click(button('解析当前已审核风格'));
  view.rerender(<StyleDNAEditor api={api} catalog={{ ...data, chapters: [{ ...data.chapters[0], version: 4, content_digest: 'c'.repeat(64) }] }} available onRefresh={vi.fn()} />);
  await act(async () => finish(resolution)); expect(screen.queryByText(/RESULT_AMBER/)).toBeNull();
  const advanced = profile(); advanced.style_dna!.overrides = [{ target: { level: 'SCENE', document: { id: 'doc', version: 2, digest }, scene_id: 'scene' }, rules: { sound: 'Keep original' } }];
  view.rerender(<StyleDNAEditor api={api} catalog={catalog([advanced])} available onRefresh={vi.fn()} />); pick(); expect(screen.queryByLabelText('Style DNA 标题')).toBeNull(); expect(screen.getByText(/Keep original/)).toBeTruthy(); expect(screen.queryByRole('button', { name: '保存 Style DNA 新草稿版本' })).toBeNull();
});
it('quarantines a forbidden save response without keeping private field values', async () => {
  const client = raw(); client.put.mockRejectedValue(new ApiError({ status: 403, code: 'FORBIDDEN', message: 'Denied' })); const api = styleReviewClient(client);
  render(<StyleDNAEditor api={api} catalog={catalog()} available onRefresh={vi.fn()} />); pick(); fireEvent.change(screen.getByLabelText('全局 · 色彩'), { target: { value: 'PRIVATE_SAVE' } }); fireEvent.click(button('保存 Style DNA 新草稿版本')); await screen.findByText(/FORBIDDEN/); expect(screen.queryByDisplayValue('PRIVATE_SAVE')).toBeNull();
});

it('keeps captured unsupported hierarchy locked across editable server-shape drift until reopen', () => {
  const advanced = profile(); advanced.style_dna!.overrides = [{ target: { level: 'SHOT', document: { id: 'doc', version: 2, digest }, scene_id: 'scene', shot_id: 'shot' }, rules: { sound: 'Original shot rule' } }];
  const api = styleReviewClient(raw()); const view = render(<StyleDNAEditor api={api} catalog={catalog([advanced])} available onRefresh={vi.fn()} />); pick();
  view.rerender(<StyleDNAEditor api={api} catalog={catalog([{ ...profile(), version: 2 }])} available onRefresh={vi.fn()} />);
  expect(screen.queryByLabelText('Style DNA 标题')).toBeNull(); expect(screen.getByText(/Original shot rule/)).toBeTruthy(); pick(); expect(screen.getByLabelText('Style DNA 标题')).toBeTruthy();
});
it('hides but preserves unsaved edits across transient catalog failure', () => {
  const api = styleReviewClient(raw()); const data = catalog(); const view = render(<StyleDNAEditor api={api} catalog={data} available onRefresh={vi.fn()} />); pick();
  fireEvent.change(screen.getByLabelText('全局 · 色彩'), { target: { value: 'KEEP_MY_DRAFT' } });
  view.rerender(<StyleDNAEditor api={api} catalog={data} available={false} error={new Error('network')} onRefresh={vi.fn()} />); expect(screen.queryByDisplayValue('KEEP_MY_DRAFT')).toBeNull();
  view.rerender(<StyleDNAEditor api={api} catalog={data} available onRefresh={vi.fn()} />); expect((screen.getByLabelText('全局 · 色彩') as HTMLTextAreaElement).value).toBe('KEEP_MY_DRAFT');
});
