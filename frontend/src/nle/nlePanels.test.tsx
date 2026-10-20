// @vitest-environment jsdom
/**
 * UX-06 面板契约测试：
 *  - 标尺与轨道头只渲染给定事实；
 *  - 不受支持的编辑被拒绝并给出原因，绝不静默改成别的动作（不调用 onEdit）；
 *  - 预览永远不会被写成最终成片；
 *  - 上限提示在触界之前出现；
 *  - 任何面板都不发网络请求、不创建定时器。
 */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { checkedTimeline } from '../creative/studioTimelineTypes';
import type { StudioTimeline } from '../creative/studioTimelineTypes';
import { ClipInspectorPanel } from './ClipInspectorPanel';
import { ExportDeliveryPanel } from './ExportDeliveryPanel';
import { SubtitleTrackPanel } from './SubtitleTrackPanel';
import { TimelineRulerPanel } from './TimelineRulerPanel';
import { TimelineWorkspacePanel } from './TimelineWorkspacePanel';
import { TrackHeaderPanel } from './TrackHeaderPanel';
import { rulerTicks, timebaseOf } from './timelineOps';
import { NLE_CODES } from './timelineOpsTypes';

const DIGEST = 'b'.repeat(64);
const videoSource = { id: 'asset-video', kind: 'ASSET', asset_kind: 'video', version: 1, digest: DIGEST };
const audioSource = { id: 'asset-audio', kind: 'ASSET', asset_kind: 'audio', version: 2, digest: DIGEST };
const imageSource = { id: 'asset-image', kind: 'ASSET', asset_kind: 'image', version: 1, digest: DIGEST };

function videoClip(id: string, start: number, inMs: number, outMs: number) {
  return { id, source_snapshot: videoSource, start_ms: start, in_ms: inMs, out_ms: outMs,
    x: 0, y: 0, width: 1280, height: 720, speed_num: 1, speed_den: 1, opacity: 1, muted: false,
    gain_db: 0, fade_in_ms: 0, fade_out_ms: 0, include_audio: false };
}
function imageClip(id: string, start: number, outMs: number) {
  return { id, source_snapshot: imageSource, start_ms: start, in_ms: 0, out_ms: outMs,
    x: 0, y: 0, width: 1280, height: 720, speed_num: 1, speed_den: 1, opacity: 1, muted: false,
    gain_db: 0, fade_in_ms: 0, fade_out_ms: 0, include_audio: false };
}
function fixture(): StudioTimeline {
  return checkedTimeline({
    schema_version: 2, duration_ms: 10_000, width: 1280, height: 720, fps: 25,
    tracks: [
      { id: 'video-1', kind: 'VIDEO', order: 0, role: 'PRIMARY', muted: false, gain_db: 0,
        clips: [videoClip('clip-a', 0, 0, 4000), videoClip('clip-b', 4000, 0, 3000)] },
      { id: 'audio-1', kind: 'AUDIO', order: 1, role: 'DIALOGUE', muted: true, gain_db: -6,
        clips: [{ id: 'clip-c', source_snapshot: audioSource, start_ms: 0, in_ms: 0, out_ms: 5000,
          speed_num: 1, speed_den: 1, muted: false, gain_db: 0, fade_in_ms: 0, fade_out_ms: 0 }] },
      { id: 'video-2', kind: 'VIDEO', order: 2, role: 'OVERLAY', muted: false, gain_db: 0,
        clips: [imageClip('clip-d', 5000, 2000)] },
    ],
    captions: [{ start_ms: 0, end_ms: 1000, text: '第一句' }],
  });
}

const TIMELINE = fixture();
const TIMEBASE = timebaseOf(TIMELINE);
const previewReceipt = (preset: string) => ({
  contract: 'studio-timeline-export-preview/1', export_profile: { preset }, preview_digest: 'c'.repeat(64),
  limits: { max_output_bytes: 25 * 1024 * 1024, render_timeout_seconds: 120 },
  model_called: false, automatic_replay: false, product_acceptance: 'LOCAL_REQUIRED',
});

afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('标尺与轨道头只渲染给定事实', () => {
  it('刻度与视窗端点完全等于 rulerTicks 的结果，且不超过 owner 的总长', () => {
    const view = { startMs: 0, scale: 0.5 };
    const { container } = render(<TimelineRulerPanel timebase={TIMEBASE} view={view} playheadMs={1234}
      marks={{ inMs: 1000, outMs: 8000 }} editable onPlayhead={() => {}} onView={() => {}} />);
    const expected = rulerTicks(view, TIMEBASE, 960);
    const ruler = container.querySelector('.nle-ruler');
    expect(ruler?.getAttribute('data-duration-ms')).toBe('10000');
    expect(ruler?.getAttribute('data-fps')).toBe('25');
    expect(ruler?.getAttribute('data-window-start')).toBe(String(expected.range.startMs));
    expect(ruler?.getAttribute('data-window-end')).toBe(String(expected.range.endMs));
    const rendered = [...container.querySelectorAll('.nle-ruler__ticks > li')].map(node => Number(node.getAttribute('data-ms')));
    expect(rendered).toEqual(expected.ticks.map(tick => tick.ms));
    expect(rendered.every(ms => ms <= TIMEBASE.durationMs)).toBe(true);
    expect(container.querySelector('[data-major="true"]')).not.toBeNull();
    expect(screen.getByText(/入点 1000 毫秒/)).toBeTruthy();
    expect(screen.getByText(/出点 8000 毫秒/)).toBeTruthy();
  });

  it('非法视窗或时间基数只给出拒绝说明，不画任何刻度', () => {
    const { container, rerender } = render(<TimelineRulerPanel timebase={{ durationMs: 0, fps: 25 }}
      view={{ startMs: 0, scale: 1 }} playheadMs={0} marks={{ inMs: null, outMs: null }} editable
      onPlayhead={() => {}} onView={() => {}} />);
    expect(container.querySelector('.nle-ruler__ticks')).toBeNull();
    rerender(<TimelineRulerPanel timebase={TIMEBASE} view={{ startMs: 0, scale: 99 }} playheadMs={0}
      marks={{ inMs: null, outMs: null }} editable onPlayhead={() => {}} onView={() => {}} />);
    expect(container.querySelector('.nle-ruler__ticks')).toBeNull();
    expect(screen.getByRole('alert').textContent).toContain('视窗');
  });

  it('轨道头只显示已保存的锁、静音与增益', () => {
    const { container } = render(<TrackHeaderPanel timeline={TIMELINE} selectedClipIds={['clip-a']} editable
      onSelectClips={() => {}} />);
    const rows = [...container.querySelectorAll('.nle-track')].map(node => ({
      id: node.getAttribute('data-track-id'), locked: node.getAttribute('data-locked'),
      muted: node.getAttribute('data-muted'), gain: node.getAttribute('data-gain-db'),
    }));
    expect(rows).toEqual([
      { id: 'video-1', locked: 'false', muted: 'false', gain: '0' },
      { id: 'audio-1', locked: 'false', muted: 'true', gain: '-6' },
      { id: 'video-2', locked: 'false', muted: 'false', gain: '0' },
    ]);
    expect(container.querySelector('.nle-tracks')?.getAttribute('data-track-count')).toBe('3');
    expect(container.querySelector('[data-track-id="video-1"]')?.textContent).toContain('固定 0 dB');
    expect(container.querySelector('[data-track-id="audio-1"]')?.textContent).toContain('-6 dB');
    expect(container.querySelector('[data-track-id="audio-1"]')?.textContent).not.toContain('固定');
    expect(screen.getByRole('button', { name: 'clip-a' }).getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByRole('button', { name: 'clip-b' }).getAttribute('aria-pressed')).toBe('false');
  });

  it('非法时间线只给出原契约的中文说明', () => {
    render(<TrackHeaderPanel timeline={{ timeline: 'nonsense' }} selectedClipIds={[]} editable onSelectClips={() => {}} />);
    expect(screen.getByText(/时间线字段不符合原渲染接口/)).toBeTruthy();
    expect(screen.getByText('轨道头不可用')).toBeTruthy();
  });
});

describe('不受支持的编辑被拒绝而不是静默替换', () => {
  it('调色请求被拒绝、给出原因，且不调用 onEdit', () => {
    const onEdit = vi.fn();
    render(<ClipInspectorPanel timeline={TIMELINE} selectedClipIds={['clip-a']} playheadMs={2000}
      marks={{ inMs: null, outMs: null }} editable newId={() => 'clip-new'} onEdit={onEdit} />);
    fireEvent.change(screen.getByLabelText('请求的动作'), { target: { value: 'grade' } });
    fireEvent.click(screen.getByRole('button', { name: '生成编辑指令' }));
    expect(onEdit).not.toHaveBeenCalled();
    const refusal = document.querySelector('[data-refusal-code]');
    expect(refusal?.getAttribute('data-refusal-code')).toBe(NLE_CODES.editKindUnsupported);
    expect(refusal?.textContent).toContain('调色');
    expect(refusal?.textContent).toContain('没有向原服务发送任何指令');
  });

  it('对静态画面的滑移被拒绝并给出原因，且不调用 onEdit', () => {
    const onEdit = vi.fn();
    render(<ClipInspectorPanel timeline={TIMELINE} selectedClipIds={['clip-d']} playheadMs={0}
      marks={{ inMs: null, outMs: null }} editable newId={() => 'clip-new'} onEdit={onEdit} />);
    fireEvent.change(screen.getByLabelText('请求的动作'), { target: { value: 'slip' } });
    fireEvent.change(screen.getByLabelText('滑移增量（毫秒）'), { target: { value: '200' } });
    fireEvent.click(screen.getByRole('button', { name: '生成编辑指令' }));
    expect(onEdit).not.toHaveBeenCalled();
    expect(document.querySelector('[data-refusal-code]')?.getAttribute('data-refusal-code')).toBe(NLE_CODES.editStillSlipInvalid);
  });

  it('受支持的动作只发出原 owner 的操作描述符', () => {
    const onEdit = vi.fn();
    render(<ClipInspectorPanel timeline={TIMELINE} selectedClipIds={['clip-a']} playheadMs={2000}
      marks={{ inMs: null, outMs: null }} editable newId={() => 'clip-new'} onEdit={onEdit} />);
    fireEvent.click(screen.getByRole('button', { name: '以所选片段填入默认值' }));
    fireEvent.click(screen.getByRole('button', { name: '生成编辑指令' }));
    expect(onEdit).toHaveBeenCalledTimes(1);
    const command = onEdit.mock.calls[0][0] as { kind: string; payload: { op: string; clip_id: string; at_ms: number; new_clip_id: string } };
    expect(command.kind).toBe('clip.split');
    expect(command.payload).toEqual([{ op: 'clip.split', clip_id: 'clip-a', at_ms: 2000, new_clip_id: 'clip-new' }]);
    expect(screen.getByText(/已生成 1 项原 clip.split 指令/)).toBeTruthy();
  });

  it('未选择片段时不生成任何指令', () => {
    const onEdit = vi.fn();
    render(<ClipInspectorPanel timeline={TIMELINE} selectedClipIds={[]} playheadMs={0}
      marks={{ inMs: null, outMs: null }} editable newId={() => 'clip-new'} onEdit={onEdit} />);
    expect(screen.getByText('尚未选择片段')).toBeTruthy();
    expect(screen.queryByRole('button', { name: '生成编辑指令' })).toBeNull();
    expect(onEdit).not.toHaveBeenCalled();
  });
});

describe('字幕轨：没有转录模型时手动字幕仍可用', () => {
  it('转录不可用、手动字幕可用，空文字被拒绝且不调用 onEdit', () => {
    const onEdit = vi.fn();
    render(<SubtitleTrackPanel timeline={TIMELINE} editable onEdit={onEdit} />);
    expect(screen.getByText(/没有转录或时间轴推断/)).toBeTruthy();
    expect(screen.getByText(/手动字幕.*可用/)).toBeTruthy();
    expect(document.querySelector('[data-transcription-code]')?.getAttribute('data-transcription-code'))
      .toBe(NLE_CODES.subtitleNoTranscriptionOwner);
    fireEvent.change(screen.getByLabelText('新字幕开始（毫秒）'), { target: { value: '2000' } });
    fireEvent.change(screen.getByLabelText('新字幕结束（毫秒）'), { target: { value: '3000' } });
    fireEvent.click(screen.getByRole('button', { name: '添加手动字幕' }));
    expect(onEdit).not.toHaveBeenCalled();
    expect(document.querySelector('[data-refusal-code]')?.getAttribute('data-refusal-code')).toBe(NLE_CODES.captionShapeInvalid);
  });

  it('有效的手动字幕发出原 owner 的 caption.insert', () => {
    const onEdit = vi.fn();
    render(<SubtitleTrackPanel timeline={TIMELINE} editable onEdit={onEdit} />);
    fireEvent.change(screen.getByLabelText('新字幕开始（毫秒）'), { target: { value: '2000' } });
    fireEvent.change(screen.getByLabelText('新字幕结束（毫秒）'), { target: { value: '3000' } });
    fireEvent.change(screen.getByLabelText('新字幕文字'), { target: { value: '第二句' } });
    fireEvent.click(screen.getByRole('button', { name: '添加手动字幕' }));
    expect(onEdit).toHaveBeenCalledTimes(1);
    expect(onEdit.mock.calls[0][0]).toEqual({ kind: 'caption.insert', payload: { op: 'caption.insert', caption: { start_ms: 2000, end_ms: 3000, text: '第二句' } } });
  });

  it('移除字幕使用 caption.remove 并携带原序号', () => {
    const onEdit = vi.fn();
    render(<SubtitleTrackPanel timeline={TIMELINE} editable onEdit={onEdit} />);
    expect(document.querySelector('.nle-subtitles')?.getAttribute('data-cue-count')).toBe('1');
    fireEvent.click(screen.getByRole('button', { name: '移除此字幕' }));
    expect(onEdit.mock.calls[0][0]).toEqual({ kind: 'caption.remove', payload: { op: 'caption.remove', index: 0 } });
  });
});

describe('预览永远不会被写成最终成片', () => {
  it('审核预览预设只声明预览画质，交付画质保持缺省', () => {
    const { container } = render(<ExportDeliveryPanel exportReceipt={previewReceipt('REVIEW_MP4')} usage={{ tracks: 1, clips: 1, durationMs: 5000, captions: 0, captionCharacters: 0 }} />);
    const delivery = container.querySelector('.nle-delivery');
    expect(delivery?.getAttribute('data-stage')).toBe('PREVIEW_CHECKED');
    expect(delivery?.getAttribute('data-delivery-ready')).toBe('false');
    const preview = container.querySelector('[data-quality="PREVIEW"]');
    const final = container.querySelector('[data-quality="FINAL"]');
    expect(preview?.getAttribute('data-present')).toBe('true');
    expect(final?.getAttribute('data-present')).toBe('false');
    expect(preview?.textContent).toContain('审核预览画质');
    expect(final?.textContent).not.toContain('交付成片画质（mpeg4');
    expect(screen.getByText(/本界面不声明已交付/)).toBeTruthy();
    expect(screen.getByText(/审核 MP4 只是预览画质/)).toBeTruthy();
  });

  it('交付预设也仍需人工审核，结果不明时不声明成功', () => {
    const { container, rerender } = render(<ExportDeliveryPanel exportReceipt={previewReceipt('DELIVERY_H264_MP4')} />);
    expect(container.querySelector('[data-quality="FINAL"]')?.getAttribute('data-present')).toBe('true');
    expect(container.querySelector('[data-quality="PREVIEW"]')?.getAttribute('data-present')).toBe('false');
    expect(container.querySelector('.nle-delivery')?.getAttribute('data-delivery-ready')).toBe('false');
    rerender(<ExportDeliveryPanel exportReceipt={{ ...previewReceipt('DELIVERY_H264_MP4'), state: 'UNKNOWN', request_id: 'req-9' }} />);
    expect(container.querySelector('.nle-delivery')?.getAttribute('data-stage')).toBe('DISPATCHED_UNKNOWN');
    expect(screen.getByText(/结果不明/)).toBeTruthy();
    expect(screen.getByText('req-9')).toBeTruthy();
  });
});

describe('上限提示出现在触界之前', () => {
  it('接近上限时给出警告，且没有任何一行标记为已达上限', () => {
    const { container } = render(<ExportDeliveryPanel limits={null}
      usage={{ tracks: 7, clips: 28, durationMs: 590_000, captions: 480, captionCharacters: 31_000 }} />);
    const tracks = container.querySelector('[data-limit-key="tracks"]');
    expect(tracks?.getAttribute('data-near')).toBe('true');
    expect(tracks?.getAttribute('data-reached')).toBe('false');
    expect(container.querySelectorAll('[data-reached="true"]').length).toBe(0);
    expect(screen.getAllByText(/轨道总数已用 7 \/ 8 条/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/建议先拆分内容/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/不会提高任何上限/).length).toBeGreaterThan(0);
  });

  it('达到上限时如实说明，并且拒绝按更高的上限显示', () => {
    const { container } = render(<ExportDeliveryPanel limits={{ tracks: 99 }}
      usage={{ tracks: 8, clips: 30, durationMs: 600_000, captions: 500, captionCharacters: 32_000 }} />);
    expect(container.querySelector('[data-limit-key="tracks"]')?.getAttribute('data-reached')).toBe('true');
    expect(container.querySelector('[data-limit-key="tracks"]')?.textContent).toContain('8 条');
    expect(document.querySelector('[data-raise-refused="true"]')?.textContent).toContain('拒绝按其提高');
    expect(screen.getByText(/轨道总数已达上限/)).toBeTruthy();
  });
});

describe('工作区面板：冻结入口与零副作用', () => {
  beforeEach(() => { vi.stubGlobal('fetch', vi.fn()); });

  const mount = (overrides: Partial<Parameters<typeof TimelineWorkspacePanel>[0]> = {}) => render(
    <TimelineWorkspacePanel projectId="studio-project" identity="file:abc" timeline={TIMELINE}
      selectedClipIds={['clip-a']} playheadMs={2000} viewStartMs={0} viewScale={0.5} editable
      onSelectClips={() => {}} onPlayhead={() => {}} onView={() => {}} onEdit={() => {}}
      subtitles={{ exportFormat: 'SRT' }} limits={null} {...overrides} />);

  it('渲染所有子面板且不发起网络请求、不创建定时器', () => {
    vi.useFakeTimers();
    const { container, unmount } = mount();
    expect(screen.getByRole('region', { name: '多轨剪辑、预览与交付' })).toBeTruthy();
    expect(screen.getByRole('region', { name: '时间线标尺' })).toBeTruthy();
    expect(screen.getByRole('region', { name: '轨道头' })).toBeTruthy();
    expect(screen.getByRole('region', { name: '片段属性' })).toBeTruthy();
    expect(screen.getByRole('region', { name: '字幕轨' })).toBeTruthy();
    expect(screen.getByRole('region', { name: '交付' })).toBeTruthy();
    expect(container.querySelector('.nle-workspace__scope')?.getAttribute('data-editable')).toBe('true');
    expect(globalThis.fetch).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it('入出点只按给定事实计算，越界时明确拒绝', () => {
    mount({ playheadMs: 2000 });
    fireEvent.click(screen.getByRole('button', { name: '以播放头设入点' }));
    expect(screen.getAllByText(/入点 2000 毫秒/).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: '以播放头设出点' }));
    expect(screen.getByRole('alert').textContent).toContain('出点必须晚于入点');
    fireEvent.click(screen.getByRole('button', { name: '清除入出点' }));
    expect(screen.getAllByText(/入点 未设置/).length).toBeGreaterThan(0);
  });

  it('非法时间线只给出原契约说明，并提供重新核对入口', () => {
    const onUnavailable = vi.fn();
    render(<TimelineWorkspacePanel projectId="studio-project" identity="file:abc" timeline={{ broken: true }}
      selectedClipIds={[]} playheadMs={0} viewStartMs={0} viewScale={1} editable
      onSelectClips={() => {}} onPlayhead={() => {}} onView={() => {}} onEdit={() => {}} onUnavailable={onUnavailable} />);
    expect(screen.getByText('时间线入口不可用')).toBeTruthy();
    expect(document.querySelector('[data-refusal-code]')?.getAttribute('data-refusal-code')).toBe(NLE_CODES.timelineInvalid);
    expect(screen.queryByRole('region', { name: '轨道头' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '重新核对入口' }));
    expect(onUnavailable).toHaveBeenCalledTimes(1);
  });
});
