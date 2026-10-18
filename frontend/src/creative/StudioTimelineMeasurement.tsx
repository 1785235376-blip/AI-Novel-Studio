import { Badge } from '../ui/primitives';
import type { TimelineMediaMeasurement } from './studioProductionClient';

/** Display only measured receipt fields, never substitute planned recipe values. */
export function StudioTimelineMeasurement({ measurement }: { measurement: TimelineMediaMeasurement | null | undefined }) {
  if (!measurement || !Object.keys(measurement).length) return <p>尚未读取到原生输出测量，执行配方不代表已生成的媒体。</p>;
  return <section aria-label="时间线实际输出测量"><h4>实际输出测量</h4>
    {measurement.profile_validation === 'NATIVE_FFPROBE_EXACT' && <Badge>原服务 ffprobe 测量回执</Badge>}
    <dl>
      {measurement.duration_ms !== undefined && <><dt>媒体时长</dt><dd>{measurement.duration_ms} 毫秒</dd></>}
      {measurement.byte_count !== undefined && <><dt>实际大小</dt><dd>{measurement.byte_count} 字节</dd></>}
      {measurement.width !== undefined && measurement.height !== undefined && <><dt>实际画面</dt><dd>{measurement.width} × {measurement.height}{measurement.fps !== undefined && <> · {measurement.fps} fps</>}</dd></>}
      {(measurement.video_codec || measurement.audio_codec || measurement.container) && <><dt>实际编码与容器</dt><dd>{measurement.export_profile?.preset !== 'AUDIO_WAV_PCM16' && <>{measurement.video_codec ?? '视频编码未提供'} / </>}{measurement.audio_codec ?? '音频编码未提供'} · {measurement.container ?? '容器未提供'}</dd></>}
      {(measurement.sample_rate !== undefined || measurement.channels !== undefined) && <><dt>实际声音</dt><dd>{measurement.sample_rate !== undefined ? `${measurement.sample_rate} Hz` : '采样率未提供'} · {measurement.channels !== undefined ? `${measurement.channels} 声道` : '声道未提供'}</dd></>}
      {measurement.sample_count !== undefined && <><dt>实际采样</dt><dd>{measurement.sample_count} 帧 · {measurement.bits_per_sample} bit</dd></>}
      {measurement.export_profile && <><dt>服务核对的导出配置</dt><dd>{measurement.export_profile.preset}</dd></>}
    </dl><p>这些数据来自刚读取的原任务回执。候选仍须读取实际字节、核对摘要并人工审核；本机及完整流程验收状态保持原门禁。</p>
  </section>;
}
