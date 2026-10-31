// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { StudioTimelineEditor } from './StudioTimelineEditor';
import type { StudioTimelineEditorProps } from './useStudioTimelineEditor';
import type { StudioProductionClient } from './studioProductionClient';
import { checkedTimelineRow, cloneTimeline, type StudioTimelineDraft } from './studioTimelineTypes';
import { selectionRemoveAssets, selectionRemoveRow } from '../nle/timelineSelectionRemove.testFixtures';

const routed = vi.hoisted(() => ({ edit: undefined as undefined | ((command: { kind: string; payload: unknown }) => void) }));
vi.mock('../nle/TimelineWorkspacePanel', async importOriginal => {
  const actual = await importOriginal<typeof import('../nle/TimelineWorkspacePanel')>();
  return { ...actual, TimelineWorkspacePanel: (props: React.ComponentProps<typeof actual.TimelineWorkspacePanel>) => {
    routed.edit = props.onEdit; return <actual.TimelineWorkspacePanel {...props} />;
  } };
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const ids = ['video-remove', 'audio-remove'];
const batch = () => ({ kind: 'clip.remove', payload: ids.map(clip_id => ({ op: 'clip.remove', clip_id, ripple: false })) });
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
function setup() {
  let saved = selectionRemoveRow();
  const client = { timelineList: vi.fn(async () => ({ items: [cloneTimeline(saved)] })),
    timelineGet: vi.fn(async () => cloneTimeline(saved)),
    timelineSave: vi.fn(async (_id: string | undefined, body: StudioTimelineDraft & { expected_version: number }) => {
      saved = checkedTimelineRow({ ...saved, title: body.title, timeline: body.timeline,
        version: body.expected_version + 1, timeline_digest: 'c'.repeat(64) }); return cloneTimeline(saved);
    }), timelineEdit: vi.fn(), timelineRender: vi.fn() };
  const network = vi.fn(); vi.stubGlobal('fetch', network);
  const props: StudioTimelineEditorProps = { client: client as unknown as StudioProductionClient, assets: selectionRemoveAssets(),
    canMutate: true, busy: false, projectId: 'project-remove', isCurrent: () => true, read: work => work(), mutate: work => work(),
    onDirtyChange: vi.fn(), onJob: vi.fn(), onUnavailable: vi.fn() };
  return { client, network, props, view: render(<StudioTimelineEditor {...props} />) };
}
async function open(version = 1) {
  await screen.findByRole('option', { name: `Selection remove fixture · v${version}` });
  fireEvent.change(screen.getByLabelText('读取已保存时间线'), { target: { value: 'timeline-selection-remove' } });
  await screen.findByRole('heading', { name: `Selection remove fixture · v${version}` });
  fireEvent.click(screen.getByLabelText('已核对服务端内容与本地输入，确认以下选择')); click('采用服务端时间线');
}
function select() { click('video-remove'); fireEvent.click(screen.getByRole('button', { name: 'audio-remove' }), { ctrlKey: true }); }
const noHistory = () => expect((screen.getByRole('button', { name: '撤销本地编辑' }) as HTMLButtonElement).disabled).toBe(true);

it('removes video+audio without ripple in one history step, explicitly CAS saves once and reopens unchanged neighbors', async () => {
  const state = setup(); await open(); select();
  const preview = screen.getByRole('region', { name: '所选片段删除预览' });
  expect(within(preview).getByText(/1000 — 3000 毫秒/)).toBeTruthy();
  click('删除所选片段（保留间隙）');
  expect(screen.getByText(/所选片段已删除并保留间隙/)).toBeTruthy(); expect(state.client.timelineSave).not.toHaveBeenCalled();
  expect(screen.queryByRole('button', { name: 'video-remove' })).toBeNull(); expect(screen.queryByRole('button', { name: 'audio-remove' })).toBeNull();
  click('撤销本地编辑'); noHistory(); expect(screen.getByRole('button', { name: 'audio-remove' })).toBeTruthy();
  click('重做本地编辑'); click('保存时间线');
  await waitFor(() => expect(state.client.timelineSave).toHaveBeenCalledTimes(1));
  const body = state.client.timelineSave.mock.calls[0][1], expected = selectionRemoveRow().timeline;
  expected.tracks.forEach(track => { track.clips = track.clips.filter(clip => !ids.includes(clip.id)); });
  expect(body.expected_version).toBe(1); expect(body.timeline).toEqual(expected);
  expect(state.client.timelineEdit).not.toHaveBeenCalled(); expect(state.client.timelineRender).not.toHaveBeenCalled(); expect(state.network).not.toHaveBeenCalled();
  state.view.unmount(); render(<StudioTimelineEditor {...state.props} />); await open(2);
  expect((within(screen.getByRole('region', { name: '轨道 2 片段 1' })).getByLabelText('放入时间线（毫秒）') as HTMLInputElement).value).toBe('4500');
  expect(screen.getByDisplayValue('Keep this caption')).toBeTruthy(); expect(state.client.timelineSave).toHaveBeenCalledTimes(1);
});

it('rejects incomplete, extra, ripple and foreign batches, plus selection/draft ABA retained callbacks', async () => {
  const state = setup(); await open(); select();
  const original = batch();
  for (const payload of [original.payload.slice(1), [...original.payload, original.payload[0]],
    original.payload.map(op => ({ ...op, ripple: true })), original.payload.map(op => ({ ...op, extra: 1 })),
    original.payload.map(op => ({ ...op, clip_id: 'video-keep' }))]) {
    act(() => routed.edit!({ kind: 'clip.remove', payload })); noHistory();
  }
  const old = routed.edit!; click('audio-keep'); select(); act(() => old(original)); noHistory();
  const beforeEdit = routed.edit!; act(() => routed.edit!(original));
  click('撤销本地编辑'); select(); act(() => beforeEdit(original)); noHistory();
  expect(state.client.timelineSave).not.toHaveBeenCalled(); expect(state.network).not.toHaveBeenCalled();
});

it('rejects retained bridge callbacks after observed authority/busy/permission/project ABA and unmount', async () => {
  const state = setup(); await open(); select();
  const old = routed.edit!;
  for (const delta of [{ isCurrent: () => false }, { busy: true }, { canMutate: false }, { projectId: 'other' }]) {
    state.view.rerender(<StudioTimelineEditor {...state.props} {...delta} />);
    state.view.rerender(<StudioTimelineEditor {...state.props} />);
    act(() => old(batch())); noHistory();
  }
  state.view.unmount(); act(() => old(batch()));
  expect(state.client.timelineSave).not.toHaveBeenCalled(); expect(state.client.timelineEdit).not.toHaveBeenCalled(); expect(state.network).not.toHaveBeenCalled();
});
