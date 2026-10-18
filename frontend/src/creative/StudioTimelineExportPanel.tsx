import { Button, StatusMessage } from '../ui/primitives';
import { AUDIO_TIMELINE_MAX_WAV_DURATION_MS, checkedTimelineExportProfile, timelineExportPresets, type TimelineExportPreset } from './studioTimelineExportTypes';
import type { StudioTimelineEditorController } from './useStudioTimelineEditor';

const names: Record<TimelineExportPreset, string> = { AUDIO_WAV_PCM16: '音频 WAV（PCM16 / 48 kHz / 立体声）', REVIEW_MP4: '审核 MP4（原渲染配置）', DELIVERY_H264_MP4: '交付 MP4（H.264 / AAC）', DELIVERY_VP9_WEBM: '交付 WebM（VP9 / Opus）' };
const number = (value: string) => value === '' ? Number.NaN : Number(value);
const display = (value: number | undefined) => value !== undefined && Number.isFinite(value) ? value : '';

/** A replaceable view; request reservations and all consent live in the controller. */
export function StudioTimelineExportPanel({ controller: c }: { controller: StudioTimelineEditorController }) {
  if (!c.base) return null;
  const profile = c.exportProfile, preview = c.exportPreview;
  const locked = !c.canEdit || c.inputDirty || !c.sourcesCurrent || c.attempt?.state === 'UNKNOWN' || !c.exportAvailable;
  return <section aria-label="时间线交付导出"><h3>交付导出</h3>
    <p>先读取导出方案，核对保存版本、素材与编码参数，再明确发送一次本地渲染。方案预览不排队、不产生媒体；实际导出候选仍通过原制作任务预览、摘要核对与人工审核。</p>
    {!c.exportAvailable && <StatusMessage tone="warning">当前客户端未提供完整导出入口，请继续使用原渲染任务。</StatusMessage>}
    <fieldset disabled={locked}><legend>导出配置</legend>
      <label>格式<select value={profile.preset} onChange={event => c.changeExportProfile(checkedTimelineExportProfile({ preset: event.currentTarget.value }))}>
        {timelineExportPresets.filter(preset => (preset === 'AUDIO_WAV_PCM16') === (c.base!.timeline.schema_version === 3)).map(preset => <option key={preset} value={preset}>{names[preset]}</option>)}
      </select></label>
      {profile.preset !== 'REVIEW_MP4' && profile.preset !== 'AUDIO_WAV_PCM16' && <>
        <label>视频码率（kbps）<input type="number" min={100} max={20000} step={1} value={display(profile.video_bitrate_kbps)} onChange={event => c.changeExportProfile({ ...profile, video_bitrate_kbps: number(event.currentTarget.value) })} /></label>
        <label>音频码率（kbps）<input type="number" min={32} max={320} step={1} value={display(profile.audio_bitrate_kbps)} onChange={event => c.changeExportProfile({ ...profile, audio_bitrate_kbps: number(event.currentTarget.value) })} /></label>
        <label>CRF<input type="number" min={0} max={profile.preset === 'DELIVERY_VP9_WEBM' ? 63 : 51} step={1} value={display(profile.crf)} onChange={event => c.changeExportProfile({ ...profile, crf: number(event.currentTarget.value) })} /></label>
        <p>画面尺寸、帧率与时长使用已保存时间线；编码能力和输出大小由原渲染服务核对，不自动换格式或降低参数。</p>
      </>}
      {profile.preset === 'AUDIO_WAV_PCM16' && <p>固定 PCM16、48 kHz、双声道 WAV。原 25 MiB 上限可容纳最多 {AUDIO_TIMELINE_MAX_WAV_DURATION_MS} 毫秒（136.533 秒）；更长时间线请缩短或分段。草稿仍保留十分钟编辑上限。</p>}
    </fieldset>
    {c.base.timeline.schema_version === 3 && c.base.timeline.duration_ms > AUDIO_TIMELINE_MAX_WAV_DURATION_MS && <StatusMessage tone="warning">当前时长超出固定 WAV 输出大小上限。请缩短并保存后再试听或导出。</StatusMessage>}
    <Button loading={c.pending === 'EXPORT_PREVIEW'} disabled={!c.canPreviewExport} onClick={() => void c.previewExport()}>核对导出方案（不执行）</Button>
    {preview && <section aria-label="已核对导出方案"><h4>{names[preview.export_profile.preset]} · 时间线 v{preview.timeline_snapshot.version}</h4>
      <p>最多输出 {preview.limits.max_output_bytes} 字节 · 渲染期限 {preview.limits.render_timeout_seconds} 秒。模型调用：无。尚未生成媒体。</p>
      <details><summary>导出绑定与来源摘要</summary>
        <p>时间线 <code>{preview.timeline_snapshot.id}</code> · v{preview.timeline_snapshot.version} · <code>{preview.timeline_snapshot.digest}</code></p>
        <p>方案摘要 <code>{preview.preview_digest}</code> · 渲染配方 <code>{preview.execution_recipe.recipe_digest}</code></p>
        <ul>{preview.sources.map(source => <li key={source.id}>{source.asset_kind} · <code>{source.id}</code> · v{source.version} · <code>{source.digest}</code></li>)}</ul>
      </details>
      <label><input type="checkbox" checked={c.exportConfirmed} disabled={!c.canPreviewExport} onChange={event => c.setExportConfirmed(event.currentTarget.checked)} />已核对本次导出方案、版本、摘要和资源限制，确认生成私有候选</label>
      <Button variant="primary" loading={c.pending === 'EXPORT'} disabled={!c.canExport} onClick={() => void c.exportTimeline()}>明确执行此方案并生成导出候选</Button>
    </section>}
  </section>;
}
