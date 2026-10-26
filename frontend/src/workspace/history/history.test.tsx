// @vitest-environment jsdom
// [HERMIA-FE-20261025 U4-T-M9] Evidence: mock. Diff, provenance, restore impact, explicit restore (new version, old kept),
// incarnation change (delete+recreate), modified-after-confirm, double click, lost response UNKNOWN, offline/restart UNKNOWN,
// lease switch, and "restore != rerun" (no production calls exist on this path).
import {afterEach, describe, expect, it, vi} from 'vitest';
import {cleanup, render, screen, fireEvent, waitFor} from '@testing-library/react';
afterEach(cleanup);
import {diffDefinitions, restoreImpact} from './historyModel';
import {createRestoreFlow} from './restoreFlow';
import {resolveExecutionTruth} from './executionTruth';
import {HistoryPanel} from './HistoryPanel';
import {D, def, job, lease} from '../results/u4.fixtures';
import type {CanvasViewHistory} from '../../creative/studioCanvasViewClient';

const a = (v: number) => ({asset_id: 'asset-x', version: v, digest: D(String(v)), kind: 'image' as const});
function hist(over: Partial<CanvasViewHistory> = {}): CanvasViewHistory {
  const items = [
    {version: 1, definition: def([{id: 'c1', position: {x: 0, y: 0}, asset: a(1)}, {id: 'c2', position: {x: 5, y: 5}}], '旧标题'), definition_digest: D('1'), reference_states: [], created_at: 't', updated_at: '10-24 10:00', can_restore: true},
    {version: 2, definition: def([{id: 'c1', position: {x: 9, y: 0}, asset: a(2)}, {id: 'c3', position: {x: 1, y: 1}}]), definition_digest: D('2'), reference_states: [], created_at: 't', updated_at: '10-25 08:00', can_restore: true},
  ];
  return {project_id: 'p1', id: 'cv1', incarnation: 'inc-1', current_version: 2, current_definition_digest: D('2'), items, restore_policy: 'CURRENT_METADATA_ONLY', execution_authority: false, binary_content_verified: false, ...over} as unknown as CanvasViewHistory;
}

describe('U4 M9 diff / impact', () => {
  it('diff current vs historical', () => {
    const h = hist(); const d = diffDefinitions(h.items[1].definition, h.items[0].definition);
    expect(d.titleChanged).toBe(true);
    expect(d.cards).toEqual([{cardId: 'c1', change: 'moved'}, {cardId: 'c1', change: 'asset-changed', from: '图像素材第 1 版', to: '图像素材第 2 版'},
      {cardId: 'c3', change: 'added'}, {cardId: 'c2', change: 'removed'}]);
  });
  it('restore impact explains new version, keeps old, no rerun', () => {
    const r = restoreImpact(hist(), 1); expect(r.ok).toBe(true); if (!r.ok) return;
    expect(r.newVersion).toBe(3);
    expect(r.lines).toContain('恢复后生成新的第 3 版；当前第 2 版和所有旧版本都保留');
    expect(r.lines).toContain('不会重跑模型、不会重新入队，也不会自动重新采用旧结果');
    expect(r.lines).toContain('会恢复 1 张已删除的卡片'); expect(r.lines).toContain('会移除 1 张之后新增的卡片');
  });
  it('cannot restore current or non-restorable', () => {
    expect(restoreImpact(hist(), 2)).toEqual({ok: false, reason: '这已经是当前版本。'});
    const h = hist(); (h.items[0] as any).can_restore = false;
    expect(restoreImpact(h, 1)).toEqual({ok: false, reason: '这个历史版本引用的素材已不可用，服务端不允许恢复。'});
  });
});

function rdeps(h = hist(), restore?: any) {
  const l = lease();
  const d = {canvasViews: {history: vi.fn(async () => h), restore: restore ?? vi.fn(async (src: CanvasViewHistory) => ({version: src.current_version + 1}))}, lease: l, canMutate: () => true};
  return {d: d as any, l};
}
describe('U4 M9 restore flow', () => {
  it('explicit restore calls owner once with the fresh history', async () => {
    const {d} = rdeps(); const r = await createRestoreFlow(d)('cv1', hist(), 1);
    expect(r.state).toBe('restored'); expect(d.canvasViews.restore).toHaveBeenCalledTimes(1);
    expect(d.canvasViews.restore.mock.calls[0][1]).toBe(1);
  });
  it('delete + same-name recreate (incarnation changed) blocks', async () => {
    const {d} = rdeps(hist({incarnation: 'inc-2'})); const r = await createRestoreFlow(d)('cv1', hist(), 1);
    expect(r).toEqual({state: 'blocked', text: '这个作品已被删除后重建，旧历史不能恢复到新作品。'}); expect(d.canvasViews.restore).not.toHaveBeenCalled();
  });
  it('work modified after confirm blocks', async () => {
    const {d} = rdeps(hist({current_version: 3, current_definition_digest: D('3')}));
    expect((await createRestoreFlow(d)('cv1', hist(), 1)).state).toBe('blocked'); expect(d.canvasViews.restore).not.toHaveBeenCalled();
  });
  it('lease switch during history read cancels', async () => {
    const {d, l} = rdeps(); d.canvasViews.history.mockImplementationOnce(async () => { l.epoch = 2; return hist(); });
    expect((await createRestoreFlow(d)('cv1', hist(), 1)).state).toBe('blocked'); expect(d.canvasViews.restore).not.toHaveBeenCalled();
  });
  it('double click → one owner call; lost response → UNKNOWN without resend', async () => {
    let release!: () => void; const gate = new Promise<void>(r => { release = r; });
    const {d} = rdeps(hist(), vi.fn(async () => { await gate; throw new TypeError('network'); }));
    const f = createRestoreFlow(d); const p1 = f('cv1', hist(), 1); const p2 = await f('cv1', hist(), 1);
    expect(p2.state).toBe('blocked'); release(); expect((await p1).state).toBe('unknown');
    expect(d.canvasViews.restore).toHaveBeenCalledTimes(1);
  });
});

describe('U4 M9 execution truth after refresh/offline/restart', () => {
  it('reads original task first; confirmed only from the read', async () => {
    const read = vi.fn(async () => job({status: 'AWAITING_REVIEW'}));
    expect(await resolveExecutionTruth(read, lease(), {online: true})).toEqual({state: 'CONFIRMED', status: '等待审核'}); expect(read).toHaveBeenCalledTimes(1);
  });
  it('offline → UNKNOWN with next step, no read', async () => {
    const read = vi.fn(); const r = await resolveExecutionTruth(read as any, lease(), {online: false});
    expect(r.state).toBe('UNKNOWN'); expect(read).not.toHaveBeenCalled();
  });
  it('read failure → UNKNOWN; owner UNKNOWN / needs_reconciliation → UNKNOWN', async () => {
    expect((await resolveExecutionTruth(async () => { throw new Error('x'); }, lease(), {online: true})).state).toBe('UNKNOWN');
    expect((await resolveExecutionTruth(async () => job({status: 'UNKNOWN'}), lease(), {online: true})).state).toBe('UNKNOWN');
    expect((await resolveExecutionTruth(async () => job({status: 'RUNNING', needs_reconciliation: true} as any), lease(), {online: true})).state).toBe('UNKNOWN');
  });
  it('late read after lease retire → RETIRED (dropped)', async () => {
    const l = lease(); expect(await resolveExecutionTruth(async () => { l.cur = false; return job(); }, l, {online: true})).toEqual({state: 'RETIRED'});
  });
});

describe('U4 M9 HistoryPanel', () => {
  it('no read on mount; compare → impact → confirm → new version; no raw ids', async () => {
    const {d} = rdeps(); const {container} = render(<HistoryPanel deps={d} canvasId="cv1" localDraft/>);
    expect(d.canvasViews.history).not.toHaveBeenCalled();
    expect(screen.getByTestId('u4-local-draft').getAttribute('data-record-kind')).toBe('local-draft');
    fireEvent.click(screen.getByTestId('u4-history-read'));
    fireEvent.click(await screen.findByTestId('u4-compare-1'));
    fireEvent.click(screen.getByTestId('u4-restore'));
    expect(d.canvasViews.restore).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('u4-restore-yes'));
    await waitFor(() => expect(screen.getByTestId('u4-history-msg').textContent).toBe('已恢复为新的第 3 版，旧版本都还在。没有重跑任何生成。'));
    expect(container.textContent).not.toMatch(/cv1|inc-1|asset-x|c1|c2|c3|[a-f0-9]{16}/);
  });
});
