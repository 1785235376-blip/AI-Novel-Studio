// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { captionCommand } from '../nle/timelineOps';
import { StudioTimelineCaptionStyle } from './StudioTimelineCaptionStyle';
import { StudioTimelineEditor } from './StudioTimelineEditor';
import { applyNleCaptionCommand } from './nleCaptionEditing';
import { audioTimelineAssets, audioTimelineRow } from './studioAudioTimeline.testFixtures';
import { checkedTimeline, checkedTimelineCaptionStyle, checkedTimelineRow, cloneTimeline,
  type StudioTimelineCaptionStyle as CaptionStyle, type StudioTimelineDraft } from './studioTimelineTypes';
import type { StudioProductionClient } from './studioProductionClient';
import type { StudioTimelineEditorProps } from './useStudioTimelineEditor';
import type { StudioAsset } from './studioClient';

const suggested: CaptionStyle = { font_size: 24, primary_color: '#FFFFFF', alignment: 'BOTTOM_CENTER', outline_width: 1 };
const authored: CaptionStyle = { font_size: 36, primary_color: '#12ABEF', alignment: 'TOP_CENTER', outline_width: 3 };
const source = { id: 'video', kind: 'ASSET', asset_kind: 'video', version: 1, digest: 'a'.repeat(64) };
const sizeLabel = '字幕字号（libass 参考单位）', colorLabel = '字幕颜色（#RRGGBB）';
const applyLabel = '将字幕样式应用到本地草稿', removeLabel = '移除全局字幕样式';
function row(extended = true) {
  return checkedTimelineRow({ id: 'timeline-captions', version: 1, timeline_digest: 'b'.repeat(64), title: 'Caption style', created_at: '', updated_at: '',
    timeline: { ...(extended ? { schema_version: 2 } : {}), duration_ms: 1000, width: 64, height: 64, fps: 10,
      captions: [{ start_ms: 0, end_ms: 1000, text: 'Caption' }], tracks: [
        { id: 'picture', kind: 'VIDEO', order: 0, muted: false, gain_db: 0, clips: [
          { id: 'shot', source_snapshot: source, start_ms: 0, in_ms: 0, out_ms: 1000, x: 0, y: 0, width: 64, height: 64 }] }] } });
}
const button = (name: string) => screen.getByRole('button', { name });
const input = (label: string) => screen.getByLabelText(label) as HTMLInputElement;
const handler = (element: HTMLElement) => (element as any)[Object.keys(element).find(key => key.startsWith('__reactProps$'))!].onClick;
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('closed optional caption style', () => {
  it('keeps original absence and canonicalizes only an explicitly supplied style', () => {
    const original = row().timeline;
    expect(checkedTimeline(original)).toEqual(original); expect(original).not.toHaveProperty('caption_style');
    expect(checkedTimeline({ ...original, caption_style: { ...authored, primary_color: '#12abef' } }).caption_style).toEqual(authored);
    expect(checkedTimelineCaptionStyle({ ...suggested, font_size: 8, outline_width: 0 })).toMatchObject({ font_size: 8, outline_width: 0 });
    expect(checkedTimelineCaptionStyle({ ...suggested, font_size: 72, outline_width: 4 })).toMatchObject({ font_size: 72, outline_width: 4 });
  });
  it.each([null, undefined, {}, [], 'FontSize=24', { font_size: 24 }, { ...suggested, font_name: 'Any' }, { ...suggested, ass: 'Override' },
    { ...suggested, font_size: true }, { ...suggested, font_size: '24' }, { ...suggested, font_size: NaN }, { ...suggested, font_size: Infinity },
    { ...suggested, font_size: 7 }, { ...suggested, font_size: 73 }, { ...suggested, font_size: 24.5 },
    { ...suggested, primary_color: '#fff' }, { ...suggested, primary_color: '#12345678' }, { ...suggested, primary_color: '#FF0000\n' },
    { ...suggested, primary_color: '#GG0000' }, { ...suggested, primary_color: 'red' }, { ...suggested, primary_color: ' #FFFFFF' },
    { ...suggested, alignment: 'BOTTOM_LEFT' }, { ...suggested, alignment: 2 }, { ...suggested, outline_width: -.1 },
    { ...suggested, outline_width: 5 }, { ...suggested, outline_width: 1.1 }, { ...suggested, outline_width: false },
    { font_size: 24, primary_color: '#FFFFFF', alignment: 'BOTTOM_CENTER' }])('rejects invalid saved styles %j', bad => {
    expect(() => checkedTimeline({ ...row().timeline, caption_style: bad })).toThrow();
  });
  it.each([suggested, null, undefined])('rejects style on original schema and audio schema even when null: %j', style => {
    expect(() => checkedTimeline({ ...row(false).timeline, caption_style: style })).toThrow();
    expect(() => checkedTimeline({ ...audioTimelineRow().timeline, caption_style: style })).toThrow();
  });
  it('preserves style and absence through existing caption insert/update/remove commands', () => {
    for (const style of [undefined, authored]) {
      let draft: StudioTimelineDraft = row(); if (style) draft.timeline.caption_style = style;
      const caption = { start_ms: 0, end_ms: 500, text: 'Added' };
      expect(captionCommand('caption-insert', { timeline: draft.timeline, caption }).ok).toBe(true);
      draft = applyNleCaptionCommand(draft, 'caption.insert', { op: 'caption.insert', caption });
      draft = applyNleCaptionCommand(draft, 'caption.update', { op: 'caption.update', index: 0, caption: { ...caption, text: 'Updated' } });
      draft = applyNleCaptionCommand(draft, 'caption.remove', { op: 'caption.remove', index: 0 });
      if (style) expect(draft.timeline.caption_style).toEqual(style); else expect(draft.timeline).not.toHaveProperty('caption_style');
    }
  });
});

function stageStyle() {
  fireEvent.change(input(sizeLabel), { target: { value: '36' } });
  fireEvent.change(input(colorLabel), { target: { value: '#12abef' } });
  fireEvent.change(screen.getByLabelText('字幕位置'), { target: { value: 'TOP_CENTER' } });
  fireEvent.change(input('字幕描边宽度'), { target: { value: '3' } });
}
function controls() {
  let revision = '1', current = true;
  const props = { draft: row(), scope: {}, disabled: false, isCurrent: () => current, getRevision: () => revision, onApply: vi.fn(() => true) };
  return { props, view: render(<StudioTimelineCaptionStyle {...props} />), setRevision: (value: string) => { revision = value; }, setCurrent: (value: boolean) => { current = value; } };
}
it('stages controls, validates and consumes retained apply only once', () => {
  const state = controls(); stageStyle(); expect(state.props.onApply).not.toHaveBeenCalled();
  const apply = handler(button(applyLabel)); act(() => { apply(); apply(); });
  expect(state.props.onApply).toHaveBeenCalledTimes(1); expect(state.props.onApply).toHaveBeenCalledWith(authored);
});
it.each([[sizeLabel, '7'], [sizeLabel, '24.5'], [sizeLabel, ''], [colorLabel, '#ab'], ['字幕描边宽度', '5']])('rejects invalid staged %s=%s', (label, value) => {
  const state = controls(); fireEvent.change(input(label), { target: { value } }); fireEvent.click(button(applyLabel));
  expect(state.props.onApply).not.toHaveBeenCalled(); expect(screen.getByRole('status')).toBeTruthy();
});
it.each(['scope', 'draft', 'disabled', 'revision', 'current', 'edit', 'unmount'])('rejects retained callbacks after %s changes', reason => {
  const state = controls(); stageStyle(); const retained = handler(button(applyLabel));
  if (reason === 'scope') state.view.rerender(<StudioTimelineCaptionStyle {...state.props} scope={{}} />);
  if (reason === 'draft') state.view.rerender(<StudioTimelineCaptionStyle {...state.props} draft={cloneTimeline(state.props.draft)} />);
  if (reason === 'disabled') state.view.rerender(<StudioTimelineCaptionStyle {...state.props} disabled />);
  if (reason === 'revision') state.setRevision('2');
  if (reason === 'current') state.setCurrent(false);
  if (reason === 'edit') fireEvent.change(input(sizeLabel), { target: { value: '40' } });
  if (reason === 'unmount') state.view.unmount();
  act(() => retained()); expect(state.props.onApply).not.toHaveBeenCalled();
  if (['scope', 'draft', 'disabled'].includes(reason)) expect(input(sizeLabel).value).toBe('24');
});

function setup(options: { failure?: 'UNKNOWN' | 'CONFLICT'; extended?: boolean; audio?: boolean; locked?: boolean } = {}) {
  let saved = options.audio ? audioTimelineRow() : row(options.extended ?? true);
  if (options.locked) saved.timeline.tracks[0].locked = true;
  const client = { timelineList: vi.fn(async () => ({ items: [cloneTimeline(saved)] })), timelineGet: vi.fn(async () => cloneTimeline(saved)),
    timelineSave: vi.fn(async (_id: string | undefined, body: StudioTimelineDraft & { expected_version: number }) => {
      if (options.failure) throw new ApiError({ status: options.failure === 'UNKNOWN' ? 503 : 409, code: options.failure, message: options.failure });
      saved = checkedTimelineRow({ ...saved, title: body.title, timeline: body.timeline, version: body.expected_version + 1, timeline_digest: 'c'.repeat(64) }); return cloneTimeline(saved);
    }), timelineRender: vi.fn(), timelineEdit: vi.fn(), timelinePlaybackPreview: vi.fn(), timelinePlaybackBuild: vi.fn(), list: vi.fn() };
  const props: StudioTimelineEditorProps = { client: client as unknown as StudioProductionClient,
    assets: options.audio ? audioTimelineAssets() : [{ id: 'video', kind: 'video', version: 1, sha256: 'a'.repeat(64), filename: 'sample.mp4', deleted_at: null }] as StudioAsset[],
    canMutate: true, busy: false, mediaKind: options.audio ? 'AUDIO' : 'VIDEO', isCurrent: () => true, read: work => work(), mutate: work => work(),
    onDirtyChange: vi.fn(), onJob: vi.fn(), onUnavailable: vi.fn() };
  return { client, props, id: saved.id, title: saved.title, view: render(<StudioTimelineEditor {...props} />) };
}
async function adopt(id = 'timeline-captions', title = 'Caption style') {
  await screen.findByRole('option', { name: new RegExp(`${title} · v`) });
  fireEvent.change(screen.getByLabelText('读取已保存时间线'), { target: { value: id } });
  fireEvent.click(await screen.findByLabelText('已核对服务端内容与本地输入，确认以下选择'));
  fireEvent.click(button('采用服务端时间线'));
}
it('uses mounted editor stage/apply/undo/redo/explicit Save/reopen/reset without automatic calls', async () => {
  const state = setup(); await adopt(); expect(input(sizeLabel).value).toBe('24');
  stageStyle(); expect((button('撤销本地编辑') as HTMLButtonElement).disabled).toBe(true);
  expect(state.client.timelineSave).not.toHaveBeenCalled(); fireEvent.click(button(applyLabel));
  expect(input(colorLabel).value).toBe('#12ABEF'); expect(state.client.timelineSave).not.toHaveBeenCalled();
  fireEvent.click(button('撤销本地编辑')); expect(input(sizeLabel).value).toBe('24'); expect((button(removeLabel) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(button('重做本地编辑')); expect(input(sizeLabel).value).toBe('36');
  fireEvent.click(button('保存时间线')); await waitFor(() => expect(state.client.timelineSave).toHaveBeenCalledTimes(1));
  expect(state.client.timelineSave.mock.calls[0][1].expected_version).toBe(1);
  expect(state.client.timelineSave.mock.calls[0][1].timeline.caption_style).toEqual(authored);
  await screen.findByText(/已读取或保存 v2/); state.view.unmount(); render(<StudioTimelineEditor {...state.props} />); await adopt();
  expect(input(sizeLabel).value).toBe('36'); expect(input(colorLabel).value).toBe('#12ABEF');
  fireEvent.click(button(removeLabel)); expect(input(sizeLabel).value).toBe('24');
  fireEvent.click(button('撤销本地编辑')); expect(input(sizeLabel).value).toBe('36');
  fireEvent.click(button('重做本地编辑')); fireEvent.click(button('保存时间线'));
  await waitFor(() => expect(state.client.timelineSave).toHaveBeenCalledTimes(2));
  expect(state.client.timelineSave.mock.calls[1][1].timeline).not.toHaveProperty('caption_style');
  expect(state.client.timelineEdit).not.toHaveBeenCalled(); expect(state.client.timelineRender).not.toHaveBeenCalled();
  expect(state.client.timelinePlaybackPreview).not.toHaveBeenCalled(); expect(state.client.timelinePlaybackBuild).not.toHaveBeenCalled();
});
it.each(['UNKNOWN', 'CONFLICT'] as const)('preserves authored style and prevents further actions after %s Save', async failure => {
  const state = setup({ failure }); await adopt(); stageStyle(); fireEvent.click(button(applyLabel)); fireEvent.click(button('保存时间线'));
  await screen.findByText(failure === 'UNKNOWN' ? /保存结果不确定/ : /服务端版本已变化。输入保留/);
  fireEvent.click(button('保存时间线')); fireEvent.click(button(removeLabel));
  expect(state.client.timelineSave).toHaveBeenCalledTimes(1); expect(input(sizeLabel).value).toBe('36'); expect(state.client.timelineRender).not.toHaveBeenCalled();
});
it('keeps global caption styles editable when media tracks are locked', async () => {
  const state = setup({ locked: true }); await adopt(); stageStyle(); fireEvent.click(button(applyLabel)); fireEvent.click(button('保存时间线'));
  await waitFor(() => expect(state.client.timelineSave).toHaveBeenCalledTimes(1));
  expect(state.client.timelineSave.mock.calls[0][1].timeline.caption_style).toEqual(authored);
  expect(state.client.timelineSave.mock.calls[0][1].timeline.tracks[0].locked).toBe(true);
});
it('requires the existing explicit schema upgrade before exposing style controls', async () => {
  const state = setup({ extended: false }); await adopt(); expect(screen.queryByLabelText(sizeLabel)).toBeNull();
  expect(screen.getByText('全局字幕样式需要先明确采用扩展编辑版本 2。')).toBeTruthy();
  fireEvent.click(button('明确采用扩展编辑（版本 2，需重新保存）')); expect(input(sizeLabel).value).toBe('24');
  fireEvent.click(button('保存时间线')); await waitFor(() => expect(state.client.timelineSave).toHaveBeenCalledTimes(1));
  expect(state.client.timelineSave.mock.calls[0][1].timeline.schema_version).toBe(2);
  expect(state.client.timelineSave.mock.calls[0][1].timeline).not.toHaveProperty('caption_style');
});
it('does not expose caption style in the audio editor', async () => {
  const state = setup({ audio: true }); await adopt(state.id, state.title); expect(screen.queryByLabelText(sizeLabel)).toBeNull();
  expect(screen.queryByText('全局字幕样式')).toBeNull(); expect(state.client.timelineSave).not.toHaveBeenCalled();
});
