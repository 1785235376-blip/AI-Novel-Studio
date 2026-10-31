import { useLayoutEffect, useRef, useState } from 'react';
import { Button } from '../ui/primitives';
import { formatAudioTrimTimecode, parseAudioTrimTimecode } from './studioAudioTrimTimecode';

export function StudioAudioTrimTimecodes({ start, end, disabled, onApply }: {
  start: string; end: string; disabled: boolean; onApply: (start: string, end: string) => void;
}) {
  const [from, setFrom] = useState(() => formatAudioTrimTimecode(start));
  const [to, setTo] = useState(() => formatAudioTrimTimecode(end));
  const inMs = parseAudioTrimTimecode(from), outMs = parseAudioTrimTimecode(to);
  const valid = inMs !== null && outMs !== null && outMs > inMs;
  const currentApply = useRef<object>(), lease = {};
  // A committed render owns its callback; input/owner changes and unmount retire it.
  useLayoutEffect(() => {
    currentApply.current = lease;
    return () => { if (currentApply.current === lease) currentApply.current = undefined; };
  });
  return <details>
    <summary>按时间码填写裁剪区间</summary>
    <p>输入 分:秒 或 时:分:秒，可带 1–3 位小数，例如 1:23.450。填入后仍可编辑毫秒；读取制作预览前会核对片段长度与来源。</p>
    <label>裁剪起点时间码<input type="text" maxLength={12} placeholder="0:00.000" disabled={disabled} value={from} onChange={event => setFrom(event.target.value)} /></label>
    <label>裁剪终点时间码<input type="text" maxLength={12} placeholder="0:10.000" disabled={disabled} value={to} onChange={event => setTo(event.target.value)} /></label>
    <p aria-live="polite">{valid ? `待填入：${inMs}–${outMs} 毫秒 · 片段 ${outMs - inMs} 毫秒` : '请填写 0:00 至 10:00 范围内的时间码，终点须晚于起点。'}</p>
    <Button disabled={disabled || !valid} onClick={() => {
      if (currentApply.current !== lease || disabled || !valid) return;
      currentApply.current = undefined;
      onApply(String(inMs), String(outMs));
    }}>填入起止毫秒</Button>
  </details>;
}
