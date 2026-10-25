// @vitest-environment jsdom
// [HERMIA-FE-20261025 U4-T-M8] Evidence: mock. Covers normal loop, lease switch/ABA, late response, deleted node, modified work,
// permission revoked, double click, lost response (UNKNOWN, no resend), not-reviewed, asset mismatch, no auto calls on mount.
import {afterEach, describe, expect, it, vi} from 'vitest';
import {cleanup, render, screen, fireEvent, waitFor} from '@testing-library/react';
afterEach(cleanup);
import {createAdoptFlow, type AdoptDeps} from './adoptFlow';
import {actionAvailability, projectResult} from './resultModel';
import {ResultsPanel} from './ResultsPanel';
import {asset, canvas, history, job, lease} from './u4.fixtures';

function deps(over: Partial<{j: any; cv: any; h: any; a: any; save: any; review: any; canMutate: boolean}> = {}) {
  const l = lease(); const cv = over.cv ?? canvas();
  const d = {
    production: {get: vi.fn(async () => over.j ?? job()), review: over.review ?? vi.fn(async (j: any) => ({...j, status: 'APPROVED', approved_asset_version: 2}))},
    asset: vi.fn(async () => over.a ?? asset()),
    canvasViews: {get: vi.fn(async () => cv), history: vi.fn(async () => over.h ?? history(cv)),
      save: over.save ?? vi.fn(async (_id: string, v: number, definition: any) => ({...cv, version: v + 1, definition}))},
    lease: l, canMutate: () => over.canMutate ?? true,
  };
  return {d: d as unknown as AdoptDeps & {lease: typeof l}, raw: d, l};
}
const target = {projectId: 'p1', canvasId: 'cv1', cardId: 'card-1', job: {owner: 'image' as const, id: 'job-1', version: 3, request_digest: 'a'.repeat(64)}};

describe('U4 M8 standing projection', () => {
  it('distinguishes candidate / reviewed-asset / adopted / unknown', () => {
    expect(projectResult(job({status: 'AWAITING_REVIEW', approved_asset_version: null as any}), canvas(), 'card-1').standing).toBe('candidate');
    expect(projectResult(job(), canvas(), 'card-1').standing).toBe('reviewed-asset');
    const adopted = canvas({definition: {schema_version: 1, title: 'x', viewport: {x: 0, y: 0, zoom: 1}, cards: [{id: 'card-1', position: {x: 0, y: 0}, asset: {asset_id: 'asset-9', version: 2, digest: 'b'.repeat(64), kind: 'image'}}]}});
    expect(projectResult(job(), adopted, 'card-1').standing).toBe('adopted');
    expect(projectResult(job({status: 'UNKNOWN'}), canvas(), 'card-1').standing).toBe('unknown');
  });
  it('candidate cannot be adopted; Canon write always unsupported with reason', () => {
    const v = projectResult(job({status: 'SUCCEEDED', approved_asset_version: null as any}), canvas(), 'card-1');
    const a = actionAvailability(v, {canMutate: true, compareTargetIsAsset: false});
    expect(a.adopt).toEqual({ok: false, reason: '必须先审核为正式素材，才能采用到作品。'});
    expect(a.canon.ok).toBe(false); expect(a.review.ok).toBe(true);
    expect(actionAvailability(v, {canMutate: false, compareTargetIsAsset: false}).review.ok).toBe(false);
  });
});

describe('U4 M8 adopt flow guards', () => {
  it('normal loop: prepare → commit saves with incarnation + digest + expected_card fences', async () => {
    const {d, raw} = deps(); const f = createAdoptFlow(d);
    const p = await f.prepare(target); expect(p.ok).toBe(true); if (!p.ok) return;
    const r = await f.commit(target, p); expect(r.state).toBe('adopted');
    expect(raw.canvasViews.save).toHaveBeenCalledTimes(1);
    const [, ver, , origin] = raw.canvasViews.save.mock.calls[0] as any[];
    expect(ver).toBe(5);
    expect(origin).toEqual({expected_incarnation: 'inc-1', expected_definition_digest: 'd'.repeat(64), expected_card: {card_id: 'card-1', source: {asset_id: 'asset-old', version: 1, digest: 'c'.repeat(64), kind: 'image'}}});
    expect(raw.production.review).not.toHaveBeenCalled();
  });
  it.each([
    ['not-reviewed', {j: job({status: 'AWAITING_REVIEW'})}],
    ['task-changed', {j: job({version: 4})}],
    ['project-changed', {j: job({novel_id: 'p2'})}],
    ['node-deleted', {cv: canvas({definition: {schema_version: 1, title: 'x', viewport: {x: 0, y: 0, zoom: 1}, cards: []}})}],
    ['asset-mismatch', {a: asset({version: 3})}],
    ['asset-mismatch', {a: asset({deleted_at: 'now'} as any)}],
    ['permission', {canMutate: false}],
  ] as const)('blocks %s', async (reason, over) => {
    const {d, raw} = deps(over as any); const p = await createAdoptFlow(d).prepare(target);
    expect(p).toEqual({ok: false, reason}); expect(raw.canvasViews.save).not.toHaveBeenCalled();
  });
  it('work modified between history and record → work-modified', async () => {
    const cv = canvas(); const {d} = deps({cv, h: history(cv, {current_version: 6})});
    expect(await createAdoptFlow(d).prepare(target)).toEqual({ok: false, reason: 'work-modified'});
  });
  it('late response after lease switch (A→B→A new epoch) is dropped, no save', async () => {
    const {d, raw, l} = deps(); const f = createAdoptFlow(d);
    const p = await f.prepare(target); if (!p.ok) throw new Error('x');
    l.epoch = 2; // switched away and back: new epoch
    expect(await f.commit(target, p)).toEqual({state: 'blocked', reason: 'lease-retired'});
    expect(raw.canvasViews.save).not.toHaveBeenCalled();
  });
  it('lease retired while job read in flight → lease-retired', async () => {
    const {d, raw, l} = deps(); raw.production.get.mockImplementationOnce(async () => { l.cur = false; return job(); });
    expect(await createAdoptFlow(d).prepare(target)).toEqual({ok: false, reason: 'lease-retired'});
  });
  it('work modified after confirmation → blocked before write', async () => {
    const {d, raw} = deps(); const f = createAdoptFlow(d); const p = await f.prepare(target); if (!p.ok) throw new Error('x');
    const cv2 = canvas({version: 6, definition_digest: 'e'.repeat(64)});
    raw.canvasViews.get.mockResolvedValue(cv2); raw.canvasViews.history.mockResolvedValue(history(cv2));
    expect(await f.commit(target, p)).toEqual({state: 'blocked', reason: 'work-modified'});
    expect(raw.canvasViews.save).not.toHaveBeenCalled();
  });
  it('double click: second commit while first in flight is refused; save called once', async () => {
    let release!: () => void; const gate = new Promise<void>(r => { release = r; });
    const {d, raw} = deps({save: vi.fn(async (_i: string, v: number, definition: any) => { await gate; return {...canvas(), version: v + 1, definition}; })});
    const f = createAdoptFlow(d); const p = await f.prepare(target); if (!p.ok) throw new Error('x');
    const first = f.commit(target, p); const second = await f.commit(target, p);
    expect(second).toEqual({state: 'blocked', reason: 'in-flight'});
    release(); expect((await first).state).toBe('adopted'); expect(raw.canvasViews.save).toHaveBeenCalledTimes(1);
  });
  it('lost response → UNKNOWN, never resent', async () => {
    const {d, raw} = deps({save: vi.fn(async () => { throw new TypeError('network'); })});
    const f = createAdoptFlow(d); const p = await f.prepare(target); if (!p.ok) throw new Error('x');
    const r = await f.commit(target, p); expect(r.state).toBe('unknown');
    await new Promise(r2 => setTimeout(r2, 20)); expect(raw.canvasViews.save).toHaveBeenCalledTimes(1);
  });
  it('owner conflict 409 → work-modified; 403 → permission', async () => {
    for (const [status, reason] of [[409, 'work-modified'], [403, 'permission']] as const) {
      const {d} = deps({save: vi.fn(async () => { throw Object.assign(new Error('x'), {status}); })});
      const f = createAdoptFlow(d); const p = await f.prepare(target); if (!p.ok) throw new Error('x');
      expect(await f.commit(target, p)).toEqual({state: 'blocked', reason});
    }
  });
  it('review is explicit and never chains into adopt', async () => {
    const {d, raw} = deps(); const r = await createAdoptFlow(d).review(job({status: 'AWAITING_REVIEW'}));
    expect(r.state).toBe('reviewed'); expect(raw.canvasViews.save).not.toHaveBeenCalled();
  });
});

describe('U4 M8 ResultsPanel', () => {
  it('mount performs zero calls; no raw ids on screen; adopt needs explicit confirm', async () => {
    const {d, raw} = deps(); const {container} = render(<ResultsPanel deps={d} target={target}/>);
    expect(raw.production.get).not.toHaveBeenCalled(); expect(raw.canvasViews.get).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('u4-read'));
    await waitFor(() => expect(screen.getByTestId('u4-standing-label').textContent).toBe('已审核素材（未采用）'));
    fireEvent.click(screen.getByTestId('u4-adopt'));
    await screen.findByTestId('u4-adopt-confirm'); expect(raw.canvasViews.save).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('u4-adopt-yes'));
    await waitFor(() => expect(screen.getByTestId('u4-standing-label').textContent).toBe('当前采用'));
    expect(raw.canvasViews.save).toHaveBeenCalledTimes(1);
    expect(container.textContent).not.toMatch(/job-1|asset-9|cv1|card-1|p1|inc-1|[a-f0-9]{16}/);
    expect((screen.getByTestId('u4-canon') as HTMLButtonElement).disabled).toBe(true);
  });
  it('offline read stays UNKNOWN with next step and issues no write', async () => {
    const {d, raw} = deps(); render(<ResultsPanel deps={d} target={target} online={false}/>);
    fireEvent.click(screen.getByTestId('u4-read'));
    await waitFor(() => expect(screen.getByTestId('u4-msg').textContent).toContain('当前离线'));
    expect(raw.canvasViews.save).not.toHaveBeenCalled(); expect(raw.production.review).not.toHaveBeenCalled();
  });
});
