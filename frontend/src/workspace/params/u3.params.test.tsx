// @vitest-environment jsdom
// [HERMIA-FE-20261025 U3-M7] Evidence type: mock (jsdom + fake ProductionPort). No real provider, no model call.
import {act, cleanup, fireEvent, render, screen} from '@testing-library/react';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {ApiError} from '../../api';
import type {MediaCommand, ProductionJob, ProductionPreview, ProductionProvider} from '../../creative/studioProductionClient';
import {createScopeLease} from '../state/scopeLease';
import {ParamEditPanel} from './ParamEditPanel';
import {CLOUD_INTERNAL, fieldsFromProvider, ParamSession, TEMPLATE_GAP, type ProductionPort} from './paramSession';

afterEach(cleanup);
const HEX = 'cd'.repeat(32);
const provider = (o: Partial<ProductionProvider> = {}): ProductionProvider => ({operation_id: 'm5.image.i2i', provider_id: 'p', model_id: 'm', local: true, route_digest: HEX,
  capability: 'x', supported_parameters: ['cfg'], readiness: 'CONFIGURED_NOT_VERIFIED',
  image_capabilities: {recipe_id: 'r', reference_limit: 1, reference_semantics: 'SINGLE_IMAGE_INITIALIZATION', mask_semantics: null, structural_only: true, inference_verified: false, cfg: {min: 1, max: 15, default: 7}}, ...o});
const base: MediaCommand = {operation_id: 'm5.image.i2i', request_id: 'r1', prompt: 'p', parameters: {cfg: 7, seed: 5}, source_snapshots: [], allow_cloud: false, license_note: ''};
const preview = (d = 'a'.repeat(64)) => ({preview_digest: d, request_digest: HEX} as unknown as ProductionPreview);
const job = (o: Partial<ProductionJob> = {}) => ({owner: 'image', id: 'j1', version: 1, status: 'QUEUED', request_digest: HEX, ...o} as ProductionJob);
const deferred = <T,>() => { let res!: (v: T) => void, rej!: (e: unknown) => void; const p = new Promise<T>((a, b) => { res = a; rej = b; }); return {p, res, rej}; };
function port(over: Partial<ProductionPort> = {}): ProductionPort & {[k: string]: ReturnType<typeof vi.fn>} {
  return {preview: vi.fn(async () => preview()), create: vi.fn(async () => job()), execute: vi.fn(async () => job({version: 2, status: 'RUNNING'})), get: vi.fn(async () => job()), ...over} as never;
}

describe('[U3-M7] fields from the real capability declaration', () => {
  it('editable = declared, readonly = fixed by task, unsupported = undeclared original keys + cloud internals', () => {
    const f = fieldsFromProvider(provider({local: false}), base.parameters);
    expect(f.filter(x => x.mode === 'editable').map(x => x.key)).toEqual(['cfg']);
    expect(f.filter(x => x.mode === 'readonly').map(x => x.key)).toEqual(['operation', 'model', 'route']);
    expect(f.filter(x => x.mode === 'unsupported').map(x => x.key)).toEqual(['seed', 'cloud-internal']);
    expect(f.find(x => x.key === 'cloud-internal')!.reason).toBe(CLOUD_INTERNAL);
  });
  it('validates against declared bounds; undeclared keys cannot be edited', () => {
    const s = new ParamSession(port(), provider(), base, createScopeLease('A'));
    expect(s.edit('cfg', 99)).toBe('范围是 1–15'); expect(s.edit('seed', 1)).toBe('这个参数不可修改');
    expect(s.edit('cfg', 9)).toBeNull(); expect(s.command().parameters).toEqual({cfg: 9, seed: 5});
    expect(s.cost).toEqual({state: 'UNKNOWN', why: '服务端没有提供成本估算，所以这里不显示价格。'});
  });
});

describe('[U3-M7] explicit flow, invalidation and no auto-resend', () => {
  it('edit after preview invalidates it: old digest cannot be confirmed', async () => {
    const p = port(); const s = new ParamSession(p, provider(), base, createScopeLease('A'));
    await s.preview(); expect(s.phase.kind).toBe('previewed');
    s.edit('cfg', 8); expect(s.phase.kind).toBe('editing');
    await s.confirmCreate('a'.repeat(64)); expect(p.create).not.toHaveBeenCalled();
  });
  it('happy path: preview → create(reviewed digest) → execute(job) via original entry; each exactly once', async () => {
    const p = port(); const s = new ParamSession(p, provider(), base, createScopeLease('A'));
    s.edit('cfg', 9); await s.preview(); await s.confirmCreate('a'.repeat(64));
    expect(p.create).toHaveBeenCalledWith({...base, parameters: {cfg: 9, seed: 5}}, 'a'.repeat(64));
    await s.confirmExecute(1); expect(p.execute).toHaveBeenCalledWith(job());
    expect(s.phase.kind).toBe('executed');
  });
  it('double click while in flight sends once', async () => {
    const d = deferred<ProductionJob>(); const p = port({create: vi.fn(() => d.p)});
    const s = new ParamSession(p, provider(), base, createScopeLease('A')); await s.preview();
    const a = s.confirmCreate('a'.repeat(64)), b = s.confirmCreate('a'.repeat(64));
    d.res(job()); await a; await b; expect(p.create).toHaveBeenCalledTimes(1);
  });
  it('timeout on execute ⇒ UNKNOWN, never resent; verify only reads; QUEUED returns control to the user', async () => {
    vi.useFakeTimers();
    try {
      const p = port({execute: vi.fn(() => new Promise<ProductionJob>(() => {}))});
      const s = new ParamSession(p, provider(), base, createScopeLease('A'), 1000);
      await s.preview(); await s.confirmCreate('a'.repeat(64));
      const run = s.confirmExecute(1); await vi.advanceTimersByTimeAsync(1001); await run;
      expect(s.phase.kind).toBe('unknown'); expect(p.execute).toHaveBeenCalledTimes(1);
      await vi.advanceTimersByTimeAsync(60000); expect(p.execute).toHaveBeenCalledTimes(1);
      await s.confirmExecute(1); expect(p.execute).toHaveBeenCalledTimes(1); // phase is unknown → refused
      (p.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce(job({status: 'UNKNOWN'}));
      await s.verify(); expect(s.phase.kind).toBe('unknown');
      await s.verify(); expect(s.phase.kind).toBe('created'); expect(p.execute).toHaveBeenCalledTimes(1);
    } finally { vi.useRealTimers(); }
  });
  it('lost response (network) on create ⇒ UNKNOWN; 4xx ⇒ failed; neither resends', async () => {
    const p = port({create: vi.fn(async () => { throw new TypeError('Failed to fetch'); })});
    const s = new ParamSession(p, provider(), base, createScopeLease('A')); await s.preview(); await s.confirmCreate('a'.repeat(64));
    expect(s.phase).toMatchObject({kind: 'unknown', step: 'create', job: null}); expect(p.create).toHaveBeenCalledTimes(1);
    const q = port({create: vi.fn(async () => { throw new ApiError({status: 409, code: 'C', message: 'x'}); })});
    const t = new ParamSession(q, provider(), base, createScopeLease('A')); await t.preview(); await t.confirmCreate('a'.repeat(64));
    expect(t.phase.kind).toBe('failed'); expect(q.create).toHaveBeenCalledTimes(1);
  });
  it('shared template scope is blocked (no template write interface) and cannot preview', async () => {
    const p = port(); const s = new ParamSession(p, provider(), base, createScopeLease('A'));
    s.setScope('shared-template'); expect(s.phase).toEqual({kind: 'blocked', text: TEMPLATE_GAP});
    await s.preview(); expect(p.preview).not.toHaveBeenCalled();
  });
  it('stale confirmation callback after scope switch is ignored', async () => {
    const d = deferred<ProductionPreview>(); const p = port({preview: vi.fn(() => d.p)}); const lease = createScopeLease('A');
    const s = new ParamSession(p, provider(), base, lease); const run = s.preview(); lease.retire(); d.res(preview()); await run;
    expect(s.phase.kind).toBe('previewing'); await s.confirmCreate('a'.repeat(64)); expect(p.create).not.toHaveBeenCalled();
  });
});

describe('[U3-M7] panel', () => {
  it('no call on mount; confirm dialog names target/changes/unknown cost; no raw digests on screen', async () => {
    const p = port(); const s = new ParamSession(p, provider(), base, createScopeLease('A'));
    render(<ParamEditPanel session={s} targetTitle="封面图" />);
    expect(p.preview).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('提示词引导强度'), {target: {value: '9'}});
    expect(screen.getByTestId('u3-preview-stale')).toBeTruthy();
    await act(async () => { fireEvent.click(screen.getByTestId('u3-preview')); });
    fireEvent.click(screen.getByTestId('u3-ask-create'));
    expect(screen.getByTestId('u3-confirm').textContent).toContain('影响对象：封面图。修改的参数：提示词引导强度。成本：未知。');
    expect(p.create).not.toHaveBeenCalled();
    await act(async () => { fireEvent.click(screen.getByTestId('u3-confirm-yes')); });
    expect(p.create).toHaveBeenCalledTimes(1); expect(p.execute).not.toHaveBeenCalled();
    expect(document.body.textContent).not.toMatch(/a{64}|cd{8}|j1/);
    fireEvent.click(screen.getByTestId('u3-ask-execute'));
    await act(async () => { fireEvent.click(screen.getByTestId('u3-confirm-yes')); });
    expect(p.execute).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('u3-executed').textContent).toContain('不会自动采用');
  });
});
