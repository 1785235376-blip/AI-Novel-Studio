// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { ProductionDashboard } from './ProductionDashboard';
import { productionWorkflowIntent, productionWorkflowProjection } from './productionWorkflowContract';
import {
  PRODUCTION_WORKFLOW_MODULES, type ProductionWorkflowAssetKind, type ProductionWorkflowClient,
  type ProductionWorkflowIntent, type ProductionWorkflowModuleId, type ProductionWorkflowProjection,
} from './productionWorkflowTypes';
import { useProductionWorkflow } from './useProductionWorkflow';

const MODULE_LABELS = ['导演', '分镜', '图像', '视频', '音频', '时间线', '资产'];
const values = (selected: string[]) => [
  { intent_id: 'novel_writing', label: '小说创作', selected: selected.includes('novel_writing'), custom: false },
  { intent_id: 'image_design', label: '图片设计', selected: selected.includes('image_design'), custom: false },
  { intent_id: 'custom', label: '我的短片', selected: selected.includes('custom'), custom: true },
];
function projection(version = 3, selected: string[] = [], blocked = false): ProductionWorkflowProjection {
  const pending = blocked ? 1 : 0;
  return productionWorkflowProjection({
    schema_version: 1, contract: 'studio-production-workflow/1', project_id: 'studio-project',
    scope: { mode: 'local', novel_id: 'studio-project' }, advisory_only: true, execution_authority: false,
    generated_at: '2026-10-14T09:41:59+00:00',
    project_start: {
      state: 'STARTED', entry_kind: 'NEUTRAL_STUDIO', incarnation: 'file:2f1a9c3e-0000-4000-8000-000000000000',
      has_creative_documents: true,
      start_action: { method: 'POST', path: '/api/experimental/projects', requires_original_host_session: true },
    },
    creative_intent: { version, preset: 'IMAGE', values: values(selected), editable: true, history_retained: true },
    modules: PRODUCTION_WORKFLOW_MODULES.map((id, index) => ({
      id, label: MODULE_LABELS[index], status: blocked && index === 0 ? 'REVIEW_PENDING' : 'NOT_STARTED',
      document_count: index, asset_count: blocked && index === 0 ? 3 : 0, job_count: 0,
      blocked_reasons: blocked && index === 0 ? ['PRIVATE_CANDIDATES_AWAITING_REVIEW'] : [],
      owner: `Owner${index}`, next_action: `下一步${index}`,
    })),
    asset_overview: { total: pending, by_kind: { image: pending, audio: 0, video: 0, text: 0, other: 0 }, private_pending_review: pending, reviewed: 0 },
    dashboard: { stages_total: 7, stages_started: blocked ? 1 : 0, stages_reviewed: 0, open_reviews: pending, blocked_stages: blocked ? ['director'] : [] },
  }, 'studio-project');
}
const intentView = (version: number, selected: string[]): ProductionWorkflowIntent => productionWorkflowIntent({
  version, preset: 'IMAGE', editable: true, history_retained: true, values: values(selected),
});
function fakeClient(patch: Partial<{ read: ReturnType<typeof vi.fn>; updateIntent: ReturnType<typeof vi.fn> }> = {}) {
  const client = { read: vi.fn(async () => projection()), updateIntent: vi.fn(async () => intentView(4, ['image_design'])), ...patch };
  return { client: client as unknown as ProductionWorkflowClient, read: client.read, updateIntent: client.updateIntent };
}
function Host({ client }: { client: ProductionWorkflowClient }) {
  const [selected, setSelected] = useState<ProductionWorkflowModuleId>('director');
  const [kind, setKind] = useState<ProductionWorkflowAssetKind>('image');
  const controller = useProductionWorkflow({
    identity: 'dashboard-session', active: true, denied: false, busy: false, isCurrent: () => true,
    read: work => work(), mutate: work => work(), client,
  });
  return <ProductionDashboard controller={controller} selectedModuleId={selected} onSelectModule={setSelected}
    selectedKind={kind} onSelectKind={setKind}/>;
}
const mount = (client: ProductionWorkflowClient) => render(<Host client={client}/>);
const board = () => screen.getByRole('region', { name: '七个制作模块状态' });
const save = () => screen.getByRole('button', { name: '保存创作意图' }) as HTMLButtonElement;

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('Studio production workflow dashboard', () => {
  it('renders the project start, the intent editor, seven modules and the asset overview', async () => {
    const { client } = fakeClient();
    mount(client);
    const panel = await screen.findByRole('region', { name: 'Studio 生产工作流看板' });
    expect(within(screen.getByRole('region', { name: '项目开始状态' })).getByText('独立项目已开始')).toBeTruthy();
    expect(panel.textContent).toContain('POST /api/experimental/projects');
    expect(screen.getByRole('region', { name: '创作意图编辑' })).toBeTruthy();
    expect((screen.getByLabelText('图片设计') as HTMLInputElement).checked).toBe(false);
    expect(within(board()).getAllByRole('article')).toHaveLength(7);
    expect(within(board()).getByRole('button', { name: '时间线' }).getAttribute('aria-pressed')).toBe('false');
    expect(screen.getByRole('region', { name: '素材概览' }).textContent).toContain('共 0 项');
    expect(save().disabled).toBe(true);
  });

  it('shows a blocked module with its user-facing reason and its raw blocker code', async () => {
    const { client } = fakeClient({ read: vi.fn(async () => projection(3, [], true)) });
    mount(client);
    await screen.findByRole('region', { name: '七个制作模块状态' });
    const director = within(board()).getByRole('article', { name: '导演模块' });
    expect(within(director).getByText(/有私有候选等待人工复核/)).toBeTruthy();
    expect(director.textContent).toContain('PRIVATE_CANDIDATES_AWAITING_REVIEW');
    expect(director.textContent).toContain('建议下一步：下一步0');
    expect(within(board()).getAllByRole('article')).toHaveLength(7);
  });

  it('preserves the local selection through a 409 conflict and re-submits the re-read version', async () => {
    const { client, read, updateIntent } = fakeClient();
    read.mockResolvedValueOnce(projection(3, [])).mockResolvedValue(projection(5, []));
    updateIntent.mockRejectedValueOnce(new ApiError({ status: 409, code: 'PRODUCTION_WORKFLOW_INTENT_CONFLICT', message: 'conflict' }));
    mount(client);
    await screen.findByRole('region', { name: '七个制作模块状态' });
    fireEvent.click(screen.getByLabelText('图片设计'));
    await waitFor(() => expect(save().disabled).toBe(false));
    fireEvent.click(save());
    await screen.findByText(/版本冲突/);
    expect((screen.getByLabelText('图片设计') as HTMLInputElement).checked).toBe(true);
    expect(screen.getByText(/你的选择仍保留/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '已核对，保留我的选择' }));
    await waitFor(() => expect(save().disabled).toBe(false));
    updateIntent.mockResolvedValueOnce(intentView(6, ['image_design']));
    fireEvent.click(save());
    await screen.findByText('创作意图已保存 · v6。');
    expect(updateIntent).toHaveBeenLastCalledWith({ expected_version: 5, values: expect.any(Array) });
    expect((screen.getByLabelText('图片设计') as HTMLInputElement).checked).toBe(true);
  });

  it('keeps the intent editor keyboard operable and never saves on a skip', async () => {
    const { client, updateIntent } = fakeClient();
    mount(client);
    await screen.findByRole('region', { name: '七个制作模块状态' });
    const custom = screen.getByLabelText('我的短片') as HTMLInputElement;
    expect(custom.type).toBe('checkbox');
    fireEvent.click(custom);
    expect(custom.checked).toBe(true);
    fireEvent.change(screen.getByLabelText('自定义创作意图名称'), { target: { value: '我的新短片' } });
    expect((screen.getByLabelText('自定义创作意图名称') as HTMLInputElement).value).toBe('我的新短片');
    fireEvent.click(screen.getByRole('button', { name: '跳过（稍后设置）' }));
    expect((screen.getByLabelText('我的短片') as HTMLInputElement).checked).toBe(false);
    expect(save().disabled).toBe(true);
    expect(updateIntent).not.toHaveBeenCalled();
  });

  it('switches the selected module through an accessible pressed button', async () => {
    const { client } = fakeClient();
    mount(client);
    await screen.findByRole('region', { name: '七个制作模块状态' });
    const audio = within(board()).getByRole('button', { name: '音频' });
    expect(audio.tagName).toBe('BUTTON');
    fireEvent.click(audio);
    expect(within(board()).getByRole('button', { name: '音频' }).getAttribute('aria-pressed')).toBe('true');
    expect(within(board()).getByRole('button', { name: '导演' }).getAttribute('aria-pressed')).toBe('false');
    expect(within(board()).getAllByRole('article')).toHaveLength(7);
  });

  it('reports a read failure without echoing the raw failure text', async () => {
    const { client } = fakeClient({ read: vi.fn(async () => { throw new Error('Unexpected fixture request: /private/path'); }) });
    mount(client);
    await screen.findByText('生产工作流读取失败');
    expect(screen.getByText(/制作工作流读取失败，请稍后重新核对。/)).toBeTruthy();
    expect(document.body.textContent).not.toContain('/private/path');
  });
});
