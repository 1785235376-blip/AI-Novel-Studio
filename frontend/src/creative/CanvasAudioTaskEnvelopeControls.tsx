import { useLayoutEffect, useRef } from 'react';
import { StatusMessage } from '../ui/primitives';

type EnvelopeKey = 'gain_db' | 'fade_in_ms' | 'fade_out_ms';
type Props = {
  values: Record<EnvelopeKey, string>;
  disabled: boolean;
  isCurrent: () => boolean;
  onChange: (key: EnvelopeKey, value: string) => void;
};
const fields: { key: EnvelopeKey; label: string; minimum: number; maximum: number; step: number | 'any' }[] = [
  { key: 'gain_db', label: '本任务增益（-60–12 dB，可选）', minimum: -60, maximum: 12, step: 'any' },
  { key: 'fade_in_ms', label: '本任务淡入时长（毫秒，可选）', minimum: 0, maximum: 120000, step: 1 },
  { key: 'fade_out_ms', label: '本任务淡出时长（毫秒，可选）', minimum: 0, maximum: 120000, step: 1 },
];

/** Controlled fields over the original task draft; no transport, persistence or dispatch. */
export function CanvasAudioTaskEnvelopeControls({ values, disabled, isCurrent, onChange }: Props) {
  const current = useRef<object>(), lease = {};
  useLayoutEffect(() => {
    current.current = lease;
    return () => { if (current.current === lease) current.current = undefined; };
  });
  return <fieldset disabled={disabled}>
    <legend>本任务音频增益与淡入淡出</legend>
    <p>仅修改本任务，来源音频保持原样。先应用增益，再在线性幅度上淡入淡出，最后按原流程输出 48 kHz、双声道 PCM16 WAV。淡入与淡出时长之和不能超过裁剪片段时长。</p>
    {fields.map(field => <label key={field.key}>{field.label}<input type="number" min={field.minimum}
      max={field.maximum} step={field.step} disabled={disabled} value={values[field.key]}
      placeholder="留空保持原请求" onChange={event => {
        if (current.current !== lease || disabled || !isCurrent()) return;
        current.current = undefined;
        onChange(field.key, event.target.value);
      }} /></label>)}
    <StatusMessage>留空表示省略该参数，明确填写 0 会保留在请求中。费用未估算，不能按 0 费用理解。预览、入队、执行、审核和回流仍须分别明确确认。</StatusMessage>
  </fieldset>;
}
