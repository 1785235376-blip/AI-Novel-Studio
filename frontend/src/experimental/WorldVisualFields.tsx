import { useId } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { Field } from './shared';

type VisualField = { key: string; label: string; maxLength: number; required?: boolean };
const fields = {
  CHARACTER_VISUAL: [
    { key: 'character_id', label: '视觉人物 ID', maxLength: 160, required: true },
    { key: 'appearance', label: '外貌', maxLength: 4000 },
    { key: 'clothing', label: '服装', maxLength: 4000 },
    { key: 'distinguishing', label: '辨识特征', maxLength: 2000 },
  ],
  SCENE_VISUAL: [
    { key: 'location_id', label: '视觉地点 ID', maxLength: 160, required: true },
    { key: 'architecture', label: '建筑形态', maxLength: 4000 },
    { key: 'material', label: '材质', maxLength: 4000 },
    { key: 'lighting', label: '光照', maxLength: 2000 },
    { key: 'weather', label: '天气', maxLength: 2000 },
    { key: 'mood', label: '氛围', maxLength: 2000 },
    { key: 'time_of_day', label: '时段', maxLength: 1000 },
  ],
} satisfies Record<string, VisualField[]>;
export type VisualKind = keyof typeof fields;
export type VisualData = { [key: string]: string | string[]; reference_asset_ids: string[] };
export function isVisualKind(kind: string): kind is VisualKind { return kind === 'CHARACTER_VISUAL' || kind === 'SCENE_VISUAL'; }
export function emptyVisualData(kind: VisualKind): VisualData {
  return { ...Object.fromEntries(fields[kind].map(field => [field.key, ''])), reference_asset_ids: [] };
}
// Pydantic max_length counts Unicode code points, not JavaScript UTF-16 units.
export function visualTextLength(value: string) { return Array.from(value).length; }
export function validVisualData(kind: VisualKind, data: VisualData): boolean {
  return fields[kind].every((field: VisualField) => {
    const value = data[field.key];
    return typeof value === 'string' && visualTextLength(value) <= field.maxLength && (!field.required || value.length > 0);
  }) && data.reference_asset_ids.length <= 50 && data.reference_asset_ids.every(id => typeof id === 'string');
}
export function WorldVisualFields({ kind, data, onChange, disabled }: {
  kind: VisualKind; data: VisualData; onChange: (value: VisualData) => void; disabled: boolean;
}) {
  const references = data.reference_asset_ids;
  return <section className="experimental-section" aria-label={kind === 'CHARACTER_VISUAL' ? '人物视觉设定' : '场景视觉设定'}>
    <StatusMessage>填写已有记录的真实 ID，保留原始大小写与空格。视觉设定可不关联章节；留空的视觉维度在 Bible 中表示 UNKNOWN，不会自动推断。</StatusMessage>
    {fields[kind].map((field: VisualField) => <VisualTextField key={field.key} field={field} disabled={disabled} value={data[field.key] as string} onChange={value => onChange({ ...data, [field.key]: value })} />)}
    {kind === 'CHARACTER_VISUAL' && <p>辨识特征保存在世界记录，可通过编辑和历史查看；当前 Bible 不单独展示此维度。</p>}
    <section className="experimental-section" aria-label="视觉参考资产">
      <p>参考资产 ID 仅为声明，不证明资产文件存在。逐条原样保存，最多 50 条；删除不需要的行。</p>
      {references.map((id, index) => <div className="experimental-section" key={index}>
        <Field label={`参考资产 ID ${index + 1}`}><input disabled={disabled} value={id} onChange={event => onChange({ ...data, reference_asset_ids: references.map((value, at) => at === index ? event.target.value : value) })} /></Field>
        <div className="experimental-actions"><Button type="button" disabled={disabled} onClick={() => onChange({ ...data, reference_asset_ids: references.filter((_, at) => at !== index) })}>移除参考资产 ID {index + 1}</Button></div>
      </div>)}
      <div className="experimental-actions"><Button type="button" disabled={disabled || references.length >= 50} onClick={() => onChange({ ...data, reference_asset_ids: [...references, ''] })}>添加参考资产 ID</Button></div>
    </section>
    <StatusMessage tone="warning">已批准的视觉记录不可编辑。新建视觉记录不会自动替换 Canon；Bible 优先使用首条已批准记录，否则使用首条匹配记录，并非最新记录。</StatusMessage>
  </section>;
}

function VisualTextField({ field, value, disabled, onChange }: {
  field: VisualField; value: string; disabled: boolean; onChange: (value: string) => void;
}) {
  const hint = useId(), length = visualTextLength(value);
  const common = { disabled, value, 'aria-describedby': hint, 'aria-invalid': length > field.maxLength || undefined };
  return <div className="experimental-section">
    <Field label={field.label}>{field.required
      ? <input {...common} required onChange={event => onChange(event.target.value)} />
      : <textarea {...common} onChange={event => onChange(event.target.value)} />
    }</Field>
    <p id={hint}>{length} / {field.maxLength} 字符{length > field.maxLength ? '，超出上限，请缩短后保存。' : ''}</p>
  </div>;
}
