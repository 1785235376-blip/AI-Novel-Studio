import { useState } from 'react';
import { Badge, Button, EmptyState, StatusMessage } from '../ui/primitives';
import { captionCommand, safeTimeline, subtitleTrackModel } from './timelineOps';
import type { NleEditRequest } from './timelineOpsTypes';
import './timelineWorkspace.css';

const numeric = (value: string): number => value.trim() === '' ? Number.NaN : Number(value);
const READY_LABEL = { true: '就绪', false: '不可用' } as const;

/**
 * 字幕轨面板：定位、编辑、导入导出就绪度逐项说明。
 * 原字幕服务没有转录或时间轴推断，所以转录永远不可用；没有转录模型时手动字幕仍然可用。
 */
export type SubtitleTrackPanelProps = {
  timeline: unknown;
  subtitles?: unknown;
  editable: boolean;
  onEdit: (command: NleEditRequest) => void;
};

export function SubtitleTrackPanel(props: SubtitleTrackPanelProps) {
  const [text, setText] = useState(''), [start, setStart] = useState(''), [end, setEnd] = useState('');
  const [refusal, setRefusal] = useState<{ code: string; message: string } | null>(null);
  const [accepted, setAccepted] = useState<string>('');
  const parsed = safeTimeline(props.timeline);
  if (!parsed.ok) {
    return <section className="nle-subtitles" aria-label="字幕轨"><StatusMessage tone="error">{parsed.message}</StatusMessage>
      <EmptyState title="字幕轨不可用" detail="需要一份通过原时间线契约校验的时间线。" /></section>;
  }
  const timeline = parsed.timeline;
  const offered = props.subtitles && typeof props.subtitles === 'object' && !Array.isArray(props.subtitles)
    ? props.subtitles as Record<string, unknown> : {};
  const model = subtitleTrackModel(timeline.captions, {
    durationMs: timeline.duration_ms,
    importContent: offered.importContent, importFormat: offered.importFormat, exportFormat: offered.exportFormat,
  });
  const emit = (kind: string, context: Record<string, unknown>, note: string) => {
    const plan = captionCommand(kind, context);
    if (!plan.ok) { setRefusal({ code: plan.code, message: plan.message }); setAccepted(''); return; }
    setRefusal(null); setAccepted(`${note}（${plan.op}）`);
    props.onEdit({ kind: plan.op, payload: plan.payload });
  };
  const add = () => emit('caption-insert', { timeline,
    caption: { start_ms: numeric(start), end_ms: numeric(end), text } }, '已生成添加字幕指令');
  return <section className="nle-subtitles" aria-label="字幕轨" data-cue-count={model.cueCount} data-characters={model.characters}>
    <h3>字幕轨（作者输入的纯文字）</h3>
    <dl className="nle-subtitles__readiness">
      <div data-ready={model.locateReady}><dt>定位</dt><dd>{READY_LABEL[`${model.locateReady}` as 'true' | 'false']} · {model.cueCount} 条 / 最多 {model.limits.captions} 条</dd></div>
      <div data-ready={model.editReady}><dt>编辑</dt><dd>{READY_LABEL[`${model.editReady}` as 'true' | 'false']} · 总文字 {model.characters} / {model.limits.captionCharacters}</dd></div>
      <div data-ready={model.importReady}><dt>导入</dt><dd>{model.importMessage}</dd></div>
      <div data-ready={model.exportReady}><dt>导出</dt><dd>{model.exportMessage}</dd></div>
      <div data-ready={model.transcriptionAvailable}><dt>转录</dt><dd>{model.transcriptionMessage}</dd></div>
      <div data-ready={model.manualAvailable}><dt>手动字幕</dt><dd>{model.manualAvailable ? '可用：原编辑服务的纯文字字幕不依赖任何模型。' : '已达字幕条数或字数上限，请先拆分时间线。'}</dd></div>
    </dl>
    {model.transcriptionCode && <p className="nle-subtitles__code" data-transcription-code={model.transcriptionCode}>转录状态码 {model.transcriptionCode}</p>}
    <ul className="nle-subtitles__cues">
      {model.cues.map(cue => <li key={cue.index} data-index={cue.index} data-ready={cue.editReady}>
        <header><Badge tone={cue.editReady ? 'neutral' : 'warning'}>字幕 {cue.index + 1}</Badge>
          <span>{cue.startMs} — {cue.endMs} 毫秒 · {cue.lines} 行 · {cue.characters} 字</span></header>
        <p>{cue.text || '（空）'}</p>
        {cue.problems.length > 0 && <StatusMessage tone="warning">{cue.problems.join(' ')}</StatusMessage>}
        <Button variant="danger" disabled={!props.editable}
          onClick={() => emit('caption-remove', { timeline, index: cue.index }, `已生成移除字幕 ${cue.index + 1} 指令`)}>移除此字幕</Button>
      </li>)}
    </ul>
    {!model.cues.length && <EmptyState title="尚无字幕" detail="字幕是作者输入的纯文字，不代表任何模型转录结果。" />}
    <fieldset className="nle-subtitles__add" disabled={!props.editable}>
      <legend>添加手动字幕</legend>
      <label>开始（毫秒）<input type="number" step={1} value={start} aria-label="新字幕开始（毫秒）" onChange={event => setStart(event.currentTarget.value)} /></label>
      <label>结束（毫秒）<input type="number" step={1} value={end} aria-label="新字幕结束（毫秒）" onChange={event => setEnd(event.currentTarget.value)} /></label>
      <label>文字<textarea value={text} maxLength={1000} aria-label="新字幕文字" onChange={event => setText(event.currentTarget.value)} /></label>
      <Button disabled={!props.editable} onClick={add}>添加手动字幕</Button>
      <p className="nle-subtitles__note">每条一至八行纯文字；不接受空行、样式标记、控制字符或文件路径。原服务会重新校验每条字幕。</p>
    </fieldset>
    {refusal && <div data-refusal-code={refusal.code}><StatusMessage tone="error">已拒绝（{refusal.code}）：{refusal.message} 没有向原服务发送任何指令。</StatusMessage></div>}
    {accepted && <StatusMessage tone="success">{accepted}</StatusMessage>}
  </section>;
}
