// @vitest-environment jsdom
/** Component lifecycle with software metadata responses only; no queue, media or approval. */
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createHash, webcrypto } from 'node:crypto';
import { StrictMode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CanvasImageNodeTask, type CanvasImageNodeTaskProps } from './CanvasImageNodeTask';
import { canonicalImageNode } from './canvasImageNode';
import { canvasImageNodeCreateHintKey, persistCanvasImageNodeCreateHint, readCanvasImageNodeCreateHint,
  type CanvasImageNodeCreateIntent } from './canvasImageNodeCreateIntent';
import type { StudioMediaExecutionProps } from './useStudioMediaExecution';
import type { CanvasViewRecord } from './studioCanvasViewClient';
import type { ProductionJob } from './studioProductionClient';

let panel: StudioMediaExecutionProps | undefined;
vi.mock('./StudioMediaExecutionPanel', () => ({ StudioMediaExecutionPanel: (props: StudioMediaExecutionProps) => {
  panel = props; return <p>Original production metadata panel</p>;
} }));
const incarnation = 'file:12345678-1234-1234-1234-123456789abc';
const owner = { projectId: 'recover-project', incarnation, actorId: 'recover-author', actorWorkspaceId: '', mode: 'local' as const,
  workspaceId: '', storylineId: '', branchId: '' };
const node = { id: 'recover-node', title: 'One recoverable node', prompt: 'A lighthouse', x: 24, y: 48 };
const intent: CanvasImageNodeCreateIntent = { contract: 'studio-canvas-image-node-create/1', project_id: owner.projectId,
  scope: { mode: 'local', novel_id: owner.projectId }, incarnation, node_id: node.id, title: node.title,
  position: { x: node.x, y: node.y }, prompt_digest: createHash('sha256').update(node.prompt).digest('hex') };
const prepareLabel = '为此节点保存正式空白位置', resolveLabel = '重新核对此次空白位置创建';
function retained(button: HTMLElement) {
  const key = Object.keys(button).find(key => key.startsWith('__reactProps$'))!;
  return (button as unknown as Record<string, { onClick: () => void }>)[key].onClick;
}
function fixture() {
  const definition = { schema_version: 1 as const, title: node.title, cards: [], viewport: { x: 0, y: 0, zoom: 1 } };
  const canvas = { project_id: owner.projectId, scope: intent.scope, id: 'the-original-empty-view', version: 1,
    definition_digest: createHash('sha256').update(canonicalImageNode(definition)).digest('hex'), definition,
    reference_states: [], created_at: '2026-10-24', updated_at: '2026-10-24', execution_authority: false,
    binary_content_verified: false, capacity: { history_used: 0, record_bytes: 1024 } } as CanvasViewRecord;
  const views = { create: vi.fn(async (..._args: unknown[]) => canvas), resolveImageNodeCreate: vi.fn(async (..._args: unknown[]) => canvas),
    list: vi.fn(), get: vi.fn(), history: vi.fn(), imageNodeResult: vi.fn() };
  const production = { list: vi.fn(async () => []), get: vi.fn(), create: vi.fn(), execute: vi.fn(), review: vi.fn() };
  const client = { overview: vi.fn(async () => ({ project: { id: owner.projectId, incarnation }, capabilities: { can_mutate: true } })),
    graphs: { canvasViews: views }, asset: vi.fn() };
  const props = { projectId: owner.projectId, node, owner, client, production, canMutate: true, canReview: true,
    isCurrent: () => true, read: async <T,>(work: () => Promise<T>) => work(), mutate: async <T,>(work: () => Promise<T>) => work() } as unknown as CanvasImageNodeTaskProps;
  return { props, canvas, views, client, production };
}
function seed(requestId = 'node-recovery-request') { return persistCanvasImageNodeCreateHint(owner, node.id, requestId, intent); }
async function dispatch(e: ReturnType<typeof fixture>) {
  fireEvent.click(screen.getByRole('button', { name: prepareLabel }));
  await waitFor(() => expect(e.views.create).toHaveBeenCalledOnce());
  await act(async () => {});
}
async function recover() {
  fireEvent.click(screen.getByRole('button', { name: resolveLabel }));
  await screen.findByText('Original production metadata panel');
}
beforeEach(() => { localStorage.clear(); panel = undefined; vi.stubGlobal('crypto', webcrypto); });
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('empty CanvasView create outcome recovery', () => {
  it('persists identity before the first POST, survives lost acknowledgement and explicitly cold-recovers without creating again', async () => {
    const first = fixture();
    first.views.create.mockImplementation(async (...args: unknown[]) => {
      const hint = readCanvasImageNodeCreateHint(owner, node.id);
      expect(hint.state).toBe('present');
      if (hint.state === 'present') {
        expect(hint.hint.request_id).toBe(args[1]); expect(hint.hint.intent).toEqual(args[2]);
      }
      throw new Error('Create acknowledgement lost after owner commit');
    });
    const view = render(<CanvasImageNodeTask {...first.props} />); await dispatch(first);
    const hint = readCanvasImageNodeCreateHint(owner, node.id); expect(hint.state).toBe('present');
    expect(screen.queryByText('Original production metadata panel')).toBeNull(); view.unmount();
    const reopened = fixture(); render(<CanvasImageNodeTask {...reopened.props} />);
    expect(reopened.client.overview).not.toHaveBeenCalled(); expect(reopened.views.resolveImageNodeCreate).not.toHaveBeenCalled();
    expect((screen.getByRole('button', { name: prepareLabel }) as HTMLButtonElement).disabled).toBe(true);
    await recover();
    expect(reopened.views.create).not.toHaveBeenCalled(); expect(reopened.views.resolveImageNodeCreate).toHaveBeenCalledOnce();
    expect(panel?.canvasNodeTask?.binding).toMatchObject({ canvas_id: first.canvas.id, node_id: node.id, incarnation });
    expect(reopened.production.create).not.toHaveBeenCalled(); expect(reopened.production.execute).not.toHaveBeenCalled(); expect(reopened.production.review).not.toHaveBeenCalled();
  });
  it.each([403, 404, 409])('keeps an explicit %s lookup failure unknown and does not recreate or guess from lists', async status => {
    seed(); const e = fixture(); e.views.resolveImageNodeCreate.mockRejectedValue(Object.assign(new Error('Explicit lookup refused'), { status }));
    render(<CanvasImageNodeTask {...e.props} />); const old = retained(screen.getByRole('button', { name: prepareLabel }));
    fireEvent.click(screen.getByRole('button', { name: resolveLabel })); await waitFor(() => expect(e.views.resolveImageNodeCreate).toHaveBeenCalledOnce());
    await act(async () => {}); act(() => old()); await act(async () => {});
    expect(e.views.create).not.toHaveBeenCalled(); expect(e.views.list).not.toHaveBeenCalled(); expect(e.production.list).not.toHaveBeenCalled();
    expect(screen.queryByText('Original production metadata panel')).toBeNull(); expect(readCanvasImageNodeCreateHint(owner, node.id).state).toBe('present');
  });
  it('does not dispatch when intent persistence is blocked, or overwrite a corrupt existing hint', async () => {
    const e = fixture(), save = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('Storage unavailable'); });
    const view = render(<CanvasImageNodeTask {...e.props} />); fireEvent.click(screen.getByRole('button', { name: prepareLabel }));
    await act(async () => {}); await waitFor(() => expect(save).toHaveBeenCalled()); expect(e.views.create).not.toHaveBeenCalled(); view.unmount();
    save.mockRestore(); const key = canvasImageNodeCreateHintKey(owner, node.id), broken = '{"schema_version":999}'; localStorage.setItem(key, broken);
    render(<CanvasImageNodeTask {...e.props} />); const blocked = screen.getByRole('button', { name: prepareLabel }) as HTMLButtonElement;
    expect(blocked.disabled).toBe(true); act(() => retained(blocked)()); await act(async () => {});
    expect(e.views.create).not.toHaveBeenCalled(); expect(localStorage.getItem(key)).toBe(broken);
  });
  it('retires delayed parent reads after client A/B/A and unmount without publishing recovered state', async () => {
    seed(); const e = fixture(); let invoke: (() => Promise<unknown>) | undefined;
    e.props.read = vi.fn(async work => { invoke = work; return new Promise<never>(() => {}); });
    const view = render(<CanvasImageNodeTask {...e.props} />);
    fireEvent.click(screen.getByRole('button', { name: resolveLabel })); await waitFor(() => expect(invoke).toBeDefined());
    view.rerender(<CanvasImageNodeTask {...e.props} client={{ ...e.props.client }} />); view.rerender(<CanvasImageNodeTask {...e.props} />);
    expect(() => invoke!()).toThrow(); expect(e.views.resolveImageNodeCreate).not.toHaveBeenCalled(); view.unmount();
    expect(() => invoke!()).toThrow(); expect(screen.queryByText('Original production metadata panel')).toBeNull();
  });
  it('serializes repeated reads and keeps retired preparation callbacks inert after explicit recovery', async () => {
    seed(); const e = fixture(); let finish!: (record: CanvasViewRecord) => void;
    e.views.resolveImageNodeCreate.mockReturnValue(new Promise(resolve => { finish = resolve; }));
    render(<StrictMode><CanvasImageNodeTask {...e.props} /></StrictMode>);
    const oldPrepare = retained(screen.getByRole('button', { name: prepareLabel })), oldResolve = retained(screen.getByRole('button', { name: resolveLabel }));
    act(() => { oldResolve(); oldResolve(); }); await waitFor(() => expect(e.views.resolveImageNodeCreate).toHaveBeenCalledOnce());
    await act(async () => finish(e.canvas)); await screen.findByText('Original production metadata panel');
    act(() => { oldPrepare(); oldResolve(); }); await act(async () => {});
    expect(e.views.create).not.toHaveBeenCalled(); expect(e.views.resolveImageNodeCreate).toHaveBeenCalledOnce();
  });
  it('refuses a changed current prompt rather than associating the stored old intent', async () => {
    seed(); const e = fixture(); render(<CanvasImageNodeTask {...e.props} node={{ ...node, prompt: 'A changed scene' }} />);
    fireEvent.click(screen.getByRole('button', { name: resolveLabel })); await act(async () => {});
    await waitFor(() => expect(e.client.overview).toHaveBeenCalled());
    expect(e.views.resolveImageNodeCreate).not.toHaveBeenCalled(); expect(e.views.create).not.toHaveBeenCalled(); expect(screen.queryByText('Original production metadata panel')).toBeNull();
  });
  it('retires recovered child callbacks when a different tab replaces the pending intent', async () => {
    const original = seed(); const e = fixture(); render(<CanvasImageNodeTask {...e.props} />); await recover();
    const oldPanel = panel!, binding = oldPanel.canvasNodeTask!.binding;
    const changed = JSON.stringify({ ...original.hint, request_id: 'other-tab-create-request' });
    const key = canvasImageNodeCreateHintKey(owner, node.id); localStorage.setItem(key, changed);
    act(() => window.dispatchEvent(new StorageEvent('storage', { key, oldValue: original.raw, newValue: changed })));
    const queued = { owner: 'image', id: 'software-queue-only', novel_id: owner.projectId, branch_id: null, version: 1,
      status: 'QUEUED', request_digest: 'b'.repeat(64), operation_id: 'm5.image.t2i', sources: [], provider: { local: true },
      command: { operation_id: 'm5.image.t2i', prompt: node.prompt, source_snapshots: [], allow_cloud: false, canvas_image_node: binding } } as unknown as ProductionJob;
    act(() => oldPanel.onJob?.(queued)); await act(async () => {});
    expect(localStorage.getItem(key)).toBe(changed); expect(e.views.create).not.toHaveBeenCalled();
    expect(e.production.create).not.toHaveBeenCalled(); expect(screen.queryByText('Original production metadata panel')).toBeNull();
  });
  it('keeps a newly revoked original read authority unknown without attempting the resolver', async () => {
    seed(); const e = fixture(); e.client.overview.mockRejectedValue(Object.assign(new Error('Read authority revoked'), { status: 403 }));
    render(<CanvasImageNodeTask {...e.props} />); fireEvent.click(screen.getByRole('button', { name: resolveLabel }));
    await waitFor(() => expect(e.client.overview).toHaveBeenCalledOnce()); await act(async () => {});
    expect(e.views.resolveImageNodeCreate).not.toHaveBeenCalled(); expect(e.views.create).not.toHaveBeenCalled();
    expect(readCanvasImageNodeCreateHint(owner, node.id).state).toBe('present'); expect(screen.queryByText('Original production metadata panel')).toBeNull();
  });
  it('does not resume a queue-capable association after a fresh overview revokes write permission', async () => {
    seed(); const e = fixture(); e.client.overview.mockResolvedValue({ project: { id: owner.projectId, incarnation }, capabilities: { can_mutate: false } });
    render(<CanvasImageNodeTask {...e.props} />); fireEvent.click(screen.getByRole('button', { name: resolveLabel }));
    await waitFor(() => expect(e.client.overview).toHaveBeenCalledOnce()); await act(async () => {});
    expect(e.views.resolveImageNodeCreate).not.toHaveBeenCalled(); expect(e.views.create).not.toHaveBeenCalled();
    expect(readCanvasImageNodeCreateHint(owner, node.id).state).toBe('present'); expect(screen.queryByText('Original production metadata panel')).toBeNull();
  });
  it.each(['other-request', 'corrupt'])('does not adopt a %s marker installed during its first persistence readback', async kind => {
    const e = fixture(), key = canvasImageNodeCreateHintKey(owner, node.id), originalSet = Storage.prototype.setItem;
    let replacement = '';
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function(this: Storage, changedKey: string, raw: string) {
      if (changedKey === key) {
        replacement = kind === 'corrupt' ? '{"schema_version":1}' : JSON.stringify({ ...JSON.parse(raw), request_id: 'other-tab-request' });
        return originalSet.call(this, changedKey, replacement);
      }
      return originalSet.call(this, changedKey, raw);
    });
    render(<CanvasImageNodeTask {...e.props} />); const old = retained(screen.getByRole('button', { name: prepareLabel }));
    fireEvent.click(screen.getByRole('button', { name: prepareLabel }));
    await waitFor(() => expect(replacement).not.toBe('')); await act(async () => {});
    const resolve = screen.queryByRole('button', { name: resolveLabel }); act(() => { old(); if (resolve) retained(resolve)(); }); await act(async () => {});
    expect(e.views.create).not.toHaveBeenCalled(); expect(e.views.resolveImageNodeCreate).not.toHaveBeenCalled();
    expect(localStorage.getItem(key)).toBe(replacement); expect(screen.queryByText('Original production metadata panel')).toBeNull();
  });
  it('drops a late create acknowledgement after timeout and a not-found lookup until another explicit read', async () => {
    const e = fixture(); let acknowledge!: (record: CanvasViewRecord) => void;
    e.views.create.mockReturnValue(new Promise(resolve => { acknowledge = resolve; }));
    render(<CanvasImageNodeTask {...e.props} />); vi.useFakeTimers();
    fireEvent.click(screen.getByRole('button', { name: prepareLabel })); await vi.waitFor(() => expect(e.views.create).toHaveBeenCalledOnce());
    await act(async () => vi.advanceTimersByTimeAsync(15_001));
    e.views.resolveImageNodeCreate.mockRejectedValueOnce(new Error('Not committed at read snapshot'));
    fireEvent.click(screen.getByRole('button', { name: resolveLabel })); await vi.waitFor(() => expect(e.views.resolveImageNodeCreate).toHaveBeenCalledOnce());
    await act(async () => acknowledge(e.canvas));
    expect(screen.queryByText('Original production metadata panel')).toBeNull(); expect(e.views.create).toHaveBeenCalledOnce();
    e.views.resolveImageNodeCreate.mockResolvedValue(e.canvas); fireEvent.click(screen.getByRole('button', { name: resolveLabel }));
    await vi.waitFor(() => expect(screen.queryByText('Original production metadata panel')).not.toBeNull());
    expect(e.views.create).toHaveBeenCalledOnce(); expect(e.views.resolveImageNodeCreate).toHaveBeenCalledTimes(2);
  });
});
