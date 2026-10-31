import { useId, useLayoutEffect, useRef, useState } from 'react';
import { clipBoundaryNavigation } from './clipBoundaryNavigation';
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
  /** Only view context; isCurrent reuses the original owner's revision/readiness fence. */
  navigation?: { timeline: unknown; contextKey: string; isCurrent?: () => boolean };
  onPlayhead: (ms: number) => void;
  onView: (next: { startMs: number; scale: number }) => void;
};

export function TimelineRulerPanel(props: TimelineRulerPanelProps) {
  const [draft, setDraft] = useState(() => String(Math.max(0, Math.round(props.playheadMs))));
  const hintId = useId(), composing = useRef<HTMLElement | null>(null), alive = useRef(true);
  const navigation = props.navigation ? clipBoundaryNavigation(props.navigation.timeline, props.playheadMs) : undefined;
  const key = JSON.stringify([props.navigation?.contextKey, navigation?.ok ? navigation.timelineKey : null,
    props.playheadMs, props.editable, props.timebase]);
  const context = useRef({ key, isCurrent: props.navigation?.isCurrent, generation: 0 });
  if (context.current.key !== key || context.current.isCurrent !== props.navigation?.isCurrent) {
    context.current = { key, isCurrent: props.navigation?.isCurrent, generation: context.current.generation + 1 };
  }
  const generation = context.current.generation;
  const latest = useRef(props); latest.current = props;
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; composing.current = null; }; }, []);
  // A new revision retires callbacks, while an active DOM composition survives ordinary rerenders.
  useLayoutEffect(() => { if (composing.current && !composing.current.isConnected) composing.current = null; });
  useLayoutEffect(() => { setDraft(String(props.playheadMs)); }, [props.playheadMs, props.navigation?.contextKey]);
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
  const navigationValid = navigation?.ok && navigation.durationMs === timebase.value.durationMs;
  const previousMs = navigationValid ? navigation.previousMs : null, nextMs = navigationValid ? navigation.nextMs : null;
  const navigate = (direction: 'PREVIOUS' | 'NEXT'): boolean => {
    if (!alive.current || !latest.current.editable || context.current.generation !== generation || composing.current
      || latest.current.navigation?.isCurrent?.() === false) return false;
    const ms = direction === 'PREVIOUS' ? previousMs : nextMs;
    if (ms === null) return false;
    latest.current.onPlayhead(ms); return true;
  };
  return <section key={props.navigation?.contextKey} className="nle-ruler" aria-label="时间线标尺"
    data-duration-ms={timebase.value.durationMs} data-window-start={ruler.range.startMs}
    data-window-end={ruler.range.endMs} data-step-ms={ruler.stepMs} data-fps={timebase.value.fps} data-playhead-ms={props.playheadMs}
    tabIndex={props.navigation ? 0 : undefined} aria-describedby={props.navigation ? hintId : undefined}
    aria-keyshortcuts={props.navigation ? 'ArrowUp ArrowDown' : undefined}
    onCompositionStartCapture={event => {
      if (event.target instanceof HTMLElement && event.target.isConnected) composing.current = event.target;
    }}
    onCompositionEndCapture={event => { if (event.target === composing.current) composing.current = null; }}
    onBlurCapture={event => { if (event.target === composing.current) composing.current = null; }}
    onKeyDown={event => {
      if (!props.navigation || event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey
        || event.repeat || event.nativeEvent.isComposing || event.keyCode === 229 || composing.current) return;
      if (event.target instanceof Element && event.target.closest('input, textarea, select, [contenteditable]:not([contenteditable="false"]), [role="textbox"], [role="spinbutton"], [role="combobox"]')) return;
      if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return;
      if (navigate(event.key === 'ArrowUp' ? 'PREVIOUS' : 'NEXT')) { event.preventDefault(); event.stopPropagation(); }
    }}>
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
    {props.navigation && <>
      <div className="nle-ruler__bar" role="group" aria-label="剪切点导航">
        <Button disabled={!props.editable || previousMs === null} onClick={() => navigate('PREVIOUS')}>上一个剪切点</Button>
        <Button disabled={!props.editable || nextMs === null} onClick={() => navigate('NEXT')}>下一个剪切点</Button>
      </div>
      <p id={hintId} className="nle-ruler__note">标尺内按 ↑ / ↓ 跳到上一个 / 下一个剪切点。仅使用全部轨道片段的真实起止点，相同时间合并，首末不循环；输入文字或使用输入法时不触发。</p>
      {navigation && !navigation.ok && <StatusMessage tone="error">{navigation.message}</StatusMessage>}
      {navigation?.ok && !navigationValid && <StatusMessage tone="error">剪切点与当前时间线总长不一致，请重新核对。</StatusMessage>}
    </>}
    <label className="nle-ruler__jump">播放头（毫秒）
      <input type="number" min={0} max={timebase.value.durationMs} step={1} value={draft}
        disabled={!props.editable} aria-label="播放头（毫秒）"
        onChange={event => setDraft(event.currentTarget.value)} />
    </label>
    <Button disabled={!props.editable || !validJump} onClick={() => props.onPlayhead(jump)}>跳转到播放头</Button>
    <p className="nle-ruler__note">入点 {marks.marks.inMs === null ? '未设置' : `${marks.marks.inMs} 毫秒`} · 出点 {marks.marks.outMs === null ? '未设置' : `${marks.marks.outMs} 毫秒`} · 播放头 {props.playheadMs} 毫秒。刻度与吸附都使用整数毫秒，不做浮点累加。</p>
  </section>;
}
