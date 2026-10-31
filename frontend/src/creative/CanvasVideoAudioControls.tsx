import {useId} from 'react';
import {StatusMessage} from '../ui/primitives';

export type CanvasVideoAudioControlsProps = {
  value: boolean;
  disabled: boolean;
  isCurrent: () => boolean;
  onChange: (next: boolean) => void;
};

export function CanvasVideoAudioControls({value, disabled, isCurrent, onChange}: CanvasVideoAudioControlsProps) {
  const descriptionId = useId();
  return <fieldset disabled={disabled || !isCurrent()}>
    <legend>源音轨</legend>
    <label><input type="checkbox" checked={value} aria-describedby={descriptionId}
      onChange={event => {
        if (disabled || !isCurrent()) return;
        onChange(event.target.checked);
      }}/><span>保留源音轨</span></label>
    <p id={descriptionId}>开启后保留所选源视频在截取范围内的第一音轨，并重新编码为 AAC；不是无损复制。关闭后输出静音。</p>
    <StatusMessage>源音轨是否存在及执行能力仍须由原 Timeline 流程核对。此选项不代表验证通过或执行许可。</StatusMessage>
  </fieldset>;
}
