import { useLayoutEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { checkedTimelineCaptionStyle, type StudioTimelineCaptionStyle as CaptionStyle, type StudioTimelineDraft } from './studioTimelineTypes';

type Props = { draft: StudioTimelineDraft; scope: object; disabled: boolean; isCurrent: () => boolean;
  getRevision: () => string; onApply: (style: CaptionStyle | null) => boolean };
type Fields = { font_size: string; primary_color: string; alignment: string; outline_width: string };
const suggested: CaptionStyle = { font_size: 24, primary_color: '#FFFFFF', alignment: 'BOTTOM_CENTER', outline_width: 1 };
const fields = (style: CaptionStyle): Fields => ({ ...style, font_size: String(style.font_size), outline_width: String(style.outline_width) });

/** Staged presentation only. Applying enters the original editor's local history. */
export function StudioTimelineCaptionStyle(props: Props) {
  const [staged, setStaged] = useState<{ token: object; fields: Fields }>();
  const [error, setError] = useState<{ token: object; message: string }>();
  const live = useRef(props); live.current = props;
  const alive = useRef(true), edits = useRef(0);
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const revision = props.getRevision(), values = [props.draft, props.scope, props.disabled, revision];
  const owner = useRef({ values, token: {} });
  if (values.some((value, index) => value !== owner.current.values[index])) owner.current = { values, token: {} };
  const token = owner.current.token, edit = edits.current;
  const style = props.draft.timeline.caption_style;
  const form = staged?.token === token ? staged.fields : fields(style ?? suggested);
  const current = () => alive.current && !live.current.disabled && live.current.isCurrent()
    && owner.current.token === token && edits.current === edit && live.current.getRevision() === revision
    && live.current.draft.timeline.schema_version === 2;
  function stage(key: keyof Fields, value: string) {
    if (!current()) return;
    edits.current++; setError(undefined); setStaged({ token, fields: { ...form, [key]: value } });
  }
  function apply(reset: boolean) {
    if (!current()) return;
    try {
      const next = reset ? null : checkedTimelineCaptionStyle({ ...form,
        font_size: form.font_size === '' ? Number.NaN : Number(form.font_size),
        outline_width: form.outline_width === '' ? Number.NaN : Number(form.outline_width) });
      edits.current++;
      setError(undefined);
      if (!live.current.onApply(next)) setError({ token, message: '字幕样式未改变，或当前编辑状态不允许应用。' });
    } catch (reason) {
      setError({ token, message: reason instanceof Error ? reason.message : '字幕样式无效。' });
    }
  }
  if (props.draft.timeline.schema_version === 3) return null;
  if (props.draft.timeline.schema_version !== 2) return <p>全局字幕样式需要先明确采用扩展编辑版本 2。</p>;
  return <fieldset disabled={props.disabled}><legend>全局字幕样式</legend>
    <p>字号使用 libass 参考单位，不是输出画面的像素值。使用现有固定字体回退；样式对所有字幕生效。</p>
    <p>{style ? '当前草稿已设置全局字幕样式。' : '尚未设置全局样式；以下为建议值，应用前不会写入草稿。'}</p>
    <label>字幕字号（libass 参考单位）<input type="number" min={8} max={72} step={1} value={form.font_size} onChange={event => stage('font_size', event.currentTarget.value)} /></label>
    <label>字幕颜色（#RRGGBB）<input maxLength={7} value={form.primary_color} onChange={event => stage('primary_color', event.currentTarget.value)} /></label>
    <label>字幕位置<select value={form.alignment} onChange={event => stage('alignment', event.currentTarget.value)}>
      <option value="TOP_CENTER">顶部居中</option><option value="BOTTOM_CENTER">底部居中</option>
    </select></label>
    <label>字幕描边宽度<input type="number" min={0} max={4} step={1} value={form.outline_width} onChange={event => stage('outline_width', event.currentTarget.value)} /></label>
    <Button onClick={() => apply(false)}>将字幕样式应用到本地草稿</Button>
    <Button disabled={!style} onClick={() => apply(true)}>移除全局字幕样式</Button>
    <p>应用或移除后可撤销；明确保存时间线后才会写入服务端。移除样式恢复原渲染器的字幕外观。</p>
    {error?.token === token && <StatusMessage tone="warning">{error.message}</StatusMessage>}
  </fieldset>;
}
