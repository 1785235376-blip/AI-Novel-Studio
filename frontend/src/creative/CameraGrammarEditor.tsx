import { useId, type ReactNode } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { emptyCameraGrammar, validCameraGrammar, type CameraGrammar, type CameraPoint } from './cameraGrammar';

const Field = ({ label, children }: { label: string; children: ReactNode }) => <label className="creative-field"><span>{label}</span>{children}</label>;
function PointFields({ label, value, onChange }: { label: string; value: CameraPoint; onChange: (value: CameraPoint) => void }) {
  return <>{(['x', 'y'] as const).map(key => <Field key={key} label={`${label} ${key}`}><input type="number" step="any" min={-1_000_000} max={1_000_000}
    value={Number.isFinite(value[key]) ? value[key] : ''} onChange={event => onChange({ ...value, [key]: event.target.valueAsNumber })} /></Field>)}</>;
}

/** Only edits the original parent draft. Viewing never materializes geometry. */
export function CameraGrammarEditor({ value, onChange, label }: { value?: CameraGrammar | null; onChange: (value?: CameraGrammar) => void; label: string }) {
  const help = useId();
  const update = (patch: Partial<CameraGrammar>) => onChange({ ...value!, ...patch });
  const positions = Object.entries(value?.character_positions || {});
  return <details aria-label={`${label}手填机位几何`}><summary>手填机位与轴线（辅助证据）</summary>
    <p id={help}>模型语义建议与人工创作仍是主要决策依据。此处只记录你明确填写的平面坐标，供原轴线规则辅助复算；不从文本或画面推断位置，不调用模型。修改后使用原保存或审核按钮。</p>
    {!value ? <><p>信息不足：尚未填写机位几何。</p><Button onClick={() => onChange(emptyCameraGrammar())}>启用手填几何（坐标仍为空）</Button></> : <>
      <div className="creative-form-grid">
        <Field label="坐标系标识"><input maxLength={120} value={value.coordinate_system} aria-describedby={help} onChange={e => update({ coordinate_system: e.target.value })} /></Field>
        <Field label="场景目的"><textarea maxLength={2000} value={value.scene_purpose} onChange={e => update({ scene_purpose: e.target.value })} /></Field>
        <Field label="观察视点"><input maxLength={500} value={value.viewpoint} onChange={e => update({ viewpoint: e.target.value })} /></Field>
        <Field label="镜头功能"><select value={value.shot_function} onChange={e => update({ shot_function: e.target.value as CameraGrammar['shot_function'] })}>{['UNSPECIFIED', 'ESTABLISHING', 'OTS', 'POV', 'INSERT'].map(v => <option key={v}>{v}</option>)}</select></Field>
        <Field label="焦点意图"><select value={value.focus_intent} onChange={e => update({ focus_intent: e.target.value as CameraGrammar['focus_intent'] })}>{['UNSPECIFIED', 'HOLD', 'RACK_FOCUS'].map(v => <option key={v}>{v}</option>)}</select></Field>
        <Field label="声明屏幕方向"><select value={value.screen_direction} onChange={e => update({ screen_direction: e.target.value as CameraGrammar['screen_direction'] })}>{['UNKNOWN', 'LEFT_TO_RIGHT', 'RIGHT_TO_LEFT', 'STATIONARY'].map(v => <option key={v}>{v}</option>)}</select></Field>
      </div>
      <p>世界坐标 x 向右、y 向上。两镜头需使用相同坐标系、人物位置及有序轴线。位置标识是作者填写的标签，不是已验证的角色库绑定。机位位于轴线上或人物重合时仍为信息不足。</p>
      {positions.map(([id, point], index) => <fieldset key={index}><legend>人物位置 {index + 1}</legend><div className="creative-form-grid">
        <Field label={`位置 ${index + 1} 人物标识`}><input maxLength={240} value={id} onChange={e => {
          const next = e.target.value;
          if (next !== id && Object.hasOwn(value.character_positions, next)) return;
          update({ character_positions: Object.fromEntries(positions.map(([key, p]) => [key === id ? next : key, p])), axis: value.axis.map(key => key === id ? next : key) });
        }} /></Field>
        <PointFields label={`位置 ${index + 1}`} value={point} onChange={next => update({ character_positions: { ...value.character_positions, [id]: next } })} />
      </div><Button onClick={() => update({ character_positions: Object.fromEntries(positions.filter(([key]) => key !== id)), axis: value.axis.includes(id) ? [] : value.axis })}>移除位置 {index + 1}</Button></fieldset>)}
      <Button disabled={positions.length >= 30} onClick={() => {
        let index = 1; while (Object.hasOwn(value.character_positions, `position-${index}`)) index++;
        update({ character_positions: { ...value.character_positions, [`position-${index}`]: { x: 0, y: 0 } } });
      }}>添加人物位置（初始 x=0,y=0）</Button>
      <div className="creative-form-grid">{[0, 1].map(index => <Field key={index} label={`有序轴线端点 ${index + 1}`}><select value={value.axis[index] ?? ''} onChange={e => {
        const axis = [...value.axis]; axis[index] = e.target.value; update({ axis: [axis[0] ?? '', axis[1] ?? ''] });
      }}><option value="">未指定</option>{positions.map(([id]) => <option key={id} value={id}>{id || '空标识'}</option>)}</select></Field>)}</div>
      <Button onClick={() => update({ axis: [] })}>清除轴线</Button>
      {value.camera_position ? <fieldset><legend>明确机位</legend><div className="creative-form-grid"><PointFields label="机位" value={value.camera_position} onChange={camera_position => update({ camera_position })} /></div><Button onClick={() => update({ camera_position: null })}>清除机位</Button></fieldset>
        : <Button onClick={() => update({ camera_position: { x: 0, y: 0 } })}>添加机位（初始 x=0,y=0）</Button>}
      {value.subject_movement ? <fieldset><legend>主体移动轨迹</legend><div className="creative-form-grid">{(['start', 'end'] as const).map(key => <PointFields key={key} label={key === 'start' ? '移动起点' : '移动终点'} value={value.subject_movement![key]} onChange={point => update({ subject_movement: { ...value.subject_movement!, [key]: point } })} />)}</div><Button onClick={() => update({ subject_movement: null })}>清除移动轨迹</Button></fieldset>
        : <Button onClick={() => update({ subject_movement: { start: { x: 0, y: 0 }, end: { x: 0, y: 0 } } })}>添加移动轨迹（起止初始为 0,0）</Button>}
      <fieldset><legend>有意的导演选择</legend><label><input type="checkbox" checked={value.intentional_axis_crossing} onChange={e => update({ intentional_axis_crossing: e.target.checked })} />有意越轴</label>
        {(['LONG_TAKE', 'JUMP_CUT'] as const).map(intent => <label key={intent}><input type="checkbox" checked={value.intentions.includes(intent)} onChange={e => update({ intentions: e.target.checked ? [...value.intentions.filter(v => v !== intent), intent] : value.intentions.filter(v => v !== intent) })} />{intent === 'LONG_TAKE' ? '有意长镜头' : '有意跳切'}</label>)}
        <Field label="有意选择理由"><textarea maxLength={2000} value={value.override_reason} onChange={e => update({ override_reason: e.target.value })} /></Field>
      </fieldset>
      {!validCameraGrammar(value) && <StatusMessage tone="error">几何字段无效，请补全两个不同的轴线端点、有效坐标及有意选择理由，再保存。当前输入保留。</StatusMessage>}
      <Button onClick={() => onChange(undefined)}>移除手填几何</Button>
    </>}
  </details>;
}
