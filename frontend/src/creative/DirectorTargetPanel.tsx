import { Button, Badge } from '../ui/primitives';
import { useId } from 'react';
import { creativeTextLength, validDirectorGenre, type VisualTarget } from './types';
import { CreativeField } from './CreativeCanvas';

const emptyTarget = (): VisualTarget => ({ style: '', atmosphere: '', reference_works: [], color: '', rhythm: '' });
/** View-only goal editor. Original document versioning and explicit save own persistence. */
export function DirectorTargetPanel({ value, onChange, prefix = '' }: { prefix?: string; value?: VisualTarget | null; onChange: (value?: VisualTarget) => void }) {
  const target = value || emptyTarget();
  const genreHint = useId(), genreLength = creativeTextLength(target.genre);
  const update = (patch: Partial<VisualTarget>) => onChange({ ...target, ...patch });
  return <section className="creative-visual-target" aria-label={`${prefix}项目视觉目标`}>
    <header className="creative-actions"><h3>项目视觉目标</h3><Badge>{value ? '作者设定' : '尚未设定'}</Badge></header>
    <p>导演目标随当前文档版本保存。明确建立分镜草稿时才传递到新文档；修改目标不会自动改写场景或执行媒体。</p>
    <div className="creative-form-grid"><div><CreativeField label={`${prefix}文档类型 / 题材`}><input value={target.genre ?? ''} aria-invalid={!validDirectorGenre(target)} aria-describedby={genreHint} onChange={event => update({ genre: event.target.value })} /></CreativeField><p id={genreHint}>{genreLength} / 2000 字符{!validDirectorGenre(target) ? '，超出上限，请缩短后保存。' : '；仅属于此文档，留空表示未设定。'}</p></div><CreativeField label={`${prefix}视觉风格`}><input maxLength={2000} value={target.style} onChange={event => update({ style: event.target.value })} /></CreativeField>
      <CreativeField label={`${prefix}整体氛围`}><input maxLength={2000} value={target.atmosphere} onChange={event => update({ atmosphere: event.target.value })} /></CreativeField></div>
    <details><summary>展开色彩、节奏与参考作品</summary><div className="creative-form-grid">
      <CreativeField label={`${prefix}色彩目标`}><input maxLength={2000} value={target.color} onChange={event => update({ color: event.target.value })} /></CreativeField>
      <CreativeField label={`${prefix}节奏目标`}><input maxLength={2000} value={target.rhythm} onChange={event => update({ rhythm: event.target.value })} /></CreativeField>
      </div><Button disabled={target.reference_works.length >= 20} onClick={() => update({ reference_works: [...target.reference_works, ''] })}>添加参考作品</Button>
      <ul>{target.reference_works.map((work, index) => <li key={index}><CreativeField label={`${prefix}参考作品 ${index + 1}`}><input maxLength={1000} required value={work} onChange={event => update({ reference_works: target.reference_works.map((item, i) => i === index ? event.target.value : item) })} /></CreativeField><Button onClick={() => update({ reference_works: target.reference_works.filter((_, i) => i !== index) })}>移除参考作品 {index + 1}</Button></li>)}</ul><Button disabled={!value} onClick={() => onChange(undefined)}>移除此文档视觉目标</Button></details>
    {value && <aside aria-label="视觉目标预览"><strong>{target.style || '未指定风格'}</strong><p>{[target.genre, target.atmosphere, target.color, target.rhythm].filter(Boolean).join(' · ') || '继续设定氛围、色彩与节奏。'}</p>{target.reference_works.filter(Boolean).length > 0 && <p>参考：{target.reference_works.filter(Boolean).join('、')}</p>}</aside>}
  </section>;
}
