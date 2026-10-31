// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { ClipInspectorPanel } from '../nle/ClipInspectorPanel';
import { applyClipColorOperation, clipColorOperation } from '../nle/timelineClipColor';
import { StudioTimelineEditor } from './StudioTimelineEditor';
import { checkedTimeline, checkedTimelineRow, cloneTimeline, type StudioTimelineDraft } from './studioTimelineTypes';
import type { StudioProductionClient } from './studioProductionClient';
import type { StudioTimelineEditorProps } from './useStudioTimelineEditor';
import type { StudioAsset } from './studioClient';
import { audioTimelineRow } from './studioAudioTimeline.testFixtures';

const neutral = { brightness: 0, contrast: 1, saturation: 1 }, adjusted = { brightness: .2, contrast: 1.25, saturation: .5 };
const source = { id: 'image', kind: 'ASSET', asset_kind: 'image', version: 1, digest: 'a'.repeat(64) };
function row() {
  return checkedTimelineRow({ id: 'timeline-color', version: 1, timeline_digest: 'b'.repeat(64), title: 'Basic color', created_at: '', updated_at: '',
    timeline: { schema_version: 2, duration_ms: 1000, width: 64, height: 64, fps: 10, captions: [], tracks: [
      { id: 'picture', kind: 'VIDEO', order: 0, muted: false, gain_db: 0, clips: [{ id: 'swatch', source_snapshot: source, start_ms: 0, in_ms: 0, out_ms: 1000, x: 0, y: 0, width: 64, height: 64 }] }] } });
}
const clip = (value: ReturnType<typeof row>['timeline']) => value.tracks[0].clips[0];
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('closed basic color contract and original operation', () => {
  it('keeps absent settings absent and adds/removes only the selected clip property', () => {
    const input = row().timeline;
    expect(checkedTimeline(input)).toEqual(input); expect(clip(input)).not.toHaveProperty('color_adjustment');
    const op = clipColorOperation(input, ['swatch'], adjusted);
    expect(op).toEqual({ op: 'clip.update', clip_id: 'swatch', changes: { color_adjustment: adjusted } });
    const colored = applyClipColorOperation(input, ['swatch'], op);
    expect(clip(colored).color_adjustment).toEqual(adjusted); expect(clip(input)).not.toHaveProperty('color_adjustment');
    expect(applyClipColorOperation(colored, ['swatch'], clipColorOperation(colored, ['swatch'], null))).toEqual(input);
  });
  it.each([null, {}, [], 'eq=1', { brightness: 0, contrast: 1 }, { ...neutral, lut: '/private.cube' },
    { ...neutral, brightness: true }, { ...neutral, brightness: '0.2' }, { ...neutral, brightness: NaN },
    { ...neutral, brightness: Infinity }, { ...neutral, brightness: -1.01 }, { ...neutral, brightness: 1.01 },
    { ...neutral, contrast: -.01 }, { ...neutral, contrast: 2.01 }, { ...neutral, saturation: -.01 }, { ...neutral, saturation: 3.01 }])('rejects malformed saved color %j', bad => {
    const input = row().timeline; (clip(input) as any).color_adjustment = bad;
    expect(() => checkedTimeline(input)).toThrow();
  });
  it.each(['schema1', 'audio3', 'audio2', 'locked', 'multi', 'wrongclip', 'extra', 'undefined'])('rejects %s without a second editing contract', fault => {
    let input = row().timeline; let selected = ['swatch']; let op: any = { op: 'clip.update', clip_id: 'swatch', changes: { color_adjustment: adjusted } };
    if (fault === 'schema1') { delete input.schema_version; delete input.tracks[0].role; for (const key of ['speed_num', 'speed_den', 'muted', 'gain_db', 'fade_in_ms', 'fade_out_ms', 'opacity', 'include_audio']) delete (clip(input) as any)[key]; clip(input).source_snapshot.asset_kind = 'video'; }
    if (fault === 'audio3') { input = audioTimelineRow().timeline; selected = ['voice']; op.clip_id = 'voice'; }
    if (fault === 'audio2') { const audio = audioTimelineRow().timeline.tracks[0]; audio.order = 1; input.tracks.push(audio); selected = ['voice']; op.clip_id = 'voice'; }
    if (fault === 'locked') input.tracks[0].locked = true;
    if (fault === 'multi') selected = ['swatch', 'other'];
    if (fault === 'wrongclip') op.clip_id = 'other';
    if (fault === 'extra') op.changes.source_snapshot = source;
    if (fault === 'undefined') op.changes.color_adjustment = undefined;
    expect(() => applyClipColorOperation(input, selected, op)).toThrow();
  });
});

function inspector(input = row().timeline, selected = ['swatch'], editable = true) {
  const onEdit = vi.fn(); const props = { timeline: input, selectedClipIds: selected, editable, playheadMs: 0, marks: { inMs: null, outMs: null }, onEdit };
  return { onEdit, props, view: render(<ClipInspectorPanel {...props} />) };
}
it('stages Inspector controls, applies explicitly once, and rejects invalid values without emitting', () => {
  const state = inspector();
  fireEvent.change(screen.getByLabelText('调色亮度'), { target: { value: '0.2' } });
  fireEvent.change(screen.getByLabelText('调色对比度'), { target: { value: '1.25' } });
  fireEvent.change(screen.getByLabelText('调色饱和度'), { target: { value: '0.5' } });
  expect(state.onEdit).not.toHaveBeenCalled();
  const apply = screen.getByRole('button', { name: '将基础调色应用到草稿' }); fireEvent.click(apply); fireEvent.click(apply);
  expect(state.onEdit).toHaveBeenCalledTimes(1); expect(state.onEdit).toHaveBeenCalledWith({ kind: 'clip.update', payload: { op: 'clip.update', clip_id: 'swatch', changes: { color_adjustment: adjusted } } });
  fireEvent.change(screen.getByLabelText('调色亮度'), { target: { value: '2' } }); fireEvent.click(apply);
  expect(state.onEdit).toHaveBeenCalledTimes(1); expect(screen.getByText(/参数需要在 -1 至 1 范围内/)).toBeTruthy();
});
it('resets unapplied controls on target/context change and disables locked/multi-selection', () => {
  const state = inspector(); fireEvent.change(screen.getByLabelText('调色亮度'), { target: { value: '0.5' } });
  const next = cloneTimeline(state.props.timeline); clip(next).color_adjustment = adjusted;
  state.view.rerender(<ClipInspectorPanel {...state.props} timeline={next} />);
  expect((screen.getByLabelText('调色亮度') as HTMLInputElement).value).toBe('0.2');
  state.view.rerender(<ClipInspectorPanel {...state.props} timeline={next} editable={false} />);
  fireEvent.click(screen.getByRole('button', { name: '将基础调色应用到草稿' })); expect(state.onEdit).not.toHaveBeenCalled();
  state.view.rerender(<ClipInspectorPanel {...state.props} selectedClipIds={['swatch', 'other']} />);
  fireEvent.click(screen.getByRole('button', { name: '将基础调色应用到草稿' })); expect(state.onEdit).not.toHaveBeenCalled();
});
it('does not expose color inputs on an audio Inspector', () => {
  inspector(audioTimelineRow().timeline, ['voice']); expect(screen.queryByLabelText('调色亮度')).toBeNull();
});

function setup(failure?: 'UNKNOWN' | 'CONFLICT') {
  let saved = row();
  const client = { timelineList: vi.fn(async () => ({ items: [cloneTimeline(saved)] })), timelineGet: vi.fn(async () => cloneTimeline(saved)),
    timelineSave: vi.fn(async (_id: string | undefined, body: StudioTimelineDraft & { expected_version: number }) => {
      if (failure) throw new ApiError({ status: failure === 'UNKNOWN' ? 503 : 409, code: failure === 'UNKNOWN' ? 'UNKNOWN' : 'EXPERIMENTAL_STALE_SOURCE', message: failure });
      saved = checkedTimelineRow({ ...saved, title: body.title, timeline: body.timeline, version: body.expected_version + 1, timeline_digest: 'c'.repeat(64) }); return cloneTimeline(saved);
    }), timelineRender: vi.fn(), timelineEdit: vi.fn(), timelinePlaybackPreview: vi.fn(), timelinePlaybackBuild: vi.fn(), list: vi.fn() };
  const props: StudioTimelineEditorProps = { client: client as unknown as StudioProductionClient,
    assets: [{ id: 'image', kind: 'image', version: 1, sha256: 'a'.repeat(64), filename: 'swatches.png', deleted_at: null }] as StudioAsset[],
    canMutate: true, busy: false, isCurrent: () => true, read: async work => work(), mutate: async work => work(), onDirtyChange: vi.fn(), onJob: vi.fn(), onUnavailable: vi.fn() };
  return { client, props, view: render(<StudioTimelineEditor {...props} />) };
}
async function adoptPanel() {
  await screen.findByRole('option', { name: /Basic color · v/ });
  fireEvent.change(screen.getByLabelText('读取已保存时间线'), { target: { value: 'timeline-color' } });
  const confirm = await screen.findByLabelText('已核对服务端内容与本地输入，确认以下选择'); fireEvent.click(confirm);
  fireEvent.click(screen.getByRole('button', { name: '采用服务端时间线' }));
  fireEvent.click(await screen.findByRole('button', { name: 'swatch' }));
}
function authorColor() {
  fireEvent.change(screen.getByLabelText('调色亮度'), { target: { value: '0.2' } });
  fireEvent.change(screen.getByLabelText('调色对比度'), { target: { value: '1.25' } });
  fireEvent.change(screen.getByLabelText('调色饱和度'), { target: { value: '0.5' } });
  fireEvent.click(screen.getByRole('button', { name: '将基础调色应用到草稿' }));
}
it('routes mounted Inspector through staged draft/undo/explicit Save and original reopen without rendering', async () => {
  const state = setup(); await adoptPanel(); authorColor();
  expect(state.client.timelineSave).not.toHaveBeenCalled(); expect(state.client.timelineEdit).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '撤销本地编辑' })); expect((screen.getByLabelText('调色亮度') as HTMLInputElement).value).toBe('0');
  fireEvent.click(screen.getByRole('button', { name: '重做本地编辑' })); expect((screen.getByLabelText('调色亮度') as HTMLInputElement).value).toBe('0.2');
  fireEvent.click(screen.getByRole('button', { name: '保存时间线' })); await waitFor(() => expect(state.client.timelineSave).toHaveBeenCalledTimes(1));
  const body = state.client.timelineSave.mock.calls[0][1]; expect(body.expected_version).toBe(1); expect(clip(body.timeline).color_adjustment).toEqual(adjusted);
  await screen.findByText(/已读取或保存 v2/); state.view.unmount(); render(<StudioTimelineEditor {...state.props} />); await adoptPanel();
  expect((screen.getByLabelText('调色亮度') as HTMLInputElement).value).toBe('0.2');
  fireEvent.click(screen.getByRole('button', { name: '移除片段调色' })); fireEvent.click(screen.getByRole('button', { name: '保存时间线' }));
  await waitFor(() => expect(state.client.timelineSave).toHaveBeenCalledTimes(2)); expect(clip(state.client.timelineSave.mock.calls[1][1].timeline)).not.toHaveProperty('color_adjustment');
  expect(state.client.timelineRender).not.toHaveBeenCalled(); expect(state.client.timelinePlaybackPreview).not.toHaveBeenCalled(); expect(state.client.timelinePlaybackBuild).not.toHaveBeenCalled();
});
it.each(['UNKNOWN', 'CONFLICT'] as const)('preserves applied color and blocks duplicate saves after %s', async failure => {
  const state = setup(failure); await adoptPanel(); authorColor();
  fireEvent.click(screen.getByRole('button', { name: '保存时间线' })); await waitFor(() => expect(state.client.timelineSave).toHaveBeenCalledTimes(1));
  await screen.findByText(failure === 'UNKNOWN' ? /保存结果不确定/ : /服务端版本已变化。输入保留/);
  fireEvent.click(screen.getByRole('button', { name: '保存时间线' })); expect(state.client.timelineSave).toHaveBeenCalledTimes(1);
  expect((screen.getByLabelText('调色亮度') as HTMLInputElement).value).toBe('0.2'); expect(state.client.timelineRender).not.toHaveBeenCalled();
});
