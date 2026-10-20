// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import capture from './fixtures/phase6.capture.editing-pipeline.json';
import { timelineDurationHint, timelineMeasuredDuration, parseTimelineAssetRange } from './studioTimelineAssetRange';
import { StudioTimelineAssetHandoff, appendTimelineAsset } from './StudioTimelineAssetHandoff';
import { StudioTimelineAssetPicker } from './StudioTimelineAssetPicker';
import type { StudioAsset } from './studioClient';
import type { ProductionJob } from './studioProductionClient';
import type { StudioTimelineDraft } from './studioTimelineTypes';
const asset = () => structuredClone(capture.audio_formal) as unknown as StudioAsset;
const job = () => structuredClone(capture.audio_receipts.approved) as unknown as ProductionJob;
const draft = (): StudioTimelineDraft => ({ title: 'Range', timeline: { schema_version: 2, duration_ms: 5000, width: 64, height: 64, fps: 10,
  tracks: [{ id: 'audio', kind: 'AUDIO', order: 0, muted: false, gain_db: 0, clips: [] }], captions: [] } });
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const set = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
const end = () => screen.getByLabelText('交接来源终点（毫秒）') as HTMLInputElement;
const deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes; }); return { promise, resolve }; };
afterEach(cleanup);

describe('exact approved duration receipt', () => {
  it('accepts only matching known audio and timeline producers', () => {
    expect(timelineMeasuredDuration(asset(), job())).toBe(800);
    expect(timelineMeasuredDuration(capture.formal_result as unknown as StudioAsset, capture.approved_get as unknown as ProductionJob)).toBe(1000);
  });
  it.each(['id', 'owner', 'operation', 'project', 'branch', 'status', 'output-id', 'version', 'digest', 'kind', 'proof', 'output-hash', 'reconcile', 'missing'])('does not derive duration from mismatched %s', fault => {
    const value = job();
    if (fault === 'id') value.id = 'other';
    if (fault === 'owner') value.owner = 'video';
    if (fault === 'operation') value.operation_id = 'm8.audio.speech';
    if (fault === 'project') value.novel_id = 'other';
    if (fault === 'branch') value.branch_id = 'other';
    if (fault === 'status') value.status = 'AWAITING_REVIEW';
    if (fault === 'output-id') value.output_candidate!.id = 'other';
    if (fault === 'version') value.approved_asset_version!++;
    if (fault === 'digest') value.output_candidate!.digest = 'b'.repeat(64);
    if (fault === 'kind') value.output_candidate!.kind = 'video';
    if (fault === 'proof') value.media_measurement!.profile_validation = 'NATIVE_FFPROBE_EXACT';
    if (fault === 'output-hash') (value.media_measurement as unknown as Record<string, unknown>).output_sha256 = 'b'.repeat(64);
    if (fault === 'reconcile') value.needs_reconciliation = true;
    if (fault === 'missing') value.media_measurement = null;
    expect(timelineMeasuredDuration(asset(), value)).toBeUndefined();
  });
  it.each([0, -1, NaN, Infinity, 0.5, 36000001, '800', null])('refuses unproven duration %s', value => {
    const receipt = job(); (receipt.media_measurement as unknown as Record<string, unknown>).duration_ms = value;
    expect(timelineMeasuredDuration(asset(), receipt)).toBeUndefined();
  });
  it('never accepts arbitrary asset metadata or merely a matching task id', () => {
    const value = asset(); value.provenance!.operation = 'm8.audio.music';
    Object.assign(value, { duration_ms: 800, parameters: { duration_ms: 800 } });
    expect(timelineDurationHint(value)).toBeUndefined(); expect(timelineMeasuredDuration(value, job())).toBeUndefined();
    delete value.provenance; expect(timelineDurationHint(value)).toBeUndefined();
  });
  it.each([['', '800'], ['0', ''], ['-1', '800'], ['0', 'NaN'], ['0', '1e3'], ['10', '10'], ['0', '800.5']])('retains invalid manual input %s/%s without guessing', (start, end) => {
    expect(parseTimelineAssetRange(start, end)).toBeUndefined();
  });
  it('requires a range for unknown audio/video and preserves image insertion', () => {
    const value = draft(); appendTimelineAsset(value, 'audio', asset()); expect(value.timeline.tracks[0].clips).toHaveLength(0);
    appendTimelineAsset(value, 'audio', asset(), { in_ms: 0, out_ms: 6000 }); expect(value.timeline.tracks[0].clips).toHaveLength(0);
    appendTimelineAsset(value, 'audio', asset(), { in_ms: 10, out_ms: 700 }); expect(value.timeline.tracks[0].clips[0]).toMatchObject({ in_ms: 10, out_ms: 700 });
    value.timeline.tracks.push({ id: 'image', kind: 'VIDEO', order: 1, muted: false, gain_db: 0, clips: [] });
    appendTimelineAsset(value, 'image', { ...asset(), kind: 'image' }); expect(value.timeline.tracks[1].clips[0]).toMatchObject({ in_ms: 0, out_ms: 1000 });
  });
});

function panel(source = asset(), readJob = vi.fn(async () => job())) {
  const props = { request: { id: 'handoff', reference: { asset_id: source.id, version: source.version, digest: source.sha256 }, readAsset: vi.fn(async () => structuredClone(source)) },
    draft: draft(), canEdit: true, isCurrent: () => true, getRevision: () => '0', readJob, onApply: vi.fn(() => true) };
  return { props, ...render(<StudioTimelineAssetHandoff {...props} />) };
}
async function inspect() { click('核对交接素材版本'); await screen.findByLabelText('交接目标轨道'); set('交接目标轨道', 'audio'); }
describe('bounded handoff range UI', () => {
  it('rereads the original proof at acceptance and uses the exact short range', async () => {
    const state = panel(); await inspect(); expect(end().value).toBe('800'); expect(state.props.readJob).toHaveBeenCalledTimes(1);
    click('明确加入原时间线草稿'); await screen.findByText(/已把核对的原素材版本加入/);
    expect(state.props.readJob).toHaveBeenCalledTimes(2); expect(state.props.onApply).toHaveBeenCalledWith('audio', asset(), { in_ms: 0, out_ms: 800 });
  });
  it('requires an explicit unknown-source range and never probes or guesses metadata', async () => {
    const unknown = asset(); delete unknown.provenance; const state = panel(unknown); await inspect();
    expect(end().value).toBe(''); expect((screen.getByRole('button', { name: '明确加入原时间线草稿' }) as HTMLButtonElement).disabled).toBe(true);
    expect(state.props.readJob).not.toHaveBeenCalled(); set('交接来源起点（毫秒）', '20'); set('交接来源终点（毫秒）', '700');
    click('明确加入原时间线草稿'); await screen.findByText(/已把核对的原素材版本加入/);
    expect(state.props.onApply).toHaveBeenCalledWith('audio', unknown, { in_ms: 20, out_ms: 700 });
  });
  it('does not apply an automatic range after its receipt disappears or stops being approved', async () => {
    const changed = job(); changed.status = 'UNKNOWN'; const state = panel(asset(), vi.fn().mockResolvedValueOnce(job()).mockResolvedValue(changed));
    await inspect(); click('明确加入原时间线草稿'); await screen.findByText(/原输出时长回执缺失或已变化/); expect(state.props.onApply).not.toHaveBeenCalled();
    expect(end().value).toBe('800');
  });
  it('preserves partial authored range across a subsequent explicit metadata read', async () => {
    panel(); await inspect(); set('交接来源起点（毫秒）', '50'); set('交接来源终点（毫秒）', ''); click('核对交接素材版本');
    await screen.findByLabelText('交接目标轨道'); expect((screen.getByLabelText('交接来源起点（毫秒）') as HTMLInputElement).value).toBe('50'); expect(end().value).toBe('');
  });
  it.each(['identity', 'selection', 'unmount'] as const)('drops late duration proof after %s', async mode => {
    const waiting = deferred<ProductionJob>(), state = panel(asset(), vi.fn(() => waiting.promise));
    click('核对交接素材版本'); await act(async () => {});
    if (mode === 'identity') state.rerender(<StudioTimelineAssetHandoff {...state.props} isCurrent={() => false} />);
    if (mode === 'selection') state.rerender(<StudioTimelineAssetHandoff {...state.props} request={{ ...state.props.request, id: 'new' }} />);
    if (mode === 'unmount') state.unmount();
    await act(async () => waiting.resolve(job())); expect(screen.queryByText(/实测时长 800/)).toBeNull(); expect(state.props.onApply).not.toHaveBeenCalled();
  });
  it('leaves missing or mismatched proof unknown instead of authorizing an automatic range', async () => {
    panel(asset(), vi.fn().mockRejectedValue(new Error('unavailable'))); await inspect(); expect(end().value).toBe('');
    expect(screen.getByText(/来源时长尚未由原输出回执验证/)).toBeTruthy();
  });
});

describe('ordinary picker keeps the same no-guess rule', () => {
  it('uses a current approved duration on the explicit add click', async () => {
    const onApply = vi.fn(() => true), readJob = vi.fn(async () => job());
    render(<StudioTimelineAssetPicker asset={asset()} canEdit isCurrent={() => true} getRevision={() => '0'} readJob={readJob} onApply={onApply} />);
    expect(readJob).not.toHaveBeenCalled(); click('将所选素材加入轨道'); await screen.findByText(/已把精确素材和来源范围加入/);
    expect(onApply).toHaveBeenCalledWith({ in_ms: 0, out_ms: 800 });
  });
  it('does not replace a partial manual range with an automatic default', () => {
    const onApply = vi.fn(() => true); render(<StudioTimelineAssetPicker asset={asset()} canEdit isCurrent={() => true} getRevision={() => '0'} readJob={async () => job()} onApply={onApply} />);
    set('所选素材来源起点（毫秒）', '50'); expect((screen.getByRole('button', { name: '将所选素材加入轨道' }) as HTMLButtonElement).disabled).toBe(true);
    expect(onApply).not.toHaveBeenCalled();
  });
  it('ignores a late receipt after an original draft generation changes', async () => {
    let revision = '0'; const waiting = deferred<ProductionJob>(), onApply = vi.fn(() => true);
    render(<StudioTimelineAssetPicker asset={asset()} canEdit isCurrent={() => true} getRevision={() => revision} readJob={() => waiting.promise} onApply={onApply} />);
    click('将所选素材加入轨道'); revision = '2'; await act(async () => waiting.resolve(job())); expect(onApply).not.toHaveBeenCalled();
  });
});
