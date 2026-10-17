import { Button, StatusMessage } from '../ui/primitives';
import { waveformTimelineCoordinate, type TimelineWaveform } from '../creative/studioTimelineWaveformTypes';

export type TimelineWaveformPanelProps = { available: boolean; canRequest: boolean; pending: boolean; preview?: TimelineWaveform;
  error: string; unavailable: string; onRequest: () => void };
/** Presentation only: measured source peaks, no network, decoding, playback or editing. */
export function TimelineWaveformPanel(props: TimelineWaveformPanelProps) {
  // A bounded view even when embedded callers bypass the original controller.
  let candidate = props.preview;
  if (candidate) {
    const ints = [candidate.frame_count, candidate.sample_rate, candidate.channels, candidate.start_frame, candidate.end_frame, candidate.samples_per_bucket,
      candidate.clip?.in_ms, candidate.clip?.out_ms, candidate.clip?.start_ms, candidate.clip?.speed_num, candidate.clip?.speed_den];
    if (ints.some(number => !Number.isSafeInteger(number)) || candidate.frame_count < 1 || candidate.frame_count > 4194304
      || candidate.frame_count > candidate.sample_rate * 600 || candidate.sample_rate < 1 || candidate.sample_rate > 192000 || ![1, 2].includes(candidate.channels)
      || candidate.start_frame < 0 || candidate.end_frame > candidate.frame_count || candidate.end_frame <= candidate.start_frame
      || candidate.samples_per_bucket !== Math.ceil((candidate.end_frame - candidate.start_frame) / 512)
      || candidate.clip.in_ms < 0 || candidate.clip.out_ms > 600000 || candidate.clip.out_ms <= candidate.clip.in_ms
      || candidate.clip.start_ms < 0 || candidate.clip.start_ms > 600000 || candidate.clip.speed_num < 1 || candidate.clip.speed_num > 4
      || candidate.clip.speed_den < 1 || candidate.clip.speed_den > 4
      || candidate.start_frame !== Math.ceil(candidate.clip.in_ms * candidate.sample_rate / 1000)
      || candidate.end_frame !== Math.ceil(candidate.clip.out_ms * candidate.sample_rate / 1000)
      || candidate.duration_seconds?.num !== candidate.frame_count || candidate.duration_seconds?.den !== candidate.sample_rate
      || !Array.isArray(candidate.peaks) || candidate.peaks.length < 1 || candidate.peaks.length > 512
      || candidate.peaks.length !== Math.ceil((candidate.end_frame - candidate.start_frame) / candidate.samples_per_bucket)
      || Array.from(candidate.peaks).some(peak => typeof peak !== 'number' || !Number.isFinite(peak) || peak < 0 || peak > 1 || !Number.isInteger(peak * 32768))) candidate = undefined;
  }
  const value = candidate;
  const width = 512, height = 96;
  const duration = value ? (value.clip.out_ms - value.clip.in_ms) * value.clip.speed_den / value.clip.speed_num : 0;
  const x = (frame: number) => {
    const time = waveformTimelineCoordinate(value!, frame);
    return Math.max(0, Math.min(width, (time.num - value!.clip.start_ms * time.den) * width / (time.den * duration)));
  };
  return <section className="nle-clip" aria-label="所选音频源波形">
    <h3>所选音频源波形</h3>
    <p className="nle-workspace__note">仅按需读取已保存片段的 PCM16 WAV 源采样包络（单声道或双声道，最多 8 MiB、十分钟）。不是混音、增益或淡入淡出后的声音，也不表示语音对齐；不会播放或保存。</p>
    <div className="nle-clip__actions"><Button disabled={!props.canRequest} loading={props.pending} onClick={props.onRequest}>读取所选源波形</Button></div>
    {props.unavailable && <p className="nle-workspace__note">{props.unavailable}</p>}
    {props.pending && <StatusMessage>正在读取所选源采样包络…</StatusMessage>}
    {props.error && <StatusMessage tone="warning">{props.error}</StatusMessage>}
    {props.preview && !value && <StatusMessage tone="warning">源波形数据无效，未绘制。</StatusMessage>}
    {value && <>
      <svg role="img" aria-label="已测量的所选片段源采样包络" viewBox={`0 0 ${width} ${height}`} width="100%" height={height} preserveAspectRatio="none">
        <title>所选片段源采样包络；最多 512 个峰值，非渲染后音频</title>
        {value.peaks.map((peak, index) => {
          const start = value.start_frame + index * value.samples_per_bucket;
          const end = Math.min(value.end_frame, start + value.samples_per_bucket);
          return <rect key={start} x={x(start)} y={height / 2 - peak * height / 2} width={Math.max(0, x(end) - x(start))}
            height={peak * height} fill="currentColor" data-start-frame={start} data-end-frame={end} />;
        })}
      </svg>
      <p className="nle-workspace__note">{value.peaks.length} 个源峰值 · {value.channels} 声道 · {value.sample_rate} Hz · 源总长 {value.duration_seconds.num}/{value.duration_seconds.den} 秒</p>
      <p className="nle-workspace__note">源采样范围 [{value.start_frame}, {value.end_frame}) · 裁剪 [{value.clip.in_ms}, {value.clip.out_ms}) 毫秒 · 时间线起点 {value.clip.start_ms} 毫秒 · 速度 {value.clip.speed_num}/{value.clip.speed_den}</p>
      <p className="nle-workspace__note">未应用静音、片段/轨道音量或淡入淡出。多声道取绝对峰值，不代表实际混音响度；Windows 原生验证仍待执行。</p>
    </>}
  </section>;
}
