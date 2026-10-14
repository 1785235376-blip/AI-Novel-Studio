import { useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { NLE_DEFAULT_VIEW_WIDTH_PX, rulerTicks, validateMarks, validateTimebase, validateWindow } from './timelineOps';
import type { NleMarks, NleTimebase, NleViewWindow } from './timelineOpsTypes';
import './timelineWorkspace.css';

/**
 * 标尺面板：只按给定事实绘制刻度、视窗与播放头。
 * 刻度位置来自 `rulerTicks`（`序号 × 步长`，无浮点累加），从不超出 owner 的总长。
 */
export type TimelineRulerPanelProps = {
  timebase: NleTimebase;
  view: NleViewWindow;
  playheadMs: number;
  marks: NleMarks;
  editable: boolean;
  widthPx?: number;
  onPlayhead: (ms: number) => void;
  onView: (next: { startMs: number; scale: number }) => void;
};

export function TimelineRulerPanel(props: TimelineRulerPanelProps) {
  const [draft, setDraft] = useState(() => String(Math.max(0, Math.round(props.playheadMs))));
  const timebase = validateTimebase(props.timebase);
  if (!timebase.ok) return <StatusMessage tone="error">{timebase.message}</StatusMessage>;
  const view = validateWindow(props.view, timebase.value);
  if (!view.ok) return <StatusMessage tone="error">{view.message}</StatusMessage>;
  const marks = validateMarks(props.marks, timebase.value);
  if (!marks.ok) return <StatusMessage tone="error">{marks.message}</StatusMessage>;
  const width = props.widthPx ?? NLE_DEFAULT_VIEW_WIDTH_PX;
  const ruler = rulerTicks(view.window, timebase.value, width);
  const parse = (value: string): number => value.trim() === '' ? Number.NaN : Number(value);
  const jump = parse(draft);
  const validJump = Number.isSafeInteger(jump) && jump >= 0 && jump <= timebase.value.durationMs;
  const move = (deltaMs: number) => props.onView({ startMs: view.window.startMs + deltaMs, scale: view.window.scale });
  const zoom = (factor: number) => props.onView({ startMs: view.window.startMs, scale: view.window.scale * factor });
  const fitted = width / timebase.value.durationMs;
  return <section className="nle-ruler" aria-label="时间线标尺"
    data-duration-ms={timebase.value.durationMs} data-window-start={ruler.range.startMs}
    data-window-end={ruler.range.endMs} data-step-ms={ruler.stepMs} data-fps={timebase.value.fps}>
    <header className="nle-ruler__bar">
      <Button disabled={!props.editable} onClick={() => zoom(0.5)}>缩小</Button>
      <Button disabled={!props.editable} onClick={() => zoom(2)}>放大</Button>
      <Button disabled={!props.editable} onClick={() => move(-ruler.range.windowMs)}>左移一屏</Button>
      <Button disabled={!props.editable} onClick={() => move(ruler.range.windowMs)}>右移一屏</Button>
      <Button disabled={!props.editable} onClick={() => props.onView({ startMs: 0, scale: fitted })}>显示全部</Button>
      <span className="nle-ruler__metre">
        {ruler.range.startMs} — {ruler.range.endMs} 毫秒 · 每毫秒 {view.window.scale} 像素 · {ruler.ticks.length} 个刻度
        {ruler.truncated ? '（已截断）' : ''}
      </span>
    </header>
    <ol className="nle-ruler__ticks" aria-label="标尺刻度">
      {ruler.ticks.map(tick => <li key={tick.ms} data-ms={tick.ms} data-major={tick.major}
        aria-hidden={tick.major ? undefined : true}>
        {tick.major ? <span className="nle-ruler__label">{tick.label}</span> : null}
      </li>)}
    </ol>
    <label className="nle-ruler__jump">播放头（毫秒）
      <input type="number" min={0} max={timebase.value.durationMs} step={1} value={draft}
        disabled={!props.editable} aria-label="播放头（毫秒）"
        onChange={event => setDraft(event.currentTarget.value)} />
    </label>
    <Button disabled={!props.editable || !validJump} onClick={() => props.onPlayhead(jump)}>跳转到播放头</Button>
    <p className="nle-ruler__note">入点 {marks.marks.inMs === null ? '未设置' : `${marks.marks.inMs} 毫秒`} · 出点 {marks.marks.outMs === null ? '未设置' : `${marks.marks.outMs} 毫秒`} · 播放头 {props.playheadMs} 毫秒。刻度与吸附都使用整数毫秒，不做浮点累加。</p>
  </section>;
}
