// @vitest-environment jsdom
// Mounted original owners with controlled HTTP responses. This is not browser E2E
// or a persistence/provider test; no child, client, or controller is replaced.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useStudio } from '../store';
import { useLocalHostSession } from '../localHostSession';
import { IndependentStudioWorkspace, type IndependentStudioProps } from './IndependentStudioWorkspace';
import { blankGraph } from './graphDraft';
import { modelCatalog } from './studioGraphModel.testFixtures';
import type { StudioGraphRecord } from './studioGraphTypes';
import type { StudioOverview } from './studioClient';
import { newDocument, newScene, newShot, type CreativeDocument } from './types';
import emptyPromptLibrary from '../prompt/__fixtures__/empty-library.json';

const project = 'editor-handoff-project', studio = `/api/projects/${project}/studio`;
const creative = `/api/novels/${project}/experimental/creative`;
const sourcePin = { id: 'authored-director', version: 3, digest: 'a'.repeat(64) };
const targetPin = { id: 'chosen-storyboard', version: 7, digest: 'b'.repeat(64) };
const source = (): CreativeDocument => ({ ...newDocument('DIRECTOR'), id: sourcePin.id, version: sourcePin.version,
  title: 'Human director', status: 'DRAFT', source_independent: true, actor_id: 'author', source_evidence: {},
  created_at: '2026-10-17T00:00:00Z', updated_at: '2026-10-17T00:00:00Z',
  scenes: [{ ...newScene(1), id: 'scene-one', heading: 'INT. STATION - DAY', action: 'The traveller waits.' }],
  director_notes: [{ id: 'direction-one', number: 1, scene_id: 'scene-one', note: 'Hold before the turn',
    shot_size: 'MEDIUM', camera_angle: 'EYE_LEVEL', camera_motion: 'STATIC', duration_seconds: 5,
    emotion: 'Anticipation', pacing: 'Slow', performance: 'Look toward the platform', blocking: 'Beside the window' }] });
const board = (): CreativeDocument => ({ ...source(), id: targetPin.id, version: targetPin.version, mode: 'STORYBOARD',
  title: 'Exact selected board', source_documents: { [sourcePin.id]: { version: sourcePin.version, digest: sourcePin.digest } },
  shots: [{ ...newShot(1, 'scene-one'), id: 'shot-one', frame_prompt: 'The traveller beside the station window',
    action: 'Hold before the turn', director_note_ids: ['direction-one'] }] });
const graph = (): StudioGraphRecord => ({ project_id: project, scope: { mode: 'local', novel_id: project },
  id: 'saved-graph', version: 4, can_edit: true, reference_states: [], definition_digest: 'c'.repeat(64), execution_digest: 'c'.repeat(64),
  created_at: '2026-10-17T00:00:00Z', updated_at: '2026-10-17T00:00:00Z',
  definition: { ...blankGraph(), title: 'Saved original graph', nodes: [{ id: 'author-input', definition_id: 'text_input',
    definition_version: 1, enabled: true, position: { x: 0, y: 0 }, parameters: { text: 'Original graph input' } }] } });
const overview: StudioOverview = { project: { id: project, title: 'Handoff project', entry_kind: 'NEUTRAL_STUDIO' },
  preferences: { version: 1, intents: [], preset: 'BLANK', custom_intent: '' },
  capabilities: { can_mutate: true, can_review: true, manual_import: true, manual_export: true, model_required: false,
    chapter_required: false, intent_is_permission: false, media_validator_configured: true, asset_kinds: ['image', 'video', 'audio'] } };
const caps = { enabled: true, can_mutate: true, modes: ['DIRECTOR', 'STORYBOARD'] };
const response = (body: unknown, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => structuredClone(body) });
const exportReceipt = () => ({ document: stored, document_digest: targetPin.digest, format: 'creative-json/1', boundary: 'original-owner' });
type Override = (url: string, init: RequestInit) => unknown;
let fetchMock: ReturnType<typeof vi.fn>, stored: CreativeDocument, savedGraph: StudioGraphRecord;
const unexpected: string[] = [];
function server(override?: Override) {
  fetchMock = vi.fn(async (url: string, init: RequestInit = {}) => {
    const special = override?.(url, init); if (special !== undefined) return await special;
    if (url === studio) return response(overview);
    if (url === `${studio}/prompts`) return response({ ...emptyPromptLibrary, project_id: project, scope: { mode: 'local', novel_id: project } });
    if (url === `${studio}/assets` || url.startsWith(`${studio}/assets?`)) return response({ items: [] });
    if (url === `${studio}/graphs/catalog`) return response(modelCatalog(false));
    if (url === `${studio}/graphs`) return response({ items: [savedGraph] });
    if (url === `${studio}/graphs/${savedGraph.id}`) return response(savedGraph);
    if (url === `${studio}/graphs/${savedGraph.id}/runs`) return response({ items: [] });
    if (url === `${creative}/capabilities`) return response(caps);
    if (url === `${creative}/documents`) return response({ items: [
      { ...board(), id: 'first-listed-board', title: 'Wrong first board', shots: [{ ...newShot(1, 'scene-one'), id: 'wrong-shot', frame_prompt: 'Never auto-select this board' }] },
      source(), stored,
    ] });
    if (url === `${creative}/documents/${sourcePin.id}/export`) return response({ document: source(), document_digest: sourcePin.digest, format: 'creative-json/1', boundary: 'original-owner' });
    if (url === `${creative}/documents/${targetPin.id}/export`) return response(exportReceipt());
    if (url === `${creative}/documents/${targetPin.id}` && init.method === 'PUT') {
      const { expected_version, ...input } = JSON.parse(String(init.body));
      if (expected_version !== stored.version) return response({ code: 'CREATIVE_VERSION_CONFLICT' }, 409);
      stored = { ...stored, ...input, version: stored.version + 1 }; return response(stored);
    }
    if (url === `/api/novels/${project}/creation-reference-data`) return response({ characters: [], locations: [], story_routes: [] });
    if (url === `/api/novels/${project}/assets`) return response([]);
    // These original optional readers may mount with the Director console.
    if (url === `${creative}/director-proposals` || url === `${creative}/director-proposals/model-routes`) return response({ items: [] });
    unexpected.push(`${init.method} ${url}`); throw new Error(`Unexpected request: ${init.method} ${url}`);
  });
  vi.stubGlobal('fetch', fetchMock);
}
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const change = (name: string, value: string) => fireEvent.change(screen.getByLabelText(name), { target: { value } });
const input = (name: string) => screen.getByLabelText(name) as HTMLInputElement;
const writes = () => fetchMock.mock.calls.filter(([, init]) => init.method !== 'GET');
const targetReads = () => fetchMock.mock.calls.filter(([url]) => url === `${creative}/documents/${targetPin.id}/export`);
function mount(module: 'IMAGE' | 'VIDEO' = 'IMAGE') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const props: IndependentStudioProps = { projectId: project, context: { sessionToken: '' },
    scope: { workspace: 'Local', project: 'Handoff project', storyline: 'Default', branch: 'Main' }, actor: 'Author', module,
    onModuleChange: vi.fn(), onProjectChoice: vi.fn() };
  const element = (next: Partial<IndependentStudioProps> = {}) => <QueryClientProvider client={client}><IndependentStudioWorkspace {...props} {...next} /></QueryClientProvider>;
  const view = render(element());
  return { ...view, props, rerenderModule: (next: 'IMAGE' | 'VIDEO') => view.rerender(element({ module: next })) };
}
async function inspect(module: 'IMAGE' | 'VIDEO' = 'IMAGE') {
  const view = mount(module);
  click((await screen.findByRole('button', { name: '创作图' })).textContent!);
  await screen.findByRole('option', { name: /Saved original graph/ });
  change('已保存创作图', savedGraph.id);
  await waitFor(() => expect(input('创作图标题').value).toBe(savedGraph.definition.title));
  click('打开导演总控台');
  await waitFor(() => expect(input('文档标题').closest('fieldset')!.disabled).toBe(false));
  click('读取导演原文档目录'); await screen.findByRole('option', { name: 'Human director · v3' });
  change('总控台原导演文档', sourcePin.id); click('读取所选导演原文档');
  await screen.findByDisplayValue('Human director');
  click('读取关联分镜与状态'); await screen.findByRole('button', { name: '读取分镜 Exact selected board · v7' });
  expect(screen.queryByRole('button', { name: '在原分镜编辑器打开' })).toBeNull();
  click('读取分镜 Exact selected board · v7');
  const receipt = await screen.findByRole('complementary', { name: '分镜原文档状态回传' });
  expect(receipt.textContent).toContain(targetPin.id); expect(receipt.textContent).toContain(targetPin.digest);
  expect(targetReads()).toHaveLength(1); expect(writes()).toEqual([]);
  return view;
}
function confirmDiscard() { fireEvent.click(screen.getByLabelText('确认放弃未保存输入')); click('确认离开'); }
function expectGraphPreserved(title = 'Unsaved graph input') {
  expect(input('创作图标题').value).toBe(title);
  expect(input('文档标题').value).toBe('Human director');
  expect(screen.getByRole('complementary', { name: '分镜原文档状态回传' })).toBeTruthy();
  expect(screen.queryByLabelText('原分镜精确文档')).toBeNull();
  expect(writes()).toEqual([]);
}
function deferred() { let resolve!: (value: ReturnType<typeof response>) => void; const promise = new Promise<ReturnType<typeof response>>(yes => { resolve = yes; }); return { promise, resolve }; }
beforeEach(() => {
  localStorage.clear(); unexpected.length = 0; stored = board(); savedGraph = graph();
  useStudio.setState({ novelId: project, chapterId: '', sessionToken: '', actor: undefined, scope: undefined });
  useLocalHostSession.setState({ token: '', actorId: '' }); server();
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); expect(unexpected).toEqual([]); });

describe('mounted graph → exact original storyboard editor navigation', () => {
  it.each(['IMAGE', 'VIDEO'] as const)('keeps the originating %s shell, exact target and original explicit version-aware save', async module => {
    const view = await inspect(module), beforeOpen = fetchMock.mock.calls.length;
    click('在原分镜编辑器打开');
    await screen.findByLabelText('原分镜精确文档');
    expect(screen.getByLabelText('原分镜精确文档').textContent).toBe(`原分镜 ${targetPin.id} · v7 · ${module}`);
    expect(input('文档标题').value).toBe('Exact selected board');
    expect(input('画面描述').value).toBe('The traveller beside the station window');
    expect(document.querySelectorAll('.app-shell')).toHaveLength(1);
    expect(document.querySelectorAll('.creative-workspace')).toHaveLength(1);
    expect(within(screen.getByRole('tablist', { name: '创作模块' })).getByRole('tab', { name: module === 'IMAGE' ? '图片' : '视频' }).getAttribute('aria-selected')).toBe('true');
    expect(screen.queryByRole('button', { name: '折叠导演总控台' })).toBeNull();
    expect(screen.queryByLabelText('创作图标题')).toBeNull();
    expect(screen.queryByDisplayValue('Never auto-select this board')).toBeNull();
    const admission = fetchMock.mock.calls.slice(beforeOpen).filter(([url]) => url === `${creative}/capabilities` || url.endsWith('/export') || url === `${creative}/documents`);
    expect(admission.map(([url]) => url)).toEqual([`${creative}/capabilities`, `${creative}/documents/${targetPin.id}/export`]);
    expect(targetReads()).toHaveLength(2); expect(writes()).toEqual([]);
    change('画面描述', 'Explicitly edited in the original shot canvas'); click('保存草稿');
    await screen.findByText('已保存 · v8');
    expect(writes()).toHaveLength(1);
    expect(writes()[0][0]).toBe(`${creative}/documents/${targetPin.id}`);
    expect(writes()[0][1].method).toBe('PUT');
    expect(JSON.parse(writes()[0][1].body)).toMatchObject({ expected_version: 7, mode: 'STORYBOARD', shots: [{ id: 'shot-one', frame_prompt: 'Explicitly edited in the original shot canvas' }] });
    expect(stored.source_documents).toEqual(board().source_documents);
    expect(savedGraph).toEqual(graph()); expect(view.props.onModuleChange).not.toHaveBeenCalled();
    expect(fetchMock.mock.calls.some(([url]) => /derive|approve|dispatch|model-capabilities|\/preflight|\/graph-runs/.test(url))).toBe(false);
    change('画面描述', 'Unsaved return draft'); click('返回独立创作图'); click('继续编辑');
    expect(input('画面描述').value).toBe('Unsaved return draft');
    click('返回独立创作图'); fireEvent.click(screen.getByLabelText('确认放弃未保存草稿并离开')); click('确认离开');
    await screen.findByLabelText('创作图标题'); expect(document.querySelectorAll('.app-shell')).toHaveLength(1);
    expect(screen.queryByLabelText('原分镜精确文档')).toBeNull(); expect(writes()).toHaveLength(1);
  });

  it('keeps the original editor dirty draft when a fixed-module switch is cancelled', async () => {
    const view = await inspect(); click('在原分镜编辑器打开'); await screen.findByLabelText('原分镜精确文档');
    change('画面描述', 'Retain this editor draft on module cancellation');
    fireEvent.click(within(screen.getByRole('tablist', { name: '创作模块' })).getByRole('tab', { name: '视频' }));
    expect(view.props.onModuleChange).not.toHaveBeenCalled();
    expect(screen.getByLabelText('确认放弃未保存草稿并离开')).toBeTruthy(); click('继续编辑');
    expect(input('画面描述').value).toBe('Retain this editor draft on module cancellation');
    expect(screen.getByLabelText('原分镜精确文档').textContent).toContain(targetPin.id);
    expect(view.props.onModuleChange).not.toHaveBeenCalled(); expect(writes()).toEqual([]);
    expect(targetReads()).toHaveLength(2);
  });

  it('retires the hosted editor before an accepted dirty fixed-module switch and never revives it on return', async () => {
    const view = await inspect(); click('在原分镜编辑器打开'); await screen.findByLabelText('原分镜精确文档');
    change('画面描述', 'Explicitly discard this editor draft');
    fireEvent.click(within(screen.getByRole('tablist', { name: '创作模块' })).getByRole('tab', { name: '视频' }));
    expect(view.props.onModuleChange).not.toHaveBeenCalled();
    fireEvent.click(screen.getByLabelText('确认放弃未保存草稿并离开')); click('确认离开');
    expect(view.props.onModuleChange).toHaveBeenCalledTimes(1);
    expect(view.props.onModuleChange).toHaveBeenCalledWith('VIDEO');
    expect(screen.queryByLabelText('原分镜精确文档')).toBeNull();
    expect(screen.queryByDisplayValue('Explicitly discard this editor draft')).toBeNull();
    view.rerenderModule('VIDEO'); view.rerenderModule('IMAGE');
    expect(screen.queryByLabelText('原分镜精确文档')).toBeNull();
    await screen.findByLabelText('创作图标题');
    expect(document.querySelectorAll('.app-shell')).toHaveLength(1);
    expect(writes()).toEqual([]); expect(targetReads()).toHaveLength(2);
  });

  it('retires an already mounted editor across external module A→B→A instead of reopening the old receipt', async () => {
    const view = await inspect(); click('在原分镜编辑器打开'); await screen.findByLabelText('原分镜精确文档');
    change('画面描述', 'Old module private editor input');
    view.rerenderModule('VIDEO');
    expect(screen.queryByLabelText('原分镜精确文档')).toBeNull();
    expect(screen.queryByDisplayValue('Old module private editor input')).toBeNull();
    view.rerenderModule('IMAGE');
    expect(screen.queryByLabelText('原分镜精确文档')).toBeNull();
    expect(screen.queryByDisplayValue('Old module private editor input')).toBeNull();
    await screen.findByLabelText('创作图标题');
    expect(view.props.onModuleChange).not.toHaveBeenCalled();
    expect(document.querySelectorAll('.app-shell')).toHaveLength(1);
    expect(writes()).toEqual([]); expect(targetReads()).toHaveLength(2);
  });

  it('cancels dirty graph navigation before any final read or discard', async () => {
    await inspect(); change('创作图标题', 'Unsaved graph input'); const count = fetchMock.mock.calls.length;
    click('在原分镜编辑器打开'); expect(screen.getByLabelText('确认放弃未保存输入')).toBeTruthy();
    expect(fetchMock.mock.calls).toHaveLength(count); click('继续编辑'); expectGraphPreserved();
  });

  it('keeps the graph and director mounted until both admission reads finish, then consumes the receipt without a second admission', async () => {
    const capsRead = deferred(), finalRead = deferred(); let preparing = false;
    server(url => preparing && url === `${creative}/capabilities` ? capsRead.promise : preparing && url === `${creative}/documents/${targetPin.id}/export` ? finalRead.promise : undefined);
    await inspect(); change('创作图标题', 'Unsaved graph input'); preparing = true;
    click('在原分镜编辑器打开'); confirmDiscard(); expectGraphPreserved(); expect(targetReads()).toHaveLength(1);
    await act(async () => { capsRead.resolve(response(caps)); await capsRead.promise; });
    await waitFor(() => expect(targetReads()).toHaveLength(2)); expectGraphPreserved();
    await act(async () => { finalRead.resolve(response(exportReceipt())); await finalRead.promise; });
    await screen.findByLabelText('原分镜精确文档');
    expect(targetReads()).toHaveLength(2); expect(writes()).toEqual([]);
    expect(fetchMock.mock.calls.filter(([url]) => url === `${creative}/capabilities`)).toHaveLength(2);
    expect(screen.queryByLabelText('创作图标题')).toBeNull();
  });

  it.each(['network', '503', 'digest', 'version', 'source binding', 'revoked capability',
    'shot characters', 'shot emotion', 'shot note IDs', 'visual references', 'note planning', 'note performances', 'shot continuity'] as const)('preserves graph input and director state on failed final %s admission', async failure => {
    let preparing = false;
    server(url => {
      if (!preparing) return undefined;
      if (failure === 'revoked capability' && url === `${creative}/capabilities`) return response({ ...caps, can_mutate: false });
      if (url !== `${creative}/documents/${targetPin.id}/export`) return undefined;
      if (failure === 'network') throw new TypeError('Final read offline');
      if (failure === '503') return response({ code: 'UNAVAILABLE' }, 503);
      const value = structuredClone(exportReceipt());
      const body = value.document as unknown as Record<string, unknown>;
      const shot = (body.shots as Record<string, unknown>[])[0];
      if (failure === 'shot characters') shot.characters = {};
      if (failure === 'shot emotion') shot.emotion = {};
      if (failure === 'shot note IDs') shot.director_note_ids = {};
      if (failure === 'visual references') body.visual_target = { style: '', atmosphere: '', reference_works: {}, color: '', rhythm: '' };
      if (failure === 'note planning') shot.director_notes = [{ ...source().director_notes[0], planning: { rationale: {}, evidence: [] } }];
      if (failure === 'note performances') shot.director_notes = [{ ...source().director_notes[0], performances: [{ character: {}, action: '', expression: '', state: '' }] }];
      if (failure === 'shot continuity') shot.continuity = { characters: {}, outfit: '', environment: '', camera: '' };
      if (failure === 'digest') value.document_digest = 'd'.repeat(64);
      if (failure === 'version') value.document = { ...value.document, version: 8 };
      if (failure === 'source binding') value.document = { ...value.document, source_documents: { [sourcePin.id]: { version: 2, digest: 'e'.repeat(64) } } };
      return response(value);
    });
    await inspect(); change('创作图标题', 'Unsaved graph input'); preparing = true;
    click('在原分镜编辑器打开'); confirmDiscard();
    await waitFor(() => expect((screen.getByRole('button', { name: '在原分镜编辑器打开' }) as HTMLButtonElement).disabled).toBe(false));
    expectGraphPreserved(); expect(savedGraph).toEqual(graph());
    click('继续编辑'); expectGraphPreserved();
  });

  it('does not allow an edited director draft to silently replace the inspected source', async () => {
    await inspect(); change('文档标题', 'Unsaved director input');
    expect(screen.queryByRole('button', { name: '在原分镜编辑器打开' })).toBeNull();
    expect(input('文档标题').value).toBe('Unsaved director input');
    expect(screen.queryByLabelText('原分镜精确文档')).toBeNull();
    expect(targetReads()).toHaveLength(1); expect(writes()).toEqual([]);
  });

  it.each(['cancel', 'module ABA'] as const)('ignores a late final export after %s without discarding the graph', async retirement => {
    const late = deferred(); let preparing = false;
    server(url => preparing && url === `${creative}/documents/${targetPin.id}/export` ? late.promise : undefined);
    const view = await inspect(); change('创作图标题', 'Unsaved graph input'); preparing = true;
    click('在原分镜编辑器打开'); confirmDiscard(); await waitFor(() => expect(targetReads()).toHaveLength(2));
    if (retirement === 'cancel') click('继续编辑');
    else { view.rerenderModule('VIDEO'); view.rerenderModule('IMAGE'); }
    await act(async () => { late.resolve(response(exportReceipt())); await late.promise; });
    expectGraphPreserved(); expect(document.querySelectorAll('.app-shell')).toHaveLength(1);
  });
});
