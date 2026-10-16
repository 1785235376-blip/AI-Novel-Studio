// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { TimelineTransferReview } from './TimelineTransferReview';
import { transferClipTarget } from './timelineTransferReview';
import { StudioTimelineEditor } from './StudioTimelineEditor';
import type { StudioTimelineEditorProps } from './useStudioTimelineEditor';
import type { StudioProductionClient } from './studioProductionClient';
import type { StudioAsset } from './studioClient';
import { checkedTimelineRow, timelineSources } from './studioTimelineTypes';
import type { TimelineTransferPreview } from './studioTimelineTransferTypes';
import capture from './fixtures/phase6.capture.editing-pipeline.json';
const captured = vi.hoisted(() => ({ props: undefined as undefined | { controller: import('./useStudioTimelineTransfer').StudioTimelineTransferController; onLocate?: (preview: TimelineTransferPreview, path: string) => void } }));
vi.mock('./StudioTimelineTransferPanel', async importOriginal => {
  const original = await importOriginal<typeof import('./StudioTimelineTransferPanel')>();
  return { ...original, StudioTimelineTransferPanel: (props: Parameters<typeof original.StudioTimelineTransferPanel>[0]) => {
    captured.props = props; return <original.StudioTimelineTransferPanel {...props} />;
  } };
});
const source = () => checkedTimelineRow(structuredClone(capture.created));
function preview(): TimelineTransferPreview {
  const row = source();
  return { contract: 'studio-timeline-transfer-preview/1', direction: 'EXPORT', format: 'OTIO',
    timeline_snapshot: { id: row.id, version: row.version, digest: row.timeline_digest }, input_digest: 'a'.repeat(64), timeline: row.timeline,
    timeline_digest: row.timeline_digest, sources: timelineSources(row.timeline), media_bindings: [],
    loss_report: [{ path: 'tracks[0].clips[0]', code: 'VIDEO_GEOMETRY_OPACITY_REQUIRE_STUDIO_METADATA', severity: 'LOSS' }],
    requires_loss_acknowledgment: true, output_sha256: 'b'.repeat(64), output_bytes: 100, external_media_access: false, model_called: false,
    automatic_replay: false, product_acceptance: 'LOCAL_REQUIRED', target_applications: { Resolve: 'NOT_RUN', Premiere: 'NOT_RUN' }, preview_digest: 'c'.repeat(64) };
}
beforeEach(() => vi.stubGlobal('crypto', webcrypto));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
it('resolves indexed and speed-ID export paths without guessing imported indices', () => {
  const p = preview(), clip = p.timeline.tracks[0].clips[0];
  expect(transferClipTarget(p, 'tracks[0].clips[0]')?.clip).toBe(clip);
  expect(transferClipTarget(p, 'tracks[0].clips[0].transition_out')?.clip).toBe(clip);
  expect(transferClipTarget(p, `tracks[0].clips.${clip.id}`)?.clip).toBe(clip);
  expect(transferClipTarget({ ...p, direction: 'IMPORT' }, 'tracks[0].clips[0]')).toBeUndefined();
});
it.each(['tracks[00].clips[0]', 'tracks[-1].clips[0]', 'tracks[0].items[0]', 'tracks[0].clips[100]', 'tracks[0].clips[0].other', 'tracks[0]', 'captions'])('withholds unproven location %s', path => {
  expect(transferClipTarget(preview(), path)).toBeUndefined();
});
it('rejects ambiguous clip IDs and duplicate tracks', () => {
  const p = preview(); p.timeline.tracks[0].clips.push(structuredClone(p.timeline.tracks[0].clips[0]));
  expect(transferClipTarget(p, 'tracks[0].clips[0]')).toBeUndefined();
  const q = preview(); q.timeline.tracks.push(structuredClone(q.timeline.tracks[0])); expect(transferClipTarget(q, 'tracks[0].clips[0]')).toBeUndefined();
});
it('shows original pins and exact integers, bounded pages and untranslated unknown codes', () => {
  const p = preview(), locate = vi.fn(); p.loss_report = Array.from({ length: 21 }, (_, i) => ({ path: 'tracks[0].clips[0]', code: i ? 'UNKNOWN_NEW_LIMIT' : 'VIDEO_GEOMETRY_OPACITY_REQUIRE_STUDIO_METADATA', severity: 'LOSS' }));
  const pin = p.timeline.tracks[0].clips[0].source_snapshot; p.media_bindings = [{ reference: 'media/exact-pin', source_snapshot: { version: pin.version, digest: pin.digest, id: pin.id, kind: pin.kind, asset_kind: pin.asset_kind } }];
  const before = JSON.stringify(p); render(<TimelineTransferReview preview={p} disabled={false} onLocate={locate} />);
  expect(screen.getAllByRole('listitem')).toHaveLength(20); expect(screen.getAllByText('media/exact-pin')).toHaveLength(20); expect(screen.getByText(/画面位置、尺寸/)).toBeTruthy();
  expect(screen.getAllByText(p.timeline.tracks[0].clips[0].source_snapshot.digest)).toHaveLength(20);
  fireEvent.click(screen.getAllByRole('button', { name: /定位原片段/ })[0]); expect(locate).toHaveBeenCalledWith(p, 'tracks[0].clips[0]');
  fireEvent.click(screen.getByRole('button', { name: '下一页限制' })); expect(screen.getAllByRole('listitem')).toHaveLength(1);
  expect(screen.getByText('UNKNOWN_NEW_LIMIT')).toBeTruthy(); expect(JSON.stringify(p)).toBe(before);
});
it('does not claim OTIO support for subtitles or locate imported paths', () => {
  render(<TimelineTransferReview preview={{ ...preview(), direction: 'IMPORT', format: 'SRT' }} disabled={false} />);
  expect(screen.queryByText(/OTIO 原生子集/)).toBeNull(); expect(screen.queryByRole('button', { name: /定位原片段/ })).toBeNull();
});
async function mounted() {
  const p = preview(), row = source();
  const client = { timelineList: vi.fn().mockResolvedValue({ items: [row] }), timelineGet: vi.fn().mockResolvedValue(row), timelineSave: vi.fn(), timelineRender: vi.fn(), list: vi.fn(),
    timelineTransferPreview: vi.fn().mockResolvedValue(p), timelineTransferImport: vi.fn(), timelineTransferAttachment: vi.fn() };
  const props: StudioTimelineEditorProps = { client: client as unknown as StudioProductionClient, assets: [structuredClone(capture.video_source)] as unknown as StudioAsset[], canMutate: true, busy: false,
    isCurrent: () => true, read: async work => work(), mutate: async work => work(), onDirtyChange: vi.fn(), onUnavailable: vi.fn(), onJob: vi.fn() };
  const view = render(<StudioTimelineEditor {...props} />);
  await screen.findByRole('option', { name: new RegExp(row.title) });
  fireEvent.change(screen.getByLabelText('读取已保存时间线'), { target: { value: row.id } });
  await screen.findByRole('region', { name: '核对服务端时间线' });
  fireEvent.click(screen.getByLabelText('已核对服务端内容与本地输入，确认以下选择'));
  fireEvent.click(screen.getByRole('button', { name: '采用服务端时间线' }));
  fireEvent.click(screen.getByRole('button', { name: '读取转换预览' }));
  await screen.findByRole('button', { name: /定位原片段/ });
  return { p, row, client, props, view };
}
it('locates the exact original mounted clip without saving, granting consent or discarding local controls', async () => {
  const { client } = await mounted();
  const target = screen.getByRole('region', { name: '轨道 1 片段 1' });
  fireEvent.change(screen.getByLabelText('拆分位置（时间线毫秒）'), { target: { value: '333' } });
  fireEvent.change(screen.getByLabelText('复制或移动至（时间线毫秒）'), { target: { value: '222' } });
  fireEvent.click(screen.getByRole('button', { name: /定位原片段/ })); expect(document.activeElement).toBe(target);
  expect((screen.getByLabelText('拆分位置（时间线毫秒）') as HTMLInputElement).value).toBe('333');
  expect((screen.getByLabelText('复制或移动至（时间线毫秒）') as HTMLInputElement).value).toBe('222');
  expect((screen.getByLabelText('已读取全部损失和互通限制，接受本次转换') as HTMLInputElement).checked).toBe(false);
  expect(client.timelineSave).not.toHaveBeenCalled(); expect(client.timelineTransferImport).not.toHaveBeenCalled(); expect(client.timelineTransferAttachment).not.toHaveBeenCalled();
});
it('preserves dirty title and blocks location until the original draft is reconciled', async () => {
  const { client } = await mounted(); const title = screen.getByLabelText('名称') as HTMLInputElement;
  fireEvent.change(title, { target: { value: '保留未保存 🎬' } }); title.focus();
  const button = screen.getByRole('button', { name: /定位原片段/ }) as HTMLButtonElement;
  expect(button.disabled).toBe(true); fireEvent.click(button); expect(title.value).toBe('保留未保存 🎬'); expect(document.activeElement).toBe(title);
  expect(client.timelineSave).not.toHaveBeenCalled();
});
it('retains active IME input and blocks busy, changed-owner and stale-preview navigation', async () => {
  const { props, view } = await mounted(); const title = screen.getByLabelText('名称'); title.focus(); fireEvent.compositionStart(title);
  fireEvent.click(screen.getByRole('button', { name: /定位原片段/ })); expect(document.activeElement).toBe(title);
  fireEvent.compositionEnd(title); view.rerender(<StudioTimelineEditor {...props} busy />);
  expect((screen.getByRole('button', { name: /定位原片段/ }) as HTMLButtonElement).disabled).toBe(true);
  view.rerender(<StudioTimelineEditor {...props} isCurrent={() => false} />);
  await waitFor(() => expect(screen.queryByRole('button', { name: /定位原片段/ })).toBeNull());
});

it('rejects a retained locator after same-batch export settings ABA without sending anything', async () => {
  const { p, client } = await mounted(), original = captured.props!;
  const title = screen.getByLabelText('名称'); title.focus();
  act(() => { original.controller.change({ format: 'SRT' }); original.controller.change({ format: 'OTIO' }); original.onLocate!(p, 'tracks[0].clips[0]'); });
  expect(document.activeElement).toBe(title); expect(screen.queryByRole('button', { name: /定位原片段/ })).toBeNull();
  expect(client.timelineTransferPreview).toHaveBeenCalledOnce(); expect(client.timelineTransferImport).not.toHaveBeenCalled();
});
it('rejects retained location after edits and undo restore the same contents', async () => {
  const { p, client } = await mounted(), original = captured.props!;
  const title = screen.getByLabelText('名称'); const initial = (title as HTMLInputElement).value;
  fireEvent.change(title, { target: { value: 'temporary' } }); fireEvent.click(screen.getByRole('button', { name: '撤销本地编辑' }));
  title.focus(); act(() => original.onLocate!(p, 'tracks[0].clips[0]'));
  expect((title as HTMLInputElement).value).toBe(initial); expect(document.activeElement).toBe(title); expect(client.timelineSave).not.toHaveBeenCalled();
});
it('does not locate a forged version, mismatched source or import-only preview', async () => {
  const { p } = await mounted(), original = captured.props!; const title = screen.getByLabelText('名称'); title.focus();
  act(() => { original.onLocate!({ ...p, timeline_snapshot: { ...p.timeline_snapshot, version: 999 } }, 'tracks[0].clips[0]');
    original.onLocate!({ ...p, direction: 'IMPORT' }, 'tracks[0].clips[0]'); });
  expect(document.activeElement).toBe(title);
});

it('blocks retained location while the original explicit attachment is pending', async () => {
  const { p, client } = await mounted(); let reject!: (reason: Error) => void;
  client.timelineTransferAttachment.mockReturnValue(new Promise((_resolve, no) => { reject = no; }));
  act(() => { captured.props!.controller.setAcknowledged(true); captured.props!.controller.setConfirmed(true); });
  const original = captured.props!, title = screen.getByLabelText('名称'); title.focus(); let work!: Promise<void>;
  act(() => { work = original.controller.attachmentTransfer(); original.onLocate!(p, 'tracks[0].clips[0]'); });
  expect(document.activeElement).toBe(title); expect(captured.props!.controller.pending).toBe('ATTACHMENT');
  expect(captured.props!.controller.isCurrentPreview(p)).toBe(false);
  await act(async () => { reject(new Error('Synthetic attachment unavailable')); await work; });
  expect(client.timelineTransferAttachment).toHaveBeenCalledOnce(); expect(client.timelineSave).not.toHaveBeenCalled();
});
it('keeps the original UNKNOWN import request and blocks locators and repeat import', async () => {
  const { p, client } = await mounted(); const old = captured.props!, imported = { ...p, direction: 'IMPORT' as const, format: 'SRT' as const, output_bytes: null, output_sha256: null };
  client.timelineTransferPreview.mockResolvedValue(imported); client.timelineTransferImport.mockRejectedValue(new Error('Synthetic lost reply'));
  act(() => captured.props!.controller.change({ direction: 'IMPORT', format: 'SRT', content: '1\n00:00:00,000 --> 00:00:00,500\n字幕' }));
  await act(async () => captured.props!.controller.previewTransfer());
  act(() => { captured.props!.controller.setAcknowledged(true); captured.props!.controller.setConfirmed(true); });
  await act(async () => captured.props!.controller.importTransfer());
  const unknown = captured.props!.controller.unknown; expect(unknown?.requestId).toBeTruthy();
  expect(captured.props!.controller.isCurrentPreview(imported)).toBe(false);
  const recovery = screen.getByRole('button', { name: '读取本次请求的原时间线回执' }); recovery.focus();
  act(() => old.onLocate!(p, 'tracks[0].clips[0]')); expect(document.activeElement).toBe(recovery);
  await act(async () => captured.props!.controller.importTransfer());
  expect(client.timelineTransferImport).toHaveBeenCalledOnce(); expect(captured.props!.controller.unknown?.requestId).toBe(unknown?.requestId);
  expect(client.timelineSave).not.toHaveBeenCalled();
});
