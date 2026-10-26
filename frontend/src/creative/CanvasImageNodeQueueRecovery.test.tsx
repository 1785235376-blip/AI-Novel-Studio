// @vitest-environment jsdom
/** Software HTTP owner projections through the real node, panel and clients.
 * These tests never execute, review, inspect or fetch candidate media. */
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createHash, webcrypto } from 'node:crypto';
import { StrictMode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CanvasImageNodeTask, type CanvasImageNodeTaskProps } from './CanvasImageNodeTask';
import { studioClient } from './studioClient';
import { studioProductionClient, type MediaCommand, type ProductionJob, type ProductionProvider } from './studioProductionClient';
import { canonicalImageNode } from './canvasImageNode';
import { readCanvasImageNodeCreateHint } from './canvasImageNodeCreateIntent';
import { canvasImageNodeQueueHintKey, persistCanvasImageNodeQueueHint, readCanvasImageNodeQueueHint } from './canvasImageNodeQueueIntent';

const sha = (value: string) => createHash('sha256').update(value).digest('hex');
const owner = { projectId: 'queue-recover-project', incarnation: 'file:12345678-1234-4234-8234-123456789abc', actorId: 'queue-recover-author',
  actorWorkspaceId: '', mode: 'local' as const, workspaceId: '', storylineId: '', branchId: '' };
const node = { id: 'queue-recover-node', title: 'One original node', prompt: 'A lighthouse for one original request', x: 24, y: 48 };
const base = `/api/projects/${owner.projectId}/studio`, productionBase = base + '/production', canvasId = 'the-original-canvas';
const provider: ProductionProvider = { operation_id: 'm5.image.t2i', provider_id: 'software-local-image', model_id: 'software-model', local: true,
  route_digest: 'b'.repeat(64), capability: 'TEXT_TO_IMAGE', supported_parameters: ['steps', 'seed'], readiness: 'CONFIGURED_NOT_VERIFIED' };
const overview = { project: { id: owner.projectId, title: 'Software recovery fixture', entry_kind: 'NEUTRAL_STUDIO', incarnation: owner.incarnation },
  preferences: { version: 1, intents: ['IMAGE_DESIGN'], preset: 'IMAGE', custom_intent: '' }, capabilities: { manual_import: true, manual_export: true,
    can_mutate: true, can_review: true, model_required: false, chapter_required: false, media_validator_configured: true, asset_kinds: ['image'], intent_is_permission: false } };
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
const definition = () => ({ schema_version: 1, title: node.title, cards: [], viewport: { x: 0, y: 0, zoom: 1 } });
const canvas = () => ({ project_id: owner.projectId, scope: { mode: 'local' as const, novel_id: owner.projectId }, id: canvasId, version: 1,
  definition: definition(), definition_digest: sha(canonicalImageNode(definition())), reference_states: [], created_at: '2026-10-24', updated_at: '2026-10-24',
  execution_authority: false, binary_content_verified: false, capacity: { history_used: 0, record_bytes: 2048 } });
const recipe = (command: MediaCommand) => ({ contract: 'studio-execution-recipe/1', operation_id: command.operation_id, adapter: 'AUTOMATIC1111_IMAGE',
  parameters: command.parameters, automatic_fallback: false, recipe_digest: sha('software-recipe:' + JSON.stringify(command.parameters)) });
function queued(command: MediaCommand): ProductionJob {
  return { contract: 'studio-production-job/1', owner: 'image', id: 'the-original-queued-job', novel_id: owner.projectId, branch_id: null, version: 1,
    status: 'QUEUED', operation_id: command.operation_id, request_id: command.request_id, request_digest: sha(JSON.stringify(command)), receipt_digest: null,
    output_candidate: null, timeline_snapshot: null, sources: [], command, provider: { provider_id: provider.provider_id, model_id: provider.model_id,
      local: true, route_digest: provider.route_digest }, execution_recipe: recipe(command), approved_asset_version: null,
    created_at: '2026-10-24T00:00:00Z', updated_at: '2026-10-24T00:00:00Z', product_acceptance: 'LOCAL_REQUIRED', automatic_replay: false,
    remote_compute_may_continue: false } as ProductionJob;
}
function retained(button: HTMLElement) { const key = Object.keys(button).find(key => key.startsWith('__reactProps$'))!;
  return (button as unknown as Record<string, { onClick: () => void }>)[key].onClick; }
let props: CanvasImageNodeTaskProps, fetcher: ReturnType<typeof vi.fn>, original: ProductionJob | undefined, createBody: any;
let acknowledgeQueue: (job: ProductionJob) => Promise<Response>, resolveQueue: (body: any) => Promise<Response>;
const posts = (suffix: string) => fetcher.mock.calls.filter(([url, init]) => url.endsWith(suffix) && init?.method === 'POST');
beforeEach(() => {
  localStorage.clear(); vi.stubGlobal('crypto', webcrypto); original = undefined; createBody = undefined;
  const context = { sessionToken: '', localHostToken: 'synthetic-queue-recovery-host' };
  props = { projectId: owner.projectId, node, owner, client: studioClient(owner.projectId, context), production: studioProductionClient(owner.projectId, context),
    canMutate: true, canReview: true, isCurrent: () => true, read: work => work(), mutate: work => work() };
  acknowledgeQueue = async () => { throw new Error('Queue acknowledgement lost after the declared software owner commit'); };
  resolveQueue = async body => {
    if (!original) return json({ detail: { code: 'STUDIO_CANVAS_IMAGE_NODE_QUEUE_NOT_FOUND' } }, 404);
    expect(body).toEqual({ request_id: original.request_id, request_digest: original.request_digest, canvas_image_node: original.command!.canvas_image_node });
    return json(original);
  };
  fetcher = vi.fn(async (url: string, init: RequestInit = {}) => {
    const body = init.body ? JSON.parse(String(init.body)) : undefined;
    if (url === base && (!init.method || init.method === 'GET')) return json(overview);
    if (url === base + '/canvas-views' && init.method === 'POST') { createBody = body; return json(canvas(), 201); }
    if (url === base + '/canvas-views/resolve-create') return json({ contract: 'studio-canvas-image-node-resolve/1', request_id: createBody.request_id,
      image_node_intent: createBody.image_node_intent, incarnation: owner.incarnation, canvas: canvas() });
    if (url === `${base}/canvas-views/${canvasId}`) return json(canvas());
    if (url === `${base}/canvas-views/${canvasId}/history`) return json({ project_id: owner.projectId, scope: canvas().scope, id: canvasId,
      incarnation: owner.incarnation, current_version: 1, current_definition_digest: canvas().definition_digest, items: [{ version: 1, definition: definition(),
        definition_digest: canvas().definition_digest, reference_states: [], created_at: '2026-10-24', updated_at: '2026-10-24', can_restore: false }],
      restore_policy: 'CURRENT_METADATA_ONLY', execution_authority: false, binary_content_verified: false });
    if (url === productionBase + '/providers') return json({ items: [provider], health_probed: false, credentials_read: false });
    if (url === productionBase + '/preview') return json({ contract: 'studio-production-preview/1', novel_id: owner.projectId, branch_id: null,
      request_id: body.request_id, operation_id: body.operation_id, request_digest: sha(JSON.stringify(body)), preview_digest: sha('preview:' + JSON.stringify(body)),
      command: body, provider: { provider_id: provider.provider_id, model_id: provider.model_id, local: true, route_digest: provider.route_digest }, sources: [],
      execution_recipe: recipe(body), product_acceptance: 'LOCAL_REQUIRED', execution_available: true, automatic_dispatch: false,
      output_policy: 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW' });
    if (url === productionBase + '/jobs' && init.method === 'POST') {
      original = queued(body.command);
      const hint = readCanvasImageNodeQueueHint(owner, node.id); expect(hint.state).toBe('present');
      if (hint.state === 'present') {
        expect(hint.hint.request_id).toBe(original.request_id); expect(hint.hint.request_digest).toBe(original.request_digest);
        expect(hint.hint.binding).toEqual(original.command!.canvas_image_node);
      }
      return acknowledgeQueue(original);
    }
    if (url === productionBase + '/jobs/image/resolve-create') return resolveQueue(body);
    if (url === productionBase + '/jobs' && (!init.method || init.method === 'GET')) return json({ items: original ? [original] : [], product_acceptance: 'LOCAL_REQUIRED' });
    if (url === productionBase + '/jobs/image/the-original-queued-job' && original) return json(original);
    throw new Error('Unexpected software request; execute, review and media are forbidden: ' + url);
  }); vi.stubGlobal('fetch', fetcher);
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
async function prepareDraft() {
  const view = render(<CanvasImageNodeTask {...props} />);
  fireEvent.click(screen.getByRole('button', { name: '为此节点保存正式空白位置' }));
  const picker = await screen.findByLabelText('服务商与模型') as HTMLSelectElement;
  const configurations = screen.getByRole('button', { name: '重新读取配置' }) as HTMLButtonElement;
  await waitFor(() => expect(configurations.disabled).toBe(false));
  if (picker.options.length === 1) fireEvent.click(configurations);
  await waitFor(() => expect(picker.options.length).toBe(2)); fireEvent.change(picker, { target: { value: picker.options[1].value } });
  fireEvent.change(screen.getByLabelText('采样步数（1–150）'), { target: { value: '31' } });
  fireEvent.change(screen.getByLabelText('种子（0–2147483647）'), { target: { value: '71' } });
  fireEvent.click(screen.getByRole('button', { name: '读取制作预览' })); await screen.findByRole('region', { name: '制作预览确认' });
  fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界'));
  const impact = screen.getByLabelText('已核对本次输入变化与影响范围') as HTMLInputElement;
  await waitFor(() => expect(impact.disabled).toBe(false)); fireEvent.click(impact); fireEvent.click(screen.getByRole('button', { name: '确认本次输入核对' }));
  const create = screen.getByRole('button', { name: '仅创建任务并入队' }); await waitFor(() => expect((create as HTMLButtonElement).disabled).toBe(false));
  return { view, create, oldCreate: retained(create) };
}
async function prepareAndQueue(beforeQueue?: () => void) {
  const result = await prepareDraft(); beforeQueue?.(); fireEvent.click(result.create); await act(async () => {});
  expect(posts('/production/jobs')).toHaveLength(1); return result;
}
function seedPendingQueue() {
  const command: MediaCommand = { operation_id: 'm5.image.t2i', request_id: 'pending-original-queue', provider_id: provider.provider_id,
    model_id: provider.model_id, prompt: node.prompt, parameters: { steps: 31, seed: 71 }, source_snapshots: [], allow_cloud: false, license_note: '',
    canvas_image_node: { contract: 'studio-canvas-image-node/1', project_id: owner.projectId, scope: canvas().scope, incarnation: owner.incarnation,
      canvas_id: canvasId, canvas_version: 1, canvas_digest: canvas().definition_digest, node_id: node.id, title: node.title,
      position: { x: node.x, y: node.y }, prompt_digest: sha(node.prompt) } };
  original = queued(command); return persistCanvasImageNodeQueueHint(owner, node.id, original.request_id, original.request_digest, command.canvas_image_node!);
}

describe('formal single-node queue UNKNOWN recovery', () => {
  it('recovers the exact original queued request after cold remount through the real node, panel and HTTP clients', async () => {
    const first = await prepareAndQueue(); await waitFor(() => expect(readCanvasImageNodeQueueHint(owner, node.id).state).toBe('present')); expect(original).toBeDefined();
    first.view.unmount(); const before = fetcher.mock.calls.length;
    render(<StrictMode><CanvasImageNodeTask {...props} /></StrictMode>); await act(async () => {});
    expect(fetcher.mock.calls).toHaveLength(before);
    expect(posts('/production/jobs')).toHaveLength(1);
    // The concrete recovery control is supplied by the original production flow.
    const recover = await screen.findByRole('button', { name: /核对.*入队|读取.*入队.*请求|恢复.*入队/ });
    fireEvent.click(recover); await screen.findByRole('button', { name: '明确执行当前入队任务' });
    expect(posts('/production/jobs/image/resolve-create')).toHaveLength(1); expect(posts('/production/jobs')).toHaveLength(1);
    expect(posts('/execute')).toHaveLength(0); expect(posts('/review')).toHaveLength(0);
    expect((screen.getByRole('button', { name: '明确执行当前入队任务' }) as HTMLButtonElement).disabled).toBe(true);
    expect(readCanvasImageNodeCreateHint(owner, node.id).state).toBe('absent');
  });
  it.each([403, 404, 409])('keeps %s lookup unknown and never guesses another queue row or recreates', async status => {
    seedPendingQueue(); resolveQueue = async () => json({ detail: { code: 'STUDIO_QUEUE_LOOKUP_REFUSED' } }, status);
    render(<CanvasImageNodeTask {...props} />); const prepare = retained(screen.getByRole('button', { name: '为此节点保存正式空白位置' }));
    const recover = screen.getByRole('button', { name: /核对.*入队|读取.*入队.*请求|恢复.*入队/ });
    expect(fetcher).not.toHaveBeenCalled(); fireEvent.click(recover);
    await waitFor(() => expect(posts('/production/jobs/image/resolve-create')).toHaveLength(1)); await act(async () => {});
    act(() => prepare()); await act(async () => {});
    expect(posts('/production/jobs')).toHaveLength(0); expect(posts('/canvas-views')).toHaveLength(0);
    expect(fetcher.mock.calls.some(([url]) => url === productionBase + '/jobs')).toBe(false);
    expect(readCanvasImageNodeQueueHint(owner, node.id).state).toBe('present');
    expect(screen.queryByRole('button', { name: '明确执行当前入队任务' })).toBeNull();
  });
  it('retires a parent-deferred lookup across client A/B/A and unmount before actual dispatch', async () => {
    seedPendingQueue(); let invoke: (() => Promise<unknown>) | undefined;
    props.read = vi.fn(async work => { invoke = work; return new Promise<never>(() => {}); });
    const view = render(<CanvasImageNodeTask {...props} />);
    fireEvent.click(screen.getByRole('button', { name: /核对.*入队|读取.*入队.*请求|恢复.*入队/ }));
    await waitFor(() => expect(invoke).toBeDefined());
    view.rerender(<CanvasImageNodeTask {...props} client={{ ...props.client }} />); view.rerender(<CanvasImageNodeTask {...props} />);
    expect(() => invoke!()).toThrow(); view.unmount(); expect(() => invoke!()).toThrow();
    expect(posts('/production/jobs/image/resolve-create')).toHaveLength(0); expect(posts('/production/jobs')).toHaveLength(0);
  });
  it('serializes repeated explicit recovery and retires old creation callbacks under StrictMode', async () => {
    seedPendingQueue(); let finish!: (value: Response) => void; resolveQueue = () => new Promise(resolve => { finish = resolve; });
    render(<StrictMode><CanvasImageNodeTask {...props} /></StrictMode>);
    const prepare = retained(screen.getByRole('button', { name: '为此节点保存正式空白位置' }));
    const recover = retained(screen.getByRole('button', { name: /核对.*入队|读取.*入队.*请求|恢复.*入队/ }));
    act(() => { recover(); recover(); }); await waitFor(() => expect(finish).toBeDefined());
    expect(posts('/production/jobs/image/resolve-create')).toHaveLength(1);
    await act(async () => finish(json(original))); await screen.findByRole('button', { name: '明确执行当前入队任务' });
    await act(async () => { recover(); prepare(); });
    expect(posts('/production/jobs/image/resolve-create')).toHaveLength(1); expect(posts('/production/jobs')).toHaveLength(0);
  });
  it('blocks queue dispatch when its durable intent cannot be written and read back', async () => {
    const ready = await prepareDraft(), key = canvasImageNodeQueueHintKey(owner, node.id), native = Storage.prototype.setItem;
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function(this: Storage, name, value) {
      if (name === key) throw new Error('Queue hint storage denied'); native.call(this, name, value);
    });
    fireEvent.click(ready.create); await act(async () => {});
    expect(posts('/production/jobs')).toHaveLength(0); expect(posts('/execute')).toHaveLength(0); expect(posts('/review')).toHaveLength(0);
  });
  it('keeps a corrupt cold queue hint intact and blocks both canvas creation and queueing', async () => {
    const key = canvasImageNodeQueueHintKey(owner, node.id), raw = '{"schema_version":999}'; localStorage.setItem(key, raw);
    render(<CanvasImageNodeTask {...props} />);
    const create = screen.getByRole('button', { name: '为此节点保存正式空白位置' }) as HTMLButtonElement;
    expect(create.disabled).toBe(true); await act(async () => retained(create)());
    expect(fetcher).not.toHaveBeenCalled(); expect(localStorage.getItem(key)).toBe(raw);
    expect(posts('/production/jobs')).toHaveLength(0); expect(posts('/canvas-views')).toHaveLength(0);
  });
  it.each(['foreign', 'corrupt'])('does not substitute a %s partial queue-hint readback for the intended request', async kind => {
    const ready = await prepareDraft(), key = canvasImageNodeQueueHintKey(owner, node.id), native = Storage.prototype.setItem;
    let replacement = '';
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function(this: Storage, name, value) {
      if (name === key) {
        const marker = JSON.parse(value); marker.request_id = 'other-window-request';
        replacement = kind === 'foreign' ? canonicalImageNode(marker) : '{broken-after-partial-write';
        native.call(this, name, replacement); return;
      }
      native.call(this, name, value);
    });
    fireEvent.click(ready.create); await act(async () => {});
    expect(posts('/production/jobs')).toHaveLength(0); expect(localStorage.getItem(key)).toBe(replacement);
    expect(screen.queryByRole('button', { name: /核对.*入队|读取.*入队.*请求|恢复.*入队/ })).toBeNull();
    await act(async () => ready.oldCreate());
    expect(posts('/production/jobs')).toHaveLength(0); expect(posts('/production/jobs/image/resolve-create')).toHaveLength(0);
  });
  it('ignores a timed-out create acknowledgement after a not-found lookup until another explicit read', async () => {
    let finish!: (value: Response) => void; acknowledgeQueue = () => new Promise(resolve => { finish = resolve; });
    const first = await prepareAndQueue(() => vi.useFakeTimers());
    await act(async () => { await vi.advanceTimersByTimeAsync(15001); }); vi.useRealTimers();
    let reads = 0; resolveQueue = async () => ++reads === 1 ? json({ detail: { code: 'STUDIO_QUEUE_NOT_FOUND' } }, 404) : json(original);
    fireEvent.click(screen.getByRole('button', { name: /核对.*入队|读取.*入队.*请求|恢复.*入队/ }));
    await waitFor(() => expect(reads).toBe(1)); await act(async () => {});
    await act(async () => finish(json(original)));
    expect(screen.queryByRole('button', { name: '明确执行当前入队任务' })).toBeNull();
    await act(async () => first.oldCreate()); expect(posts('/production/jobs')).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: /核对.*入队|读取.*入队.*请求|恢复.*入队/ }));
    await screen.findByRole('button', { name: '明确执行当前入队任务' });
    expect(posts('/production/jobs/image/resolve-create')).toHaveLength(2); expect(posts('/production/jobs')).toHaveLength(1);
    expect(posts('/execute')).toHaveLength(0); expect(posts('/review')).toHaveLength(0);
  });
});
