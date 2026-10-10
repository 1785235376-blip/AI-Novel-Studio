// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { creativeClient, type CreativeClient } from './client';
import { ScreenplayPresetPanel } from './ScreenplayPresetPanel';
import { CreativeWorkspace, type CreativeWorkspaceProps } from './CreativeWorkspace';
import { instantiateScreenplayPreset, parseScreenplayPresets, SCREENPLAY_PRESET_IDS } from './screenplayPresets';
import { newDocument, newScene, type CreativeDocument } from './types';
const catalog = () => ({ schema_version: 1, templates: SCREENPLAY_PRESET_IDS.map((id, i) => ({ id, version: 1, title: `Guide ${i}`, description: 'Synthetic writing guide', document: { ...newDocument('SCREENPLAY'), title: `Guide ${i}`, source_independent: true, script: null, scenes: [{ ...newScene(1), id: `prototype-${i}`, action: 'Replace this synthetic writing prompt.' }] } })) });
const response = (body: unknown, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => body });
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it('parses detached guides and creates distinct independent local drafts only on explicit use', () => {
  const raw = catalog(), parsed = parseScreenplayPresets(raw), one = instantiateScreenplayPreset(parsed.templates[0]), two = instantiateScreenplayPreset(parsed.templates[0]);
  expect(one).toMatchObject({ mode: 'SCREENPLAY', source_independent: true, source_chapter_ids: [], director_notes: [], shots: [], video_plan: null });
  expect(one.scenes[0].id).not.toBe('prototype-0'); expect(one.scenes[0].id).not.toBe(two.scenes[0].id);
  one.scenes[0].action = 'My own scene'; parsed.templates[0].document.scenes[0].action = 'Changed detached catalog';
  expect(raw.templates[0].document.scenes[0].action).toBe('Replace this synthetic writing prompt.');
  expect(two.scenes[0].action).toBe('Replace this synthetic writing prompt.');
});
it.each(['schema','version','order','source','independent','scene_source','sequence','director','extra','mode','empty','script'])('rejects incompatible or source-bearing guide %s', kind => {
  const raw = catalog(); const p = raw.templates[0], d = p.document;
  if (kind === 'schema') raw.schema_version = 2;
  if (kind === 'version') p.version = 2;
  if (kind === 'order') raw.templates.reverse();
  if (kind === 'source') d.source_chapter_ids = ['private-chapter'];
  if (kind === 'independent') d.source_independent = false;
  if (kind === 'scene_source') d.scenes[0].source_chapter_id = 'private-chapter';
  if (kind === 'sequence') d.scenes[0].sequence = 2;
  if (kind === 'director') (d.director_notes as unknown[]).push({ secret: 'private-note' });
  if (kind === 'extra') Object.assign(p, { private_prompt: 'must not be adopted' });
  if (kind === 'mode') d.mode = 'SCRIPT';
  if (kind === 'empty') d.scenes = [];
  if (kind === 'script') Object.assign(d, { script: { purpose: 'CUSTOM', body: 'foreign' } });
  expect(() => parseScreenplayPresets(raw)).toThrow(/目录/);
});
it('uses the original captured session and branch for a read-only catalog request', async () => {
  const fetch = vi.fn(async () => response(catalog())); vi.stubGlobal('fetch', fetch);
  const client = creativeClient('project', { sessionToken: 'captured', scope: { workspaceId: 'w', projectId: 'p', storylineId: 's', branchId: 'branch' } });
  const signal = new AbortController().signal; await client.screenplayPresets(signal);
  expect(fetch).toHaveBeenCalledWith('/api/novels/project/experimental/creative/screenplay-presets', expect.objectContaining({ method: 'GET', signal, headers: expect.objectContaining({ 'X-Session-Token': 'captured', 'X-Branch-Id': 'branch' }) }));
  expect(fetch.mock.calls).toHaveLength(1);
});
it('loads only on opening, shows guide content and never performs a persistence request', async () => {
  const read = vi.fn(async () => parseScreenplayPresets(catalog())), onUse = vi.fn();
  render(<ScreenplayPresetPanel client={{ screenplayPresets: read } as unknown as CreativeClient} available onUse={onUse} onDenied={vi.fn()} />);
  expect(read).not.toHaveBeenCalled(); fireEvent.click(screen.getByRole('button', { name: '浏览起稿模板' }));
  await screen.findByLabelText('起稿类型'); expect(onUse).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText('起稿类型'), { target: { value: 'ANIMATION' } });
  fireEvent.click(screen.getByRole('button', { name: '从模板新建未保存剧本' }));
  expect(onUse).toHaveBeenCalledWith(expect.objectContaining({ id: 'ANIMATION' })); expect(read).toHaveBeenCalledOnce();
});
it('aborts a closed catalog and ignores its late response before a new read', async () => {
  let resolve!: (value: ReturnType<typeof parseScreenplayPresets>) => void;
  const read = vi.fn(() => new Promise<ReturnType<typeof parseScreenplayPresets>>(done => { resolve = done; }));
  render(<ScreenplayPresetPanel client={{ screenplayPresets: read } as unknown as CreativeClient} available onUse={vi.fn()} onDenied={vi.fn()} />);
  fireEvent.click(screen.getByRole('button', { name: '浏览起稿模板' })); fireEvent.click(screen.getByRole('button', { name: '收起起稿模板' }));
  await act(async () => resolve(parseScreenplayPresets(catalog())));
  expect((read.mock.calls[0] as unknown as [AbortSignal])[0].aborted).toBe(true); expect(screen.queryByLabelText('起稿类型')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '浏览起稿模板' })); expect(read).toHaveBeenCalledTimes(2);
});
it('gates dirty/read-only use and reports revoked catalog authority to the original owner', async () => {
  const onDenied = vi.fn(), read = vi.fn(async () => parseScreenplayPresets(catalog())), p = { client: { screenplayPresets: read } as unknown as CreativeClient, available: false, onUse: vi.fn(), onDenied };
  const view = render(<ScreenplayPresetPanel {...p} />); fireEvent.click(screen.getByRole('button', { name: '浏览起稿模板' }));
  expect((await screen.findByRole('button', { name: '从模板新建未保存剧本' })).hasAttribute('disabled')).toBe(true);
  view.unmount(); read.mockRejectedValueOnce(new ApiError({ status: 403, code: 'REVOKED', message: 'denied' }));
  render(<ScreenplayPresetPanel {...p} />); fireEvent.click(screen.getByRole('button', { name: '浏览起稿模板' }));
  await waitFor(() => expect(onDenied).toHaveBeenCalledOnce()); expect(p.onUse).not.toHaveBeenCalled();
});
function workspaceProps(): CreativeWorkspaceProps {
  return { enabled: true, novelId: 'p', context: { sessionToken: 'owner' }, scope: { workspace: 'w', project: 'p', storyline: 's', branch: 'b' }, actor: 'Author', chapterCount: 0, manuscriptReady: false, novelMain: <div>Original manuscript</div>, novelSidebar: <div>Chapters</div>, novelInspector: <div>Inspector</div>, novelStatus: <span>Saved manuscript</span>, onExit: vi.fn(), onModuleChange: vi.fn() };
}
it('creates a fresh unsaved draft once, preserves the saved document and uses original POST then versioned PUT', async () => {
  const old = { ...newDocument('SCREENPLAY'), id: 'saved-original', title: 'Original saved', version: 7, status: 'DRAFT', source_independent: true, source_evidence: {}, scenes: [newScene(1)] } as CreativeDocument;
  const writes: { method: string; body: Record<string, unknown> }[] = [];
  const fetch = vi.fn(async (url: string, init: RequestInit = {}) => {
    if (url.endsWith('/capabilities')) return response({ enabled: true, can_mutate: true, modes: ['SCREENPLAY'] });
    if (url.endsWith('/documents') && init.method === 'GET') return response({ items: [old] });
    if (url.endsWith('/screenplay-presets')) return response(catalog());
    if (url.endsWith('/creation-reference-data')) return response({ characters: [], locations: [], story_routes: [] });
    if (url.endsWith('/assets')) return response([]);
    if (url.endsWith('/director-proposals') || url.endsWith('/model-routes')) return response({ items: [] });
    if (url.endsWith('/local-ai/environment')) return response({ code: 'UNAVAILABLE' }, 404);
    if (init.method === 'POST' || init.method === 'PUT') { const body = JSON.parse(String(init.body)); writes.push({ method: init.method, body }); return response({ ...old, ...body, id: 'new-starter', version: writes.length }); }
    throw new Error('unexpected request');
  });
  vi.stubGlobal('fetch', fetch); render(<CreativeWorkspace {...workspaceProps()} />);
  await waitFor(() => expect(screen.queryByText('正在核对创作文档与权限…')).toBeNull());
  fireEvent.click(within(screen.getByRole('tablist', { name: '创作模式' })).getByRole('tab', { name: /Screenplay/ }));
  await screen.findByDisplayValue('Original saved'); fireEvent.click(screen.getByRole('button', { name: '浏览起稿模板' }));
  const use = await screen.findByRole('button', { name: '从模板新建未保存剧本' }); fireEvent.click(use); fireEvent.click(use);
  expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe('Guide 0'); expect(writes).toEqual([]);
  expect(old.title).toBe('Original saved'); expect(screen.queryByText('已保存 · v7')).toBeNull();
  expect(screen.getByRole('button', { name: '从模板新建未保存剧本' }).hasAttribute('disabled')).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '保存草稿' })); await screen.findByText('已保存“Guide 0” · v1');
  expect(writes).toHaveLength(1); expect(writes[0].method).toBe('POST'); expect(writes[0].body.source_chapter_ids).toEqual([]);
  const scenes = writes[0].body.scenes as { id: string; source_chapter_id: null }[]; expect(scenes[0].id).not.toBe('prototype-0'); expect(scenes[0].source_chapter_id).toBeNull();
  fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'My edited screenplay' } }); fireEvent.click(screen.getByRole('button', { name: '保存草稿' }));
  await screen.findByText('已保存“My edited screenplay” · v2'); expect(writes[1]).toMatchObject({ method: 'PUT', body: { expected_version: 1 } });
});
