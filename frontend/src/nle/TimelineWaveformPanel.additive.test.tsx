// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { TimelineWaveformPanel } from './TimelineWaveformPanel';
import { waveformDto } from '../creative/studioTimelineWaveform.testFixtures';
import type { TimelineWaveform } from '../creative/studioTimelineWaveformTypes';
afterEach(cleanup);
const props = () => ({ available: true, canRequest: true, pending: false, error: '', unavailable: '', onRequest: vi.fn() });
describe('bounded network-free waveform presentation', () => {
  it('requires explicit action and labels source-only truthfully', () => {
    const input = props(), view = render(<TimelineWaveformPanel {...input} />); expect(input.onRequest).not.toHaveBeenCalled();
    expect(screen.queryByRole('img')).toBeNull(); fireEvent.click(screen.getByRole('button', { name: '读取所选源波形' })); expect(input.onRequest).toHaveBeenCalledTimes(1);
    view.rerender(<TimelineWaveformPanel {...input} preview={waveformDto()} />);
    expect(input.onRequest).toHaveBeenCalledTimes(1); expect(screen.getByText(/未应用静音、片段\/轨道音量或淡入淡出/)).toBeTruthy();
    const svg = screen.getByRole('img', { name: '已测量的所选片段源采样包络' });
    const bars = svg.querySelectorAll('rect'); expect(bars).toHaveLength(507);
    expect(bars[0].getAttribute('data-start-frame')).toBe('45'); expect(bars[bars.length - 1].getAttribute('data-end-frame')).toBe('44100');
    for (const rect of bars) for (const name of ['x', 'y', 'width', 'height']) expect(Number.isFinite(Number(rect.getAttribute(name)))).toBe(true);
    expect(Number(bars[0].getAttribute('x'))).toBeGreaterThan(0);
  });
  it('draws no fabricated waveform for unsupported or over-budget sources', () => {
    const input = props(); render(<TimelineWaveformPanel {...input} error="素材超过源波形预览上限" />);
    expect(screen.queryByRole('img')).toBeNull(); expect(screen.getByText('素材超过源波形预览上限')).toBeTruthy();
  });
  it.each([
    { peaks: Array(513).fill(0) }, { peaks: [] }, { peaks: [Infinity] }, { sample_rate: 0 }, { samples_per_bucket: 0 },
    { start_frame: -1 }, { end_frame: NaN }, { clip: null }, { duration_seconds: null },
  ])('rejects malformed presentation without slicing, drawing, or throwing %j', change => {
    render(<TimelineWaveformPanel {...props()} preview={{ ...waveformDto(), ...change } as unknown as TimelineWaveform} />);
    expect(screen.queryByRole('img')).toBeNull(); expect(screen.getByText('源波形数据无效，未绘制。')).toBeTruthy();
  });
  it('disables the button during explicit reads and on unavailable selection', () => {
    const input = props(), view = render(<TimelineWaveformPanel {...input} canRequest={false} pending />);
    fireEvent.click(screen.getByRole('button', { name: '读取所选源波形' })); expect(input.onRequest).not.toHaveBeenCalled();
    view.rerender(<TimelineWaveformPanel {...input} canRequest={false} unavailable="请选择一个已保存的音频片段。" />);
    expect(screen.getByText('请选择一个已保存的音频片段。')).toBeTruthy();
  });
  it('clips the final sample cell at fractional trim end without changing source peak data', () => {
    const dto = waveformDto(); dto.clip.out_ms = 4; dto.end_frame = 177; dto.samples_per_bucket = 1; dto.peaks = Array(132).fill(0.5);
    render(<TimelineWaveformPanel {...props()} preview={dto} />); const bars = screen.getByRole('img').querySelectorAll('rect');
    const last = bars[bars.length - 1]; expect(Number(last.getAttribute('x')) + Number(last.getAttribute('width'))).toBeCloseTo(512, 10);
    expect(last.getAttribute('data-end-frame')).toBe('177'); expect(dto.peaks).toHaveLength(132);
  });
});
