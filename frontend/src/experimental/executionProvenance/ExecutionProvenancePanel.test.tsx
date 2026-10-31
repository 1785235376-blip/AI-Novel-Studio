// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api';
import type { StudioAsset } from '../../creative/studioClient';
import { studioProductionClient, type ProductionJob } from '../../creative/studioProductionClient';
import { cutoutJob, cutoutProject } from '../../creative/studioCpuCutout.testFixtures';
import { useLocalHostSession } from '../../localHostSession';
import { ExecutionProvenancePanel, type ExecutionProvenanceProps } from './ExecutionProvenancePanel';

const a = 'a'.repeat(64), b = 'b'.repeat(64), c = 'c'.repeat(64);
function job(patch: Partial<ProductionJob> = {}): ProductionJob {
  const sources = [{ id: 'input-original', kind: 'ASSET' as const, asset_kind: 'image' as const, version: 7, digest: b }];
  return { contract: 'studio-production-job/1', owner: 'image', id: 'job-original', novel_id: 'project-a', branch_id: 'branch-a', version: 3,
    operation_id: 'm5.image.i2i', request_id: 'request-original', status: 'AWAITING_REVIEW', request_digest: a, receipt_digest: b,
    output_candidate: { id: 'candidate-original', version: 1, digest: c, kind: 'image' },
    product_acceptance: 'LOCAL_REQUIRED', automatic_replay: false, remote_compute_may_continue: false, timeline_snapshot: null, sources,
    command: { operation_id: 'm5.image.i2i', request_id: 'request-original', provider_id: 'provider-original', model_id: 'model-original',
      prompt: 'private-prompt-secret', parameters: { steps: 33, seed: 100, denoising_strength: 0.6 }, source_snapshots: sources, allow_cloud: false, license_note: 'private-license-secret' },
    provider: { provider_id: 'provider-original', model_id: 'model-original', local: true, route_digest: a },
    execution_recipe: { contract: 'studio-execution-recipe/1', operation_id: 'm5.image.i2i', adapter: 'COMFYUI_BUILTIN_IMAGE', recipe_digest: b, automatic_fallback: false },
    approved_asset_version: null, created_at: '2026-10-20T00:00:00Z', updated_at: '2026-10-20T00:00:00Z', ...patch };
}
function asset(patch: Partial<StudioAsset> = {}): StudioAsset {
  return { id: 'candidate-original', novel_id: 'project-a', branch_id: 'branch-a', version: 2, sha256: c, kind: 'image',
    filename: 'result.png', media_type: 'image/png', size: 10, created_at: '', updated_at: '', ...patch };
}
function props(patch: Partial<ExecutionProvenanceProps> = {}): ExecutionProvenanceProps {
  const original = job();
  return { selection: { projectId: original.novel_id, branchId: original.branch_id, identity: 'session-a', job: {
    owner: original.owner, id: original.id, version: original.version, request_id: original.request_id, request_digest: original.request_digest } },
    production: { get: vi.fn().mockResolvedValue(original) }, assets: { asset: vi.fn().mockResolvedValue(asset()) },
    active: true, denied: false, busy: false, isCurrent: () => true, read: work => work(), onUnavailable: vi.fn(), ...patch };
}
function mount(patch: Partial<ExecutionProvenanceProps> = {}) {
  const original = props(patch), view = render(<ExecutionProvenancePanel {...original} />);
  return { original, ...view };
}
const button = (name = '读取执行来源') => screen.getByRole('button', { name }) as HTMLButtonElement;
async function load() { fireEvent.click(button()); await screen.findByText('request-original'); }
const deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes; }); return { resolve, promise }; };
function retainedClick(element: HTMLElement): () => void {
  const key = Object.keys(element).find(name => name.startsWith('__reactProps$'))!;
  return (element as unknown as Record<string, { onClick: () => void }>)[key].onClick;
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('independent original Job provenance panel', () => {
  it('waits for explicit read, preserves actual identity/input pins and never calls writes', async () => {
    const writes = { execute: vi.fn(), refresh: vi.fn(), review: vi.fn(), reconcile: vi.fn(), cancel: vi.fn(), create: vi.fn() };
    const get = vi.fn().mockResolvedValue(job()), state = mount({ production: { get, ...writes } });
    expect(get).not.toHaveBeenCalled();
    expect(screen.getByText('尚未读取执行来源')).toBeTruthy();
    await load();
    expect(get).toHaveBeenCalledWith('image', 'job-original', expect.any(AbortSignal));
    expect(screen.getByText('job-original')).toBeTruthy();
    expect(screen.getByText('provider-original')).toBeTruthy();
    expect(screen.getByText('model-original')).toBeTruthy();
    const pins = screen.getByRole('list', { name: '执行时输入快照' });
    expect(pins.textContent).toContain('input-original'); expect(pins.textContent).toContain('v7'); expect(pins.textContent).toContain(b);
    expect(screen.getByRole('list', { name: '执行时输入快照' }).textContent).not.toContain('result.png');
    expect(screen.getByLabelText('记录的执行参数').textContent).toContain('steps33');
    expect(Object.values(writes).every(write => write.mock.calls.length === 0)).toBe(true);
    expect(state.original.assets!.asset).not.toHaveBeenCalled();
  });

  it('uses the original scoped client and only GETs the exact original URL', async () => {
    useLocalHostSession.setState({ token: '', actorId: '' });
    const value = cutoutJob('UNKNOWN', 3), fetcher = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => structuredClone(value) });
    vi.stubGlobal('fetch', fetcher);
    mount({ selection: { projectId: cutoutProject, branchId: null, identity: 'local-reader', job: value },
      production: studioProductionClient(cutoutProject, { sessionToken: '', localHostToken: '' }) });
    expect(fetcher).not.toHaveBeenCalled(); fireEvent.click(button());
    await screen.findByText('cutout-request');
    expect(fetcher.mock.calls).toHaveLength(1);
    expect(fetcher.mock.calls[0][0]).toBe(`/api/projects/${cutoutProject}/studio/production/jobs/image/cutout-job`);
    expect(fetcher.mock.calls[0][1].method).toBe('GET');
    expect(screen.getByText(/禁止重放/)).toBeTruthy();
  });

  it.each([
    ['STUDIO_IMAGE_CUTOUT_FAILED', true], ['UNKNOWN_PUBLIC_LOOKING_CODE', false],
    ['STUDIO_IMAGE_DYNAMIC_ERROR', false], ['SK_SECRET_PROBE_123456', false],
    ['Authorization: Bearer synthetic-error', false],
  ] as const)('error-code display through the original decoder handles %s', async (errorCode, visible) => {
    useLocalHostSession.setState({ token: '', actorId: '' });
    const value = { ...cutoutJob('UNKNOWN', 3), error_code: errorCode };
    const fetcher = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => structuredClone(value) });
    vi.stubGlobal('fetch', fetcher);
    mount({ selection: { projectId: cutoutProject, branchId: null, identity: 'local-reader', job: value },
      production: studioProductionClient(cutoutProject, { sessionToken: '', localHostToken: '' }) });
    fireEvent.click(button()); await screen.findByText('cutout-request');
    expect(fetcher.mock.calls).toHaveLength(1);
    expect(fetcher.mock.calls[0][1].method).toBe('GET');
    if (visible) expect(screen.getByText(errorCode)).toBeTruthy();
    else {
      expect(document.body.textContent).not.toContain(errorCode);
      expect(screen.getByText('未提供可显示的错误代码')).toBeTruthy();
    }
  });

  it.each(['UNKNOWN', 'FAILED', 'CANCELLED'] as const)('%s exposes no retry/replay/review/execute action', async status => {
    const state = mount({ production: { get: vi.fn().mockResolvedValue(job({ status, remote_compute_may_continue: true })) } });
    await load();
    expect(screen.getAllByRole('button').map(row => row.textContent)).toEqual(['重新读取执行来源']);
    expect(screen.getByText(/本地状态不代表远端已经停止/)).toBeTruthy();
    fireEvent.click(button('重新读取执行来源')); await screen.findByText('request-original');
    expect(state.original.production.get).toHaveBeenCalledTimes(2);
  });

  it('does not fetch a private unreviewed candidate as a formal asset or infer adoption', async () => {
    const state = mount(); await load();
    expect(state.original.assets!.asset).not.toHaveBeenCalled();
    expect(screen.getByText(/没有可核验的正式审核版本/)).toBeTruthy();
    expect(screen.queryByText(/已核验正式资产/)).toBeNull();
    expect(screen.getByText(/未提供持久的采用回执/)).toBeTruthy();
  });

  it('keeps candidate v1 separate from original approved asset v2 and never claims canvas adoption', async () => {
    mount({ production: { get: vi.fn().mockResolvedValue(job({ status: 'APPROVED', approved_asset_version: 2 })) } });
    await load();
    expect(screen.getByText(/原候选/).textContent).toContain('候选 v1');
    expect(screen.getByText(/已核验正式资产/).textContent).toContain('v2');
    expect(screen.getByText(/未提供持久的采用回执/)).toBeTruthy();
  });

  it.each([
    ['newer current asset', { version: 3 }], ['changed bytes', { sha256: a }], ['foreign project', { novel_id: 'foreign' }],
    ['foreign branch', { branch_id: 'foreign' }], ['deleted asset', { deleted_at: '2026-10-20T01:00:00Z' }],
  ])('does not replace the original approved version with %s', async (_name, patch) => {
    mount({ production: { get: vi.fn().mockResolvedValue(job({ status: 'APPROVED', approved_asset_version: 2 })) }, assets: { asset: vi.fn().mockResolvedValue(asset(patch)) } });
    await load();
    expect(screen.getByText(/正式资产版本或摘要已变化/)).toBeTruthy();
    expect(screen.queryByText(/已核验正式资产/)).toBeNull();
    expect(screen.getByText(/原候选/).textContent).toContain(c);
  });

  it('withholds inaccessible formal metadata but retains the readable Job candidate', async () => {
    mount({ production: { get: vi.fn().mockResolvedValue(job({ status: 'APPROVED', approved_asset_version: 2 })) },
      assets: { asset: vi.fn().mockRejectedValue(new ApiError({ status: 403, code: 'FORBIDDEN', message: 'Bearer private-asset-secret' })) } });
    await load();
    expect(screen.getByText(/正式资产不可读/)).toBeTruthy(); expect(screen.queryByText(/private-asset-secret/)).toBeNull();
    expect(screen.queryByText(/已核验正式资产/)).toBeNull();
  });

  it('drops credential, free-text, workflow and raw error data from rendered diagnostics', async () => {
    const value = job(); value.command!.parameters = { steps: 33, quality: 'Bearer quality-secret', width: 'sk-width-secret', token: 'sk-token-secret' };
    value.execution_recipe.workflow = { fake: { class_type: 'FakeCloudNode-secret', api_key: 'workflow-secret' } };
    value.provider!.local = false; value.execution_recipe.adapter = 'ORIGINAL_HTTP_PROVIDER'; value.error_code = 'Bearer error-secret';
    mount({ production: { get: vi.fn().mockResolvedValue(value) } }); await load();
    expect(document.body.textContent).not.toMatch(/private-prompt-secret|private-license-secret|quality-secret|width-secret|token-secret|workflow-secret|error-secret|FakeCloudNode/);
    expect(screen.getByText(/云端内部节点不可见/)).toBeTruthy();
  });

  it.each([
    ['project', { novel_id: 'foreign-project' }], ['branch', { branch_id: 'foreign-branch' }], ['request', { request_id: 'foreign-request' }],
    ['digest', { request_digest: c }], ['owner', { owner: 'video' }], ['job', { id: 'foreign-job' }], ['rollback', { version: 2 }],
  ] as const)('rejects a mismatched %s receipt before showing identities', async (_label, patch) => {
    mount({ production: { get: vi.fn().mockResolvedValue(job(patch as Partial<ProductionJob>)) } }); fireEvent.click(button());
    await screen.findByRole('alert'); expect(screen.queryByText('request-original')).toBeNull(); expect(document.body.textContent).not.toMatch(/foreign-/);
  });

  it('revokes reading after 403 without exposing raw provider error or silently retrying', async () => {
    const get = vi.fn().mockRejectedValue(new ApiError({ status: 403, code: 'FORBIDDEN', message: 'https://provider/?api_key=private-secret' }));
    const state = mount({ production: { get } }); fireEvent.click(button());
    await screen.findByRole('alert'); expect(button().disabled).toBe(true); expect(state.original.onUnavailable).toHaveBeenCalledOnce();
    expect(document.body.textContent).not.toContain('private-secret');
    state.rerender(<ExecutionProvenancePanel {...state.original} busy />); state.rerender(<ExecutionProvenancePanel {...state.original} />);
    fireEvent.click(button()); expect(get).toHaveBeenCalledTimes(1);
  });

  it.each(['active', 'denied', 'busy', 'current'] as const)('blocks reads when %s makes the host unavailable', key => {
    const state = mount(key === 'current' ? { isCurrent: () => false } : { [key]: key !== 'active' });
    expect(button().disabled).toBe(true); fireEvent.click(button()); expect(state.original.production.get).not.toHaveBeenCalled();
  });

  it.each(['project', 'branch', 'identity', 'client', 'active', 'denied', 'busy', 'current'] as const)('discards a late GET after %s changes, including scope ABA', async field => {
    const pending = deferred<ProductionJob>(), get = vi.fn().mockReturnValue(pending.promise), state = mount({ production: { get } });
    const oldClick = retainedClick(button()); fireEvent.click(button()); expect(get).toHaveBeenCalledOnce();
    const changed: ExecutionProvenanceProps = { ...state.original };
    if (field === 'project') changed.selection = { ...changed.selection, projectId: 'project-b' };
    if (field === 'branch') changed.selection = { ...changed.selection, branchId: 'branch-b' };
    if (field === 'identity') changed.selection = { ...changed.selection, identity: 'session-b' };
    if (field === 'client') changed.production = { get: vi.fn().mockResolvedValue(job()) };
    if (field === 'active') changed.active = false;
    if (field === 'denied') changed.denied = true;
    if (field === 'busy') changed.busy = true;
    if (field === 'current') changed.isCurrent = () => false;
    state.rerender(<ExecutionProvenancePanel {...changed} />); state.rerender(<ExecutionProvenancePanel {...state.original} />);
    await act(async () => { oldClick(); pending.resolve(job()); await pending.promise; });
    expect(get).toHaveBeenCalledOnce(); expect(screen.queryByText('request-original')).toBeNull(); expect(button().disabled).toBe(false);
  });

  it('drops a late formal asset response on identity change and does not expose metadata', async () => {
    const pending = deferred<StudioAsset>(), state = mount({ production: { get: vi.fn().mockResolvedValue(job({ status: 'APPROVED', approved_asset_version: 2 })) }, assets: { asset: vi.fn().mockReturnValue(pending.promise) } });
    fireEvent.click(button()); await waitFor(() => expect(state.original.assets!.asset).toHaveBeenCalledOnce());
    state.rerender(<ExecutionProvenancePanel {...state.original} selection={{ ...state.original.selection, identity: 'other-reader' }} />);
    await act(async () => { pending.resolve(asset()); await pending.promise; });
    expect(screen.queryByText('request-original')).toBeNull(); expect(screen.queryByText(/已核验正式资产/)).toBeNull();
  });

  it.each(['job', 'asset'] as const)('does not invoke a deferred %s GET factory after its read authority changes', async phase => {
    let invokeHeld: (() => Promise<void>) | undefined, reads = 0;
    const read: ExecutionProvenanceProps['read'] = <T,>(work: () => Promise<T>) => {
      reads += 1;
      if (reads !== (phase === 'job' ? 1 : 2)) return work();
      return new Promise<T>((resolve, reject) => {
        invokeHeld = async () => { try { resolve(await work()); } catch (reason) { reject(reason); } };
      });
    };
    const get = vi.fn().mockResolvedValue(job(phase === 'asset' ? { status: 'APPROVED', approved_asset_version: 2 } : {}));
    const getAsset = vi.fn().mockResolvedValue(asset()), state = mount({ production: { get }, assets: { asset: getAsset }, read });
    fireEvent.click(button()); await waitFor(() => expect(invokeHeld).toBeTypeOf('function'));
    state.rerender(<ExecutionProvenancePanel {...state.original} selection={{ ...state.original.selection, identity: 'changed-reader' }} />);
    await act(async () => { await invokeHeld!(); });
    expect(get).toHaveBeenCalledTimes(phase === 'job' ? 0 : 1); expect(getAsset).not.toHaveBeenCalled();
    expect(screen.queryByText('request-original')).toBeNull(); expect(screen.queryByRole('alert')).toBeNull();
    expect(state.original.onUnavailable).not.toHaveBeenCalled();
  });

  it('aborts the read and ignores retained callbacks after unmount', async () => {
    const pending = deferred<ProductionJob>(), get = vi.fn().mockReturnValue(pending.promise), state = mount({ production: { get } });
    const oldClick = retainedClick(button()); fireEvent.click(button()); const signal = get.mock.calls[0][2] as AbortSignal;
    state.unmount(); expect(signal.aborted).toBe(true);
    await act(async () => { oldClick(); pending.resolve(job()); await pending.promise; }); expect(get).toHaveBeenCalledOnce();
  });

  it('allows a newer read-only state but rejects same-version mutation and version rollback', async () => {
    const get = vi.fn().mockResolvedValueOnce(job()).mockResolvedValueOnce(job({ version: 4, status: 'UNKNOWN' }))
      .mockResolvedValueOnce(job({ version: 4, status: 'FAILED' })).mockResolvedValueOnce(job({ version: 3 }));
    mount({ production: { get } }); await load();
    fireEvent.click(button('重新读取执行来源')); await screen.findByText('UNKNOWN'); expect(screen.getByText(/原 Job 版本已变化/)).toBeTruthy();
    fireEvent.click(button('重新读取执行来源')); await screen.findByRole('alert'); expect(screen.queryByText('request-original')).toBeNull();
    fireEvent.click(button()); await screen.findByRole('alert'); expect(screen.queryByText('request-original')).toBeNull();
  });

  it('rejects changed immutable input pins even with an unchanged request digest and newer version', async () => {
    const changed = job({ version: 4 }); changed.sources = [{ ...changed.sources[0], version: 8 }]; changed.command!.source_snapshots = changed.sources;
    const get = vi.fn().mockResolvedValueOnce(job()).mockResolvedValueOnce(changed); mount({ production: { get } }); await load();
    fireEvent.click(button('重新读取执行来源')); await screen.findByRole('alert'); expect(screen.queryByText('request-original')).toBeNull();
    expect(screen.queryByText(/v8/)).toBeNull();
  });

  it.each(['busy', 'active', 'current', 'origin'] as const)('keeps immutable receipt history through a %s presentation pause', async pause => {
    const changed = job(); changed.sources = [{ ...changed.sources[0], version: 8 }]; changed.command!.source_snapshots = changed.sources;
    const get = vi.fn().mockResolvedValueOnce(job()).mockResolvedValueOnce(changed), state = mount({ production: { get } }); await load();
    const paused: ExecutionProvenanceProps = { ...state.original };
    if (pause === 'busy') paused.busy = true;
    if (pause === 'active') paused.active = false;
    if (pause === 'current') paused.isCurrent = () => false;
    if (pause === 'origin') paused.origin = { projectId: 'project-a', canvasId: 'canvas-a', canvasVersion: 2, canvasDigest: a, cardId: 'card-a', source: { asset_id: 'input-original', version: 7, digest: b, kind: 'image' } };
    state.rerender(<ExecutionProvenancePanel {...paused} />); state.rerender(<ExecutionProvenancePanel {...state.original} />);
    fireEvent.click(button()); await screen.findByRole('alert'); expect(screen.queryByText('request-original')).toBeNull();
  });

  it('does not create a source-derived origin; only shows the supplied exact session anchor', async () => {
    const origin = { projectId: 'project-a', canvasId: 'canvas-original', canvasVersion: 2, canvasDigest: a, cardId: 'card-original', source: { asset_id: 'input-original', version: 7, digest: b, kind: 'image' as const } };
    const state = mount(); await load(); expect(screen.getByText(/没有与本次任务输入匹配的会话锚点/)).toBeTruthy();
    state.rerender(<ExecutionProvenancePanel {...state.original} origin={origin} isOriginCurrent={() => true} />); await load();
    expect(screen.getByText('canvas-original')).toBeTruthy(); expect(screen.getByText('card-original')).toBeTruthy();
    expect(screen.getByText(/宿主确认原会话锚点仍有效/)).toBeTruthy();
    expect(screen.getByText(/跨会话不能恢复此位置/)).toBeTruthy();
  });

  it.each(['project', 'version', 'digest'] as const)('hides a supplied anchor whose %s does not match the Job', async field => {
    const origin = { projectId: field === 'project' ? 'foreign' : 'project-a', canvasId: 'canvas-private', canvasVersion: 2, canvasDigest: a, cardId: 'card-private', source: { asset_id: 'input-original', version: field === 'version' ? 8 : 7, digest: field === 'digest' ? c : b, kind: 'image' as const } };
    mount({ origin }); await load(); expect(document.body.textContent).not.toMatch(/canvas-private|card-private/);
  });

  it.each(['canvasId', 'cardId'] as const)('does not leak credentials placed independently in session %s', async field => {
    const origin = { projectId: 'project-a', canvasId: field === 'canvasId' ? 'sk-live-secret' : 'canvas-original', canvasVersion: 2, canvasDigest: a, cardId: field === 'cardId' ? 'token-secret' : 'card-original', source: { asset_id: 'input-original', version: 7, digest: b, kind: 'image' as const } };
    mount({ origin }); await load(); expect(document.body.textContent).not.toMatch(/sk-live-secret|token-secret/);
  });

  it('does not trigger a read during StrictMode mount rehearsal', async () => {
    const original = props(); render(<StrictMode><ExecutionProvenancePanel {...original} /></StrictMode>);
    expect(original.production.get).not.toHaveBeenCalled(); await load(); expect(original.production.get).toHaveBeenCalledOnce();
  });
});
