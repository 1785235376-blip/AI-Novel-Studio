import { useEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import type { StudioTimeline } from '../creative/studioTimelineTypes';
import type { NleEditRequest } from './timelineOpsTypes';
import { clipColorOperation } from './timelineClipColor';

/** Staged Inspector inputs. Only Apply/Remove emits an existing owner operation. */
export function ClipColorPanel(props: { timeline: StudioTimeline; selectedClipIds: string[]; editable: boolean; onEdit: (command: NleEditRequest) => void }) {
  const track = props.timeline.tracks.find(row => row.clips.some(clip => clip.id === props.selectedClipIds[0]));
  const clip = track?.clips.find(row => row.id === props.selectedClipIds[0]);
  const color = clip?.color_adjustment;
  const [brightness, setBrightness] = useState(String(color?.brightness ?? 0));
  const [contrast, setContrast] = useState(String(color?.contrast ?? 1));
  const [saturation, setSaturation] = useState(String(color?.saturation ?? 1));
  const [notice, setNotice] = useState('');
  const alive = useRef(true), consumed = useRef(false), latest = useRef(props); latest.current = props;
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const allowed = props.editable && props.selectedClipIds.length === 1 && props.timeline.schema_version === 2 && track?.kind === 'VIDEO' && !track.locked;
  const author = (work: () => void) => { consumed.current = false; setNotice(''); work(); };
  const apply = (remove: boolean) => {
    if (!alive.current || consumed.current || latest.current !== props || !allowed) return;
    try {
      const number = (value: string) => value.trim() ? Number(value) : Number.NaN;
      const operation = clipColorOperation(props.timeline, props.selectedClipIds, remove ? null : {
        brightness: number(brightness), contrast: number(contrast), saturation: number(saturation) });
      consumed.current = true;
      props.onEdit({ kind: 'clip.update', payload: operation });
      setNotice('已生成基础调色指令；应用结果见时间线提示，仍需明确保存与生成预览。');
    } catch (reason) { setNotice(reason instanceof Error ? reason.message : '基础调色参数无效。'); }
  };
  return <section aria-label="基础片段调色">
    <h4>基础片段调色</h4>
    <p>亮度 −1 至 1（默认 0），对比度 0 至 2、饱和度 0 至 3（默认 1）。仅作用于当前单个画面片段；不修改原素材。</p>
    <fieldset disabled={!allowed}><legend>待应用的画面参数</legend>
      <div className="nle-clip__form">
        <label>调色亮度<input aria-label="调色亮度" type="number" min={-1} max={1} step={0.01} value={brightness} onChange={event => author(() => setBrightness(event.currentTarget.value))} /></label>
        <label>调色对比度<input aria-label="调色对比度" type="number" min={0} max={2} step={0.01} value={contrast} onChange={event => author(() => setContrast(event.currentTarget.value))} /></label>
        <label>调色饱和度<input aria-label="调色饱和度" type="number" min={0} max={3} step={0.01} value={saturation} onChange={event => author(() => setSaturation(event.currentTarget.value))} /></label>
      </div>
      <Button onClick={() => apply(false)}>将基础调色应用到草稿</Button>
      <Button disabled={!color} onClick={() => apply(true)}>移除片段调色</Button>
    </fieldset>
    {!allowed && <p>需要扩展版本 2、可编辑且未锁定的视频轨道，并且只选择一个画面片段。</p>}
    <p>应用后可撤销；保存后再明确生成预览。未应用的输入不随草稿保存。高级调色、LUT 与自定义滤镜不支持。</p>
    {notice && <StatusMessage>{notice}</StatusMessage>}
  </section>;
}
