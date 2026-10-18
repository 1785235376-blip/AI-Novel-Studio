import { useState } from 'react';
import { Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import { ClipInspectorPanel } from './ClipInspectorPanel';
import { ExportDeliveryPanel } from './ExportDeliveryPanel';
import { SubtitleTrackPanel } from './SubtitleTrackPanel';
import { TimelineRulerPanel } from './TimelineRulerPanel';
import { TrackHeaderPanel } from './TrackHeaderPanel';
import { TimelineWaveformPanel, type TimelineWaveformPanelProps } from './TimelineWaveformPanel';
import { safeTimeline, setInOut, timebaseOf, timelineUsage, validateWindow } from './timelineOps';
import type { NleMarks } from './timelineOpsTypes';
import './timelineWorkspace.css';

/**
 * 冻结挂载形状：主代理把真实控制器值传进来；本面板把每个入参都当不可信数据处理。
 * 面板不发网络请求、不建定时器、不持有第二个编辑器引擎；它只生成原编辑服务的操作描述符。
 */
export type TimelineWorkspacePanelProps = { projectId: string; identity: string; timeline: unknown; selectedClipIds: string[]; playheadMs: number; viewStartMs: number; viewScale: number; editable: boolean; onSelectClips: (ids: string[]) => void; onPlayhead: (ms: number) => void; onView: (next: { startMs: number; scale: number }) => void; onEdit: (command: { kind: string; payload: unknown }) => void; subtitles?: unknown; exportReceipt?: unknown; limits?: unknown; waveform?: TimelineWaveformPanelProps; onUnavailable?: () => void };

const bounded = (value: unknown, max: number): string => {
  const text = typeof value === 'string' ? value : '';
  return text.length > max ? `${text.slice(0, max)}…` : text;
};

export function TimelineWorkspacePanel(props: TimelineWorkspacePanelProps) {
  const [marks, setMarks] = useState<NleMarks>({ inMs: null, outMs: null });
  const [markError, setMarkError] = useState('');
  const parsed = safeTimeline(props.timeline);
  if (!parsed.ok) {
    return <Panel title="多轨剪辑与交付" aria-label="多轨剪辑、预览与交付">
      <div data-refusal-code={parsed.code}><StatusMessage tone="error">{parsed.message}</StatusMessage></div>
      <EmptyState title="时间线入口不可用" detail="请重新核对项目、身份与原可信会话；这里不会凭空显示任何片段、字幕或导出事实。" />
      {props.onUnavailable && <Button onClick={props.onUnavailable}>重新核对入口</Button>}
    </Panel>;
  }
  const timeline = parsed.timeline;
  const timebase = timebaseOf(timeline);
  const view = validateWindow({ startMs: props.viewStartMs, scale: props.viewScale }, timebase);
  const usage = timelineUsage(timeline);
  const mark = (point: 'IN' | 'OUT') => {
    const next = setInOut(marks, point, props.playheadMs, timebase);
    if (!next.ok) { setMarkError(next.message); return; }
    setMarkError(''); setMarks(next.marks);
  };
  return <Panel title="多轨剪辑与交付" aria-label="多轨剪辑、预览与交付">
    <p className="nle-workspace__scope" data-editable={props.editable}>
      项目 {bounded(props.projectId, 240)} · 身份 {bounded(props.identity, 240)} · 总长 {timebase.durationMs} 毫秒{timebase.mediaKind === 'AUDIO' ? ' · 纯音频' : ` · ${timebase.fps} fps`} · {timeline.tracks.length} 条轨道 · {usage.clips} 个片段{timeline.schema_version !== 3 && <> · 字幕 {usage.captions} 条</>}
    </p>
    <p className="nle-workspace__note">{timeline.schema_version === 3 ? '音频时间基使用整数毫秒与整数比速度；试听与正式交付分开确认。波形按需读取，不在每次拖动时解码素材。' : '时间基仍是原 owner 的整数毫秒与整数比速度；预览画质与交付画质分开陈述；缩略图与波形按需读取，不在每次拖动时解码素材。'}</p>
    <div className="nle-workspace__marks">
      <Button disabled={!props.editable} onClick={() => mark('IN')}>以播放头设入点</Button>
      <Button disabled={!props.editable} onClick={() => mark('OUT')}>以播放头设出点</Button>
      <Button disabled={!props.editable} onClick={() => { setMarks({ inMs: null, outMs: null }); setMarkError(''); }}>清除入出点</Button>
      <span>入点 {marks.inMs === null ? '未设置' : `${marks.inMs} 毫秒`} · 出点 {marks.outMs === null ? '未设置' : `${marks.outMs} 毫秒`}</span>
    </div>
    {markError && <StatusMessage tone="error">{markError}</StatusMessage>}
    {!view.ok
      ? <StatusMessage tone="error">{view.message}</StatusMessage>
      : <TimelineRulerPanel timebase={timebase} view={view.window} playheadMs={props.playheadMs} marks={marks}
        editable={props.editable} onPlayhead={props.onPlayhead} onView={props.onView} />}
    <TrackHeaderPanel timeline={timeline} selectedClipIds={props.selectedClipIds} editable={props.editable}
      onSelectClips={props.onSelectClips} />
    <ClipInspectorPanel timeline={timeline} selectedClipIds={props.selectedClipIds} playheadMs={props.playheadMs}
      marks={marks} editable={props.editable} onEdit={props.onEdit} />
    {props.waveform && <TimelineWaveformPanel {...props.waveform} />}
    {timeline.schema_version !== 3 && <SubtitleTrackPanel timeline={timeline} subtitles={props.subtitles} editable={props.editable} onEdit={props.onEdit} />}
    <ExportDeliveryPanel mediaKind={timeline.schema_version === 3 ? 'AUDIO' : 'VIDEO'} exportReceipt={props.exportReceipt} limits={props.limits} usage={usage} />
    <p className="nle-workspace__foot">本批次不改变已保存的时间线契约、不提高任何上限、不做调色与合成；本地 Windows、真实媒体与重型渲染验收仍待执行。</p>
  </Panel>;
}
