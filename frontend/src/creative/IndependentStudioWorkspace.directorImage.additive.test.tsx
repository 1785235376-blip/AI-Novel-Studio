// @vitest-environment jsdom
// Real workspace, graph/controller, IMAGE panel and clients; HTTP is the only fixture boundary.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { useStudio } from '../store';
import { useLocalHostSession } from '../localHostSession';
import { IndependentStudioWorkspace } from './IndependentStudioWorkspace';
import { blankGraph } from './graphDraft';
import { modelCatalog } from './studioGraphModel.testFixtures';
import type { StudioGraphRecord } from './studioGraphTypes';
import type { StudioOverview } from './studioClient';
import { imageAsset, imageCapabilitiesWire, imagePendingWire, imageReviewWire, imageSnapshot, imageSourceDocument, imageStatusWire } from './directorImage.testFixtures';
import emptyPromptLibrary from '../prompt/__fixtures__/empty-library.json';

const studio = '/api/projects/project/studio', creative = '/api/novels/project/experimental/creative', images = `${creative}/director-image-v3`;
const overview: StudioOverview = { project: { id: 'project', title: 'Image workflow project', entry_kind: 'NEUTRAL_STUDIO' }, preferences: { version: 1, intents: [], preset: 'BLANK', custom_intent: '' },
  capabilities: { can_mutate: true, can_review: true, manual_import: true, manual_export: true, model_required: false, chapter_required: false, intent_is_permission: false, media_validator_configured: true, asset_kinds: ['image', 'video', 'audio'] } };
const graph: StudioGraphRecord = { project_id: 'project', scope: { mode: 'local', novel_id: 'project' }, id: 'saved-graph', version: 4, can_edit: true, reference_states: [],
  definition_digest: 'f'.repeat(64), execution_digest: 'f'.repeat(64), created_at: '2026-10-18T00:00:00Z', updated_at: '2026-10-18T00:00:00Z', definition: { ...blankGraph(), title: 'Saved original graph',
    nodes: [{ id: 'author-input', definition_id: 'text_input', definition_version: 1, enabled: true, position: { x: 0, y: 0 }, parameters: { text: 'Original graph input' } }] } };
const response = (body: unknown) => ({ ok: true, status: 200, json: async () => structuredClone(body) });
const unexpected: string[] = [];
let fetchMock: ReturnType<typeof vi.fn>, imageOpened: boolean;
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const change = (name: string, value: string) => fireEvent.change(screen.getByLabelText(name), { target: { value } });
const value = (name: string) => (screen.getByLabelText(name) as HTMLInputElement).value;
beforeEach(() => {
  localStorage.clear(); unexpected.length = 0; imageOpened = false;
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);
  useStudio.setState({ novelId: 'project', chapterId: '', sessionToken: '', actor: undefined, scope: undefined });
  useLocalHostSession.setState({ token: 'fixture-host', actorId: '' });
  fetchMock = vi.fn(async (url: string, init: RequestInit = {}) => {
    if (url === studio) return response(overview);
    if (url === `${studio}/prompts`) return response({ ...emptyPromptLibrary, project_id: 'project', scope: { mode: 'local', novel_id: 'project' } });
    if (url === `${studio}/assets` || url.startsWith(`${studio}/assets?`)) return response({ items: imageOpened ? [imageAsset] : [] });
    if (url === `${studio}/graphs/catalog`) return response(modelCatalog(false));
    if (url === `${studio}/graphs`) return response({ items: [graph] });
    if (url === `${studio}/graphs/${graph.id}`) return response(graph);
    if (url === `${studio}/graphs/${graph.id}/runs`) return response({ items: [] });
    if (url === `${creative}/capabilities`) return response({ enabled: true, can_mutate: true, modes: ['DIRECTOR'] });
    if (url === `${creative}/documents`) return response({ items: [imageSourceDocument] });
    if (url === `${creative}/documents/director/export`) return response({ document: imageSourceDocument, document_digest: imageSnapshot.digest });
    if (url === `${creative}/director-proposals` || url === `${creative}/director-proposals/model-routes`) return response({ items: [] });
    if (url === `${images}/capabilities`) { imageOpened = true; return response(imageCapabilitiesWire); }
    if (url === `${images}/proposals`) return response({ items: [imageStatusWire], limit: 30, truncated: false });
    if (url === `${images}/proposals/proposal`) return response(imageStatusWire);
    if (url === `${images}/proposals/proposal/prepare-review`) return response(imagePendingWire);
    if (url === `${images}/proposals/proposal/review`) return response(imageReviewWire);
    if (url === '/api/novels/project/creation-reference-data') return response({ characters: [], locations: [], story_routes: [] });
    if (url === '/api/novels/project/assets') return response([]);
    unexpected.push(`${init.method} ${url}`); throw new Error(`Unexpected request: ${init.method} ${url}`);
  });
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); expect(unexpected).toEqual([]); });
async function enter() {
  const onOpenBroker = vi.fn(), client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><IndependentStudioWorkspace projectId="project" context={{ sessionToken: '' }}
    scope={{ workspace: 'Local', project: 'Image workflow project', storyline: 'Default', branch: 'Main' }} actor="Author" module="IMAGE"
    onModuleChange={vi.fn()} onProjectChoice={vi.fn()} onOpenBroker={onOpenBroker} /></QueryClientProvider>);
  await waitFor(() => expect((screen.getByRole('button', { name: '创作图' }) as HTMLButtonElement).disabled).toBe(false)); click('创作图');
  await screen.findByRole('option', { name: /Saved original graph/ }); change('已保存创作图', graph.id);
  await waitFor(() => expect(value('创作图标题')).toBe(graph.definition.title)); click('打开导演总控台');
  await waitFor(() => expect((screen.getByLabelText('文档标题').closest('fieldset') as HTMLFieldSetElement).disabled).toBe(false));
  click('读取导演原文档目录'); await screen.findByRole('option', { name: /原导演 · v2/ }); change('总控台原导演文档', 'director'); click('读取所选导演原文档');
  fireEvent.click(await screen.findByRole('button', { name: '打开图像导演审核' })); await screen.findByRole('option', { name: /现有 VISION 注册/ }); change('图像理解目标场景', 'scene');
  click('读取图像提案目录'); await screen.findByRole('option', { name: /proposal · DISPATCHED/ }); change('已保存图像提案', 'proposal'); click('读取同一提案状态'); await screen.findByText(/仅核对任务元数据/);
  return onOpenBroker;
}
it.each(['cost', 'note'] as const)('keeps unsent IMAGE %s through real Broker navigation cancel, then discards only after explicit confirmation', async kind => {
  const onOpenBroker = await enter();
  const field = kind === 'cost' ? '成本声明依据' : '人工审核后的导演备注', secret = `private-unsent-image-${kind}`;
  click(kind === 'cost' ? '准备图像成本审核' : '读取图像人工审核内容'); await screen.findByLabelText(field);
  if (kind === 'cost') change('人工声明本地成本（microUSD，1 USD = 1000000）', '37');
  change(field, secret);
  const before = fetchMock.mock.calls.length;
  click('打开原 Broker 预算设置');
  expect(onOpenBroker).not.toHaveBeenCalled(); expect(screen.getByText(/有未保存的创作图／导演输入/)).toBeTruthy();
  expect((screen.getByRole('button', { name: '确认离开' }) as HTMLButtonElement).disabled).toBe(true);
  expect(value(field)).toBe(secret); click('继续编辑'); expect(value(field)).toBe(secret);
  if (kind === 'cost') expect(value('人工声明本地成本（microUSD，1 USD = 1000000）')).toBe('37');
  expect(onOpenBroker).not.toHaveBeenCalled(); click('打开原 Broker 预算设置');
  fireEvent.click(screen.getByLabelText('确认放弃未保存输入')); click('确认离开');
  expect(onOpenBroker).toHaveBeenCalledTimes(1); expect(screen.queryByDisplayValue(secret)).toBeNull();
  expect(fetchMock.mock.calls.slice(before).some(([, init]) => init.method !== 'GET')).toBe(false);
  expect(fetchMock.mock.calls.some(([url]) => /\/(declare-cost|adopt|dispatch)$/.test(url))).toBe(false);
  expect(Array.from({ length: localStorage.length }, (_, index) => localStorage.getItem(localStorage.key(index)!)).join('')).not.toContain(secret);
});
