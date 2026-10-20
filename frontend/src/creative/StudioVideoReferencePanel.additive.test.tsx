// @vitest-environment jsdom
import { webcrypto } from 'node:crypto';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { StudioVideoReferencePanel } from './StudioVideoReferencePanel';
import { videoReferencePreview, videoReferenceSource as source } from './studioVideoReference.testFixtures';
import type { StudioAsset } from './studioClient';
import type { VideoReferencePreview, VideoReferenceWindow } from './studioVideoReferenceContract';
const review = videoReferencePreview();
const deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(done => { resolve = done; }); return { promise, resolve }; };
function props() { return { scope: {}, assets: [source], blocked: false, canSave: true, isCurrent: () => true,
  onPreview: vi.fn(async (_asset: StudioAsset, _window: VideoReferenceWindow, _signal: AbortSignal) => structuredClone(review)),
  onSave: vi.fn(async (_asset: StudioAsset, _review: VideoReferencePreview, _index: number, _signal: AbortSignal) => {}) }; }
beforeEach(() => {
  vi.stubGlobal('crypto', webcrypto);
  vi.stubGlobal('URL', class extends URL { static createObjectURL = vi.fn(() => 'blob:video-frame'); static revokeObjectURL = vi.fn(); });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
async function previewFrames() {
  fireEvent.change(screen.getByLabelText('视频参考原素材'), { target: { value: source.id } });
  fireEvent.click(screen.getByRole('button', { name: '明确预览视频采样帧' }));
  return screen.findByRole('img', { name: '已校验采样帧 1' });
}
async function chooseReviewedFrame() {
  const image = await previewFrames(); fireEvent.load(image);
  fireEvent.click(screen.getByRole('button', { name: '选择第 1 帧' }));
  fireEvent.click(screen.getByLabelText('已查看所选采样帧，确认保存为派生图片素材'));
}
it('never previews automatically; requires displayed frame, explicit choice and checkbox before one save', async () => {
  const input = props(); render(<StudioVideoReferencePanel {...input} />);
  expect(input.onPreview).not.toHaveBeenCalled(); expect(input.onSave).not.toHaveBeenCalled();
  const image = await previewFrames(); expect(screen.getAllByRole('img')).toHaveLength(4);
  const save = screen.getByRole('button', { name: '保存所选参考帧到素材库' });
  fireEvent.click(screen.getByRole('button', { name: '选择第 1 帧' })); fireEvent.click(save); expect(input.onSave).not.toHaveBeenCalled();
  fireEvent.load(image); fireEvent.click(screen.getByRole('button', { name: '选择第 1 帧' })); fireEvent.click(save); expect(input.onSave).not.toHaveBeenCalled();
  fireEvent.click(screen.getByLabelText('已查看所选采样帧，确认保存为派生图片素材'));
  await act(async () => { fireEvent.click(save); fireEvent.click(save); });
  expect(input.onPreview).toHaveBeenCalledTimes(1); expect(input.onSave).toHaveBeenCalledTimes(1);
  expect(input.onSave.mock.calls[0]).toEqual([source, review, 0, expect.any(AbortSignal)]);
  expect(URL.revokeObjectURL).toHaveBeenCalledTimes(4);
});
it('allows readonly preview but never grants save when permission is absent', async () => {
  const input = props(); render(<StudioVideoReferencePanel {...input} canSave={false} />); await chooseReviewedFrame();
  fireEvent.click(screen.getByRole('button', { name: '保存所选参考帧到素材库' }));
  expect(input.onPreview).toHaveBeenCalledTimes(1); expect(input.onSave).not.toHaveBeenCalled();
  expect((screen.getByLabelText('已查看所选采样帧，确认保存为派生图片素材') as HTMLInputElement).disabled).toBe(true);
});
it.each(['window', 'source', 'scope', 'permission', 'blocked', 'read-revocation'])('retires review and URLs immediately on %s change', async kind => {
  const input = props(), view = render(<StudioVideoReferencePanel {...input} />); await chooseReviewedFrame();
  if (kind === 'window') fireEvent.change(screen.getByLabelText('采样终点（毫秒，不包含）'), { target: { value: '1250' } });
  if (kind === 'source') view.rerender(<StudioVideoReferencePanel {...input} assets={[{ ...source, version: 2 }]} />);
  if (kind === 'scope') view.rerender(<StudioVideoReferencePanel {...input} scope={{}} />);
  if (kind === 'permission') view.rerender(<StudioVideoReferencePanel {...input} canSave={false} />);
  if (kind === 'blocked') view.rerender(<StudioVideoReferencePanel {...input} blocked />);
  if (kind === 'read-revocation') view.rerender(<StudioVideoReferencePanel {...input} isCurrent={() => false} />);
  expect(screen.queryByRole('img')).toBeNull(); expect(input.onSave).not.toHaveBeenCalled(); expect(URL.revokeObjectURL).toHaveBeenCalledTimes(4);
});
it('ignores old preview after input A-B-A, aborts request and requires a new click', async () => {
  const input = props(), pending = deferred<VideoReferencePreview>(); input.onPreview.mockImplementation(() => pending.promise);
  render(<StudioVideoReferencePanel {...input} />);
  fireEvent.change(screen.getByLabelText('视频参考原素材'), { target: { value: source.id } });
  fireEvent.click(screen.getByRole('button', { name: '明确预览视频采样帧' }));
  const field = screen.getByLabelText('采样终点（毫秒，不包含）');
  act(() => { fireEvent.change(field, { target: { value: '1250' } }); fireEvent.change(field, { target: { value: '1000' } }); });
  await act(async () => pending.resolve(review));
  expect(screen.queryByRole('img')).toBeNull(); expect(input.onPreview).toHaveBeenCalledTimes(1);
  expect(input.onPreview.mock.calls[0][2]).toHaveProperty('aborted', true);
});
it('ignores late completion after Close or unmount', async () => {
  const input = props(), pending = deferred<VideoReferencePreview>(); input.onPreview.mockImplementation(() => pending.promise);
  const view = render(<StudioVideoReferencePanel {...input} />);
  fireEvent.change(screen.getByLabelText('视频参考原素材'), { target: { value: source.id } });
  fireEvent.click(screen.getByRole('button', { name: '明确预览视频采样帧' })); fireEvent.click(screen.getByRole('button', { name: '关闭采样预览' }));
  view.unmount(); await act(async () => pending.resolve(review)); expect(URL.createObjectURL).not.toHaveBeenCalled();
});
it('resets confirmation on frame selection, image error and unknown save result', async () => {
  const input = props(); input.onSave.mockRejectedValue(new Error('lost receipt')); render(<StudioVideoReferencePanel {...input} />); await chooseReviewedFrame();
  fireEvent.load(screen.getByRole('img', { name: '已校验采样帧 2' })); fireEvent.click(screen.getByRole('button', { name: '选择第 2 帧' }));
  const confirm = screen.getByLabelText('已查看所选采样帧，确认保存为派生图片素材') as HTMLInputElement;
  expect(confirm.checked).toBe(false); fireEvent.click(confirm); fireEvent.error(screen.getByRole('img', { name: '已校验采样帧 2' })); expect(confirm.checked).toBe(false);
  fireEvent.load(screen.getByRole('img', { name: '已校验采样帧 2' })); fireEvent.click(confirm);
  fireEvent.click(screen.getByRole('button', { name: '保存所选参考帧到素材库' })); await waitFor(() => expect(input.onSave).toHaveBeenCalledTimes(1));
  await screen.findByText(/保存结果未确认/); expect(confirm.checked).toBe(false);
});
it('rejects malformed preview without making object URLs or rendering images', async () => {
  const input = props(), invalid = structuredClone(review); invalid.preview_digest = '0'.repeat(64); input.onPreview.mockResolvedValue(invalid);
  render(<StudioVideoReferencePanel {...input} />);
  fireEvent.change(screen.getByLabelText('视频参考原素材'), { target: { value: source.id } }); fireEvent.click(screen.getByRole('button', { name: '明确预览视频采样帧' }));
  await screen.findByText(/来源、时间戳或图片校验未通过/); expect(URL.createObjectURL).not.toHaveBeenCalled();
});

it.each(['blocked', 'scope', 'permission'])('ignores late preview after %s A-B-A', async kind => {
  const input = props(), pending = deferred<VideoReferencePreview>(); input.onPreview.mockImplementation(() => pending.promise);
  const view = render(<StudioVideoReferencePanel {...input} />);
  fireEvent.change(screen.getByLabelText('视频参考原素材'), { target: { value: source.id } });
  fireEvent.click(screen.getByRole('button', { name: '明确预览视频采样帧' }));
  if (kind === 'blocked') view.rerender(<StudioVideoReferencePanel {...input} blocked />);
  if (kind === 'scope') view.rerender(<StudioVideoReferencePanel {...input} scope={{}} />);
  if (kind === 'permission') view.rerender(<StudioVideoReferencePanel {...input} canSave={false} />);
  view.rerender(<StudioVideoReferencePanel {...input} />);
  await act(async () => pending.resolve(review));
  expect(screen.queryByRole('img')).toBeNull(); expect(input.onPreview).toHaveBeenCalledTimes(1);
  expect(input.onPreview.mock.calls[0][2].aborted).toBe(true);
});
