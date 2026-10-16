// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { useLocalHostSession } from '../localHostSession';
import { useStudio } from '../store';
import { IndependentStudioWorkspace } from '../creative/IndependentStudioWorkspace';
import type { StudioOverview } from '../creative/studioClient';
import { productionWorkflowIntent, productionWorkflowProjection } from './productionWorkflowContract';
import {
  PRODUCTION_WORKFLOW_MODULES, type ProductionWorkflowIntent, type ProductionWorkflowProjection,
} from './productionWorkflowTypes';

const project = 'workflow-mounted-project', base = `/api/projects/${project}/studio`, production = `${base}/production`;
const workflowUrl = `${production}/workflow`, intentUrl = `${production}/workflow/intent`;
const MODULE_LABELS = ['导演', '分镜', '图像', '视频', '音频', '时间线', '资产'];
const values = (selected: string[]) => [
  { intent_id: 'novel_writing', label: '小说创作', selected: selected.includes('novel_writing'), custom: false },
  { intent_id: 'image_design', label: '图片设计', selected: selected.includes('image_design'), custom: false },
  { intent_id: 'custom', label: '我的短片', selected: selected.includes('custom'), custom: true },
];
function projection(version: number, selected: string[] = []): ProductionWorkflowProjection {
  return productionWorkflowProjection({
    schema_version: 1, contract: 'studio-production-workflow/1', project_id: project,
    scope: { mode: 'local', novel_id: project }, advisory_only: true, execution_authority: false,
    generated_at: '2026-10-14T09:41:59+00:00',
    project_start: {
      state: 'STARTED', entry_kind: 'NEUTRAL_STUDIO', incarnation: 'file:2f1a9c3e-0000-4000-8000-000000000000',
      has_creative_documents: true,
      start_action: { method: 'POST', path: '/api/experimental/projects', requires_original_host_session: true },
    },
    creative_intent: { version, preset: 'IMAGE', values: values(selected), editable: true, history_retained: true },
    modules: PRODUCTION_WORKFLOW_MODULES.map((id, index) => ({
      id, label: MODULE_LABELS[index], status: index === 2 ? 'REVIEW_PENDING' : 'NOT_STARTED',
      document_count: 0, asset_count: index === 2 ? 3 : 0, job_count: 0,
      blocked_reasons: index === 2 ? ['PRIVATE_CANDIDATES_AWAITING_REVIEW'] : [],
      owner: `Owner${index}`, next_action: `下一步${index}`,
    })),
    asset_overview: { total: 3, by_kind: { image: 3, audio: 0, video: 0, text: 0, other: 0 }, private_pending_review: 3, reviewed: 0 },
    dashboard: { stages_total: 7, stages_started: 1, stages_reviewed: 0, open_reviews: 3, blocked_stages: ['image'] },
  }, project);
}
const intentView = (version: number, selected: string[]): ProductionWorkflowIntent => productionWorkflowIntent({
  version, preset: 'IMAGE', editable: true, history_retained: true, values: values(selected),
});
const overview = (): StudioOverview => ({
  project: { id: project, title: 'Workflow fixture', entry_kind: 'NEUTRAL_STUDIO' },
  preferences: { version: 1, intents: [], preset: 'IMAGE', custom_intent: '' },
  capabilities: { can_mutate: true, can_review: true, manual_import: true, manual_export: true, chapter_required: false,
    model_required: false, media_validator_configured: true, asset_kinds: ['image', 'video', 'audio'], intent_is_permission: false },
});
const reply = (value: unknown, status = 200) => ({ ok: status < 400, status, json: async () => value, blob: async () => new Blob() });
let fetcher: ReturnType<typeof vi.fn>, conflictOnce: boolean, reads: number, savedVersion: number;

beforeEach(() => {
  localStorage.clear(); vi.stubGlobal('crypto', webcrypto); conflictOnce = false; reads = 0; savedVersion = 3;
  useStudio.setState({ novelId: project, chapterId: '', sessionToken: '', actor: undefined, scope: undefined });
  useLocalHostSession.setState({ token: 'workflow-host', actorId: '' });
  fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === base) return reply(overview());
    if (url.includes('/assets?')) return reply({ items: [] });
    if (url === `${base}/production-contracts`) return reply({ code: 'FIXTURE_CATALOG_UNAVAILABLE' }, 400);
    if (url === workflowUrl) { reads += 1; return reply(projection(reads === 1 ? savedVersion : 5, [])); }
    if (url === intentUrl) {
      const body = JSON.parse(String(init?.body)) as { expected_version: number; values: { intent_id: string; selected: boolean }[] };
      if (conflictOnce) { conflictOnce = false; return reply({ code: 'PRODUCTION_WORKFLOW_INTENT_CONFLICT' }, 409); }
      if (body.expected_version !== 5) return reply({ code: 'PRODUCTION_WORKFLOW_INTENT_CONFLICT' }, 409);
      savedVersion = 6;
      return reply(intentView(6, body.values.filter(item => item.selected).map(item => item.intent_id)));
    }
    if (url === `${production}/providers`) return reply({ items: [], health_probed: false, credentials_read: false });
    if (url.startsWith(`${production}/jobs`)) return reply({ items: [] });
    if (url === `${production}/timelines`) return reply({ items: [] });
    throw new Error(`Unexpected fixture request: ${url}`);
  });
  vi.stubGlobal('fetch', fetcher);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function mount() {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={query}><IndependentStudioWorkspace projectId={project} context={{ sessionToken: '' }}
    scope={{ workspace: '本机', project: 'Workflow fixture', storyline: '默认', branch: '主线' }} actor="作者" module="IMAGE"
    onModuleChange={vi.fn()} onProjectChoice={vi.fn()} /></QueryClientProvider>);
}
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
/** The sidebar preference form uses the same intent labels; scope every query to this editor. */
const intentCheckbox = (label: string) => within(screen.getByRole('region', { name: '创作意图编辑' })).getByLabelText(label) as HTMLInputElement;
async function openWorkflow() {
  fireEvent.click(await screen.findByRole('button', { name: '制作操作' }));
  await screen.findByRole('region', { name: '七个制作模块状态' });
}

describe('production workflow dashboard mounted in the original Studio workspace', () => {
  it('reads the projection once through the captured host session and renders it beside the operation contracts', async () => {
    mount(); await openWorkflow();
    const request = fetcher.mock.calls.find(([url]) => url === workflowUrl);
    expect(request).toBeTruthy();
    expect((request![1] as RequestInit).method).toBe('GET');
    expect((request![1] as RequestInit).headers).toMatchObject({ 'X-Session-Token': 'workflow-host', 'X-Request-ID': expect.any(String) });
    expect(reads).toBe(1);
    const dashboard = screen.getByRole('region', { name: 'Studio 生产工作流看板' });
    expect(within(dashboard).getByText('独立项目已开始')).toBeTruthy();
    expect(within(screen.getByRole('region', { name: '七个制作模块状态' })).getAllByRole('article')).toHaveLength(7);
    const image = within(screen.getByRole('region', { name: '七个制作模块状态' })).getByRole('article', { name: '图像模块' });
    expect(within(image).getByText(/有私有候选等待人工复核/)).toBeTruthy();
    expect(screen.getByRole('region', { name: '素材概览' }).textContent).toContain('共 3 项');
    // The existing contract panel is still mounted next to it.
    expect(screen.getByLabelText('Studio 制作操作契约')).toBeTruthy();
    const inspector = screen.getByRole('region', { name: 'Studio 生产工作流检查器' });
    expect(within(inspector).getByText('建议下一步：下一步0')).toBeTruthy();
    expect(within(inspector).getByRole('region', { name: '素材浏览器' }).textContent).toContain('图片 · 3 项');
    expect(screen.getByRole('button', { name: '读取模型可用性' })).toBeTruthy();
    expect(fetcher.mock.calls.some(([url]) => /model-center/.test(url))).toBe(false);
  });

  it('keeps the author selection through a 409 and saves it against the re-read version', async () => {
    conflictOnce = true; mount(); await openWorkflow();
    fireEvent.click(intentCheckbox('图片设计'));
    await waitFor(() => expect(button('保存创作意图').disabled).toBe(false));
    fireEvent.click(button('保存创作意图'));
    await screen.findByText(/版本冲突/);
    expect(intentCheckbox('图片设计').checked).toBe(true);
    expect(reads).toBe(2);
    fireEvent.click(button('已核对，保留我的选择'));
    await waitFor(() => expect(button('保存创作意图').disabled).toBe(false));
    fireEvent.click(button('保存创作意图'));
    await screen.findByText('创作意图已保存 · v6。');
    const writes = fetcher.mock.calls.filter(([url, init]) => url === intentUrl && init?.method === 'POST');
    expect(writes).toHaveLength(2);
    expect(JSON.parse(String(writes[0][1]!.body))).toMatchObject({ expected_version: 3 });
    expect(JSON.parse(String(writes[1][1]!.body))).toMatchObject({ expected_version: 5 });
    for (const [, init] of writes) expect((init!.headers as Record<string, string>)['Idempotency-Key']).toEqual(expect.any(String));
    expect(intentCheckbox('图片设计').checked).toBe(true);
  });

  it('asks before leaving the production view while the intent draft is unsaved', async () => {
    mount(); await openWorkflow();
    fireEvent.click(intentCheckbox('图片设计'));
    await waitFor(() => expect(button('保存创作意图').disabled).toBe(false));
    fireEvent.click(button('素材工作区'));
    await screen.findByText('确认放弃未保存输入');
    fireEvent.click(button('继续编辑'));
    await screen.findByRole('region', { name: 'Studio 生产工作流看板' });
    expect(intentCheckbox('图片设计').checked).toBe(true);
    expect(fetcher.mock.calls.some(([url, init]) => url === intentUrl && init?.method === 'POST')).toBe(false);
  });
});
