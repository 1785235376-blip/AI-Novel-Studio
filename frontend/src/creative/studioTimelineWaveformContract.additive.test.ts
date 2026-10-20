import { afterEach, describe, expect, it, vi } from 'vitest';
import { useLocalHostSession } from '../localHostSession';
import { studioProductionClient } from './studioProductionClient';
import { checkedTimelineWaveform, timelineWaveformRequest, waveformTimelineCoordinate } from './studioTimelineWaveformTypes';
import { waveformDto, waveformRow } from './studioTimelineWaveform.testFixtures';

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });
const checked = (value: unknown) => checkedTimelineWaveform(value, waveformRow(), 'audio-clip', { novelId: 'project-waveform', branchId: null });
describe('closed selected PCM16 source waveform contract', () => {
  it('binds exact original timeline/source/clip and leaves the source unchanged', () => {
    const source = waveformRow(), before = JSON.stringify(source); expect(checked(waveformDto())).toEqual(waveformDto());
    expect(timelineWaveformRequest(source, 'audio-clip')).toEqual({ expected_version: 1, reviewed_timeline_digest: 'b'.repeat(64),
      clip_id: 'audio-clip', source_snapshot: waveformDto().source_snapshot }); expect(JSON.stringify(source)).toBe(before);
  });
  it.each(['novel_id', 'branch_id', 'timeline_id', 'timeline_version', 'timeline_digest', 'clip_id', 'contract', 'status', 'scope'])('rejects changed %s', key => {
    expect(() => checked({ ...waveformDto(), [key]: 'wrong' })).toThrow();
  });
  it.each(['frame_count', 'sample_rate', 'channels', 'byte_count', 'start_frame', 'end_frame', 'samples_per_bucket'])('rejects numeric coercion/nonfinite %s', key => {
    for (const value of [true, '1', NaN, Infinity, -1, 0.5]) expect(() => checked({ ...waveformDto(), [key]: value })).toThrow();
  });
  it('rejects unknown/missing fields at every nested boundary', () => {
    for (const key of Object.keys(waveformDto())) { const value = { ...waveformDto() } as Record<string, unknown>; delete value[key]; expect(() => checked(value)).toThrow(); }
    expect(() => checked({ ...waveformDto(), native_url: 'ignored' })).toThrow();
    for (const key of ['source_snapshot', 'clip', 'duration_seconds'] as const) {
      expect(() => checked({ ...waveformDto(), [key]: { ...waveformDto()[key], surprise: 1 } })).toThrow();
      expect(() => checked({ ...waveformDto(), [key]: {} })).toThrow();
    }
  });
  it('refuses changed source pins, clip trim/speed and rounded duration', () => {
    expect(() => checked({ ...waveformDto(), source_snapshot: { ...waveformDto().source_snapshot, version: 3 } })).toThrow();
    for (const key of ['in_ms', 'out_ms', 'start_ms', 'speed_num', 'speed_den'] as const) expect(() => checked({ ...waveformDto(), clip: { ...waveformDto().clip, [key]: waveformDto().clip[key] + 1 } })).toThrow();
    expect(() => checked({ ...waveformDto(), duration_seconds: { num: 1, den: 1 } })).toThrow();
  });
  it('requires exact half-open ceil bounds and deterministic bounded peak layout', () => {
    for (const value of [{ start_frame: 44 }, { end_frame: 44099 }, { samples_per_bucket: 86 }, { peaks: [] }, { peaks: Array(513).fill(0) },
      { peaks: [0] }, { byte_count: 8388609 }, { byte_count: 88200 - 1 }, { sample_rate: 192001 }]) expect(() => checked({ ...waveformDto(), ...value })).toThrow();
    for (const peak of [NaN, Infinity, -0.1, 1.01, '0.5', true, 0.1]) { const dto = waveformDto(); dto.peaks[0] = peak as number; expect(() => checked(dto)).toThrow(); }
  });
  it('accepts silence and full-scale signed PCM magnitude without applying gain/mute/fades', () => {
    const dto = waveformDto(); dto.peaks.fill(0); expect(checked(dto).peaks.every(value => value === 0)).toBe(true);
    dto.peaks.fill(1); expect(checked(dto).peaks.every(value => value === 1)).toBe(true);
  });
  it('maps source frames with rational speed and does not round the noninteger source start', () => {
    const first = waveformTimelineCoordinate(waveformDto(), 45), last = waveformTimelineCoordinate(waveformDto(), 44100);
    expect(first).toEqual({ num: 132301800, den: 132300 }); expect(first.num / first.den).toBeCloseTo(1000 + (45 * 1000 / 44100 - 1) * 2 / 3, 10);
    expect(last.num / last.den).toBe(1666); expect(() => waveformTimelineCoordinate(waveformDto(), 44)).toThrow();
  });
  it('rejects nonaudio/missing selected clips before a transport request', async () => {
    const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher);
    const client = studioProductionClient('project-waveform', { sessionToken: '' });
    await expect(client.timelineWaveformPreview(waveformRow(), 'still')).rejects.toThrow();
    await expect(client.timelineWaveformPreview(waveformRow(), 'missing')).rejects.toThrow(); expect(fetcher).not.toHaveBeenCalled();
  });
  it('uses only the original scoped read route and forwards cancellation', async () => {
    useLocalHostSession.setState({ token: 'synthetic-waveform-unit', actorId: '' });
    const fetcher = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => waveformDto() }); vi.stubGlobal('fetch', fetcher);
    const client = studioProductionClient('project-waveform', { sessionToken: '' }), abort = new AbortController();
    expect(await client.timelineWaveformPreview(waveformRow(), 'audio-clip', abort.signal)).toEqual(waveformDto());
    expect(fetcher).toHaveBeenCalledTimes(1); expect(fetcher.mock.calls[0][0]).toBe('/api/projects/project-waveform/studio/production/timelines/timeline-waveform/waveform-preview');
    expect(fetcher.mock.calls[0][1].method).toBe('POST'); expect(fetcher.mock.calls[0][1].signal).toBe(abort.signal);
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual(timelineWaveformRequest(waveformRow(), 'audio-clip'));
  });
});
