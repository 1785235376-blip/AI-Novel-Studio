// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { productionWorkflowIntent, productionWorkflowProjection } from './productionWorkflowContract';
import {
  PRODUCTION_WORKFLOW_MODULES, type ProductionWorkflowClient, type ProductionWorkflowIntent,
  type ProductionWorkflowProjection,
} from './productionWorkflowTypes';
import { useProductionWorkflow, type ProductionWorkflowControllerProps } from './useProductionWorkflow';

const values = (selected: string[]) => [
  { intent_id: 'novel_writing', label: '小说创作', selected: selected.includes('novel_writing'), custom: false },
  { intent_id: 'image_design', label: '图片设计', selected: selected.includes('image_design'), custom: false },
  { intent_id: 'custom', label: '我的短片', selected: selected.includes('custom'), custom: true },
];
/** Fixtures are built through the strict validator, so the hook is driven by real contract data. */
function projection(version: number, selected: string[] = [], blocked = false): ProductionWorkflowProjection {
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
      id, label: `模块${index}`, status: blocked && index === 0 ? 'REVIEW_PENDING' : 'NOT_STARTED',
      document_count: 0, asset_count: blocked && index === 0 ? 3 : 0, job_count: 0,
      blocked_reasons: blocked && index === 0 ? ['PRIVATE_CANDIDATES_AWAITING_REVIEW'] : [],
      owner: `Owner${index}`, next_action: '尚未开始',
    })),
    asset_overview: { total: pending, by_kind: { image: pending, audio: 0, video: 0, text: 0, other: 0 }, private_pending_review: pending, reviewed: 0 },
    dashboard: { stages_total: 7, stages_started: blocked ? 1 : 0, stages_reviewed: 0, open_reviews: pending, blocked_stages: blocked ? ['director'] : [] },
  }, 'studio-project');
}
const intentView = (version: number, selected: string[]): ProductionWorkflowIntent => productionWorkflowIntent({
  version, preset: 'IMAGE', editable: true, history_retained: true, values: values(selected),
});
type Fake = { read: ReturnType<typeof vi.fn>; updateIntent: ReturnType<typeof vi.fn> };
function fakeClient(patch: Partial<Fake> = {}) {
  const client: Fake = {
    read: vi.fn(async () => projection(3, [])), updateIntent: vi.fn(async () => intentView(4, [])), ...patch,
  };
  return { client: client as unknown as ProductionWorkflowClient, read: client.read, updateIntent: client.updateIntent };
}
const props = (client: ProductionWorkflowClient, patch: Partial<ProductionWorkflowControllerProps> = {}): ProductionWorkflowControllerProps => ({
  identity: 'workflow-session', active: true, denied: false, busy: false, isCurrent: () => true,
  read: work => work(), mutate: work => work(), client, ...patch,
});
const mount = (client: ProductionWorkflowClient, patch: Partial<ProductionWorkflowControllerProps> = {}) =>
  renderHook((value: ProductionWorkflowControllerProps) => useProductionWorkflow(value), { initialProps: props(client, patch) });

afterEach(() => cleanup());

describe('production workflow controller', () => {
  it('reads once when the view opens and never while it is closed', async () => {
    const { client, read } = fakeClient();
    const view = mount(client, { active: false });
    expect(view.result.current.state).toBe('IDLE');
    expect(read).not.toHaveBeenCalled();
    view.rerender(props(client, { active: true }));
    await waitFor(() => expect(view.result.current.state).toBe('READY'));
    expect(read).toHaveBeenCalledTimes(1);
    expect(read).toHaveBeenCalledWith(expect.any(AbortSignal));
    expect(view.result.current.projection?.creative_intent.version).toBe(3);
    await act(async () => { await view.result.current.reload(); });
    expect(read).toHaveBeenCalledTimes(2);
  });

  it('keeps the served value until an explicit save and preserves the draft through a 409 conflict', async () => {
    const { client, read, updateIntent } = fakeClient();
    read.mockResolvedValueOnce(projection(3, [])).mockResolvedValue(projection(5, []));
    const flags: boolean[] = [];
    const view = mount(client, { onDirtyChange: value => flags.push(value) });
    await waitFor(() => expect(view.result.current.state).toBe('READY'));
    act(() => view.result.current.toggleIntent('image_design'));
    expect(view.result.current.dirty).toBe(true);
    expect(view.result.current.canSubmit).toBe(true);
    expect(view.result.current.values.find(item => item.intent_id === 'image_design')?.selected).toBe(true);
    // No optimistic invention: the served projection still holds the saved value.
    expect(view.result.current.projection?.creative_intent.values.find(item => item.intent_id === 'image_design')?.selected).toBe(false);
    updateIntent.mockRejectedValueOnce(new ApiError({ status: 409, code: 'PRODUCTION_WORKFLOW_INTENT_CONFLICT', message: 'conflict' }));
    await act(async () => { await view.result.current.submit(); });
    await waitFor(() => expect(view.result.current.conflict).toBe(true));
    expect(view.result.current.problem?.code).toBe('PRODUCTION_WORKFLOW_INTENT_CONFLICT');
    expect(view.result.current.values.find(item => item.intent_id === 'image_design')?.selected).toBe(true);
    await waitFor(() => expect(view.result.current.draft?.expected_version).toBe(5));
    expect(view.result.current.canSubmit).toBe(false);
    expect(view.result.current.notice).toContain('本地选择尚未提交');
    act(() => view.result.current.acknowledgeConflict());
    expect(view.result.current.conflict).toBe(false);
    expect(view.result.current.canSubmit).toBe(true);
    updateIntent.mockResolvedValueOnce(intentView(6, ['image_design']));
    await act(async () => { await view.result.current.submit(); });
    expect(updateIntent).toHaveBeenLastCalledWith({ expected_version: 5, values: expect.any(Array) });
    expect(view.result.current.draft).toBeUndefined();
    expect(view.result.current.projection?.creative_intent.version).toBe(6);
    expect(view.result.current.notice).toContain('v6');
    expect(flags[flags.length - 1]).toBe(false);
  });

  it('refuses a selected custom intent without a name and never writes', async () => {
    const { client, updateIntent } = fakeClient();
    const view = mount(client);
    await waitFor(() => expect(view.result.current.state).toBe('READY'));
    act(() => view.result.current.toggleIntent('custom'));
    act(() => view.result.current.setCustomLabel('   '));
    expect(view.result.current.customPending).toBe(true);
    expect(view.result.current.canSubmit).toBe(false);
    await act(async () => { await view.result.current.submit(); });
    expect(updateIntent).not.toHaveBeenCalled();
    expect(view.result.current.problem?.code).toBe('PRODUCTION_WORKFLOW_INTENT_LOCAL_INVALID');
    act(() => view.result.current.setCustomLabel('我的短片'));
    expect(view.result.current.customPending).toBe(false);
    expect(view.result.current.canSubmit).toBe(true);
  });

  it('drops the draft on skip and reports it as clean', async () => {
    const { client } = fakeClient();
    const flags: boolean[] = [];
    const view = mount(client, { onDirtyChange: value => flags.push(value) });
    await waitFor(() => expect(view.result.current.state).toBe('READY'));
    act(() => view.result.current.toggleIntent('image_design'));
    expect(view.result.current.dirty).toBe(true);
    act(() => view.result.current.skip());
    expect(view.result.current.draft).toBeUndefined();
    expect(view.result.current.dirty).toBe(false);
    expect(flags[flags.length - 1]).toBe(false);
  });

  it('clears data and reaches DENIED when the session loses authority', async () => {
    const onUnavailable = vi.fn();
    const { client, read } = fakeClient({
      read: vi.fn(async () => { throw new ApiError({ status: 403, code: 'CREATIVE_AUTHORITY_INVALID', message: 'denied' }); }),
    });
    const view = mount(client, { onUnavailable });
    await waitFor(() => expect(view.result.current.state).toBe('DENIED'));
    expect(view.result.current.projection).toBeUndefined();
    expect(view.result.current.canRead).toBe(false);
    expect(onUnavailable).toHaveBeenCalledTimes(1);
    await act(async () => { await view.result.current.reload(); });
    expect(read).toHaveBeenCalledTimes(1);
  });

  it('marks a not-found or conflicting read as unavailable instead of an error', async () => {
    const { client } = fakeClient({
      read: vi.fn(async () => { throw new ApiError({ status: 404, code: 'STUDIO_REQUEST_FAILED', message: '记录不可用。' }); }),
    });
    const view = mount(client);
    await waitFor(() => expect(view.result.current.state).toBe('UNAVAILABLE'));
  });

  it('never echoes an unexpected local failure verbatim', async () => {
    const { client } = fakeClient({
      read: vi.fn(async () => { throw new Error('Unexpected fixture request: /private/provider/path'); }),
    });
    const view = mount(client);
    await waitFor(() => expect(view.result.current.state).toBe('ERROR'));
    expect(view.result.current.problem?.code).toBe('PRODUCTION_WORKFLOW_READ_FAILED');
    expect(view.result.current.problem?.message).toBe('制作工作流读取失败，请稍后重新核对。');
  });

  it('keeps the draft when a save fails with an unexpected status', async () => {
    const { client, updateIntent } = fakeClient();
    updateIntent.mockRejectedValueOnce(new ApiError({ status: 503, code: 'STUDIO_REQUEST_FAILED', message: '请求未完成。' }));
    const view = mount(client);
    await waitFor(() => expect(view.result.current.state).toBe('READY'));
    act(() => view.result.current.toggleIntent('image_design'));
    await act(async () => { await view.result.current.submit(); });
    expect(view.result.current.draft).toBeDefined();
    expect(view.result.current.dirty).toBe(true);
    expect(view.result.current.conflict).toBe(false);
    expect(view.result.current.problem?.code).toBe('STUDIO_REQUEST_FAILED');
  });
});
