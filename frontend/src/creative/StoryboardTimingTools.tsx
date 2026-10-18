import { useLayoutEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import type { CreativeInput } from './types';
import { previewDirectorTiming, previewStoryboardTiming, type StoryboardTimingMode } from './storyboardTiming';
type Props = { draft: CreativeInput; sceneId?: string; disabled: boolean; onChange: (draft: CreativeInput) => void };
export function StoryboardTimingTools(props: Props) {
  const director = props.draft.mode === 'DIRECTOR', subject = director ? '导演调度' : '分镜', unit = director ? '调度' : '镜头';
  const itemCount = director ? props.draft.director_notes.length : props.draft.shots.length;
  const [scope, setScope] = useState<'scene' | 'all'>('scene'), [mode, setMode] = useState<StoryboardTimingMode>('uniform'), [amount, setAmount] = useState('5');
  const [error, setError] = useState(''), [, renderRevision] = useState(0);
  const [preview, setPreview] = useState<{ token: object; revision: number; value: ReturnType<typeof previewStoryboardTiming> }>();
  const [undo, setUndo] = useState<{ before: CreativeInput; after: CreativeInput; sceneId?: string }>();
  const live = useRef(props); live.current = props;
  const alive = useRef(true), composing = useRef(false), revision = useRef(0), input = useRef<HTMLInputElement>(null);
  const values = [props.draft, props.sceneId, props.disabled];
  const owner = useRef({ values, token: {} });
  if (values.some((value, index) => value !== owner.current.values[index])) owner.current = { values, token: {} };
  const token = owner.current.token, capturedRevision = revision.current;
  const consumed = useRef<object>();
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useLayoutEffect(() => { if (undo && (props.disabled || undo.after !== props.draft || undo.sceneId !== props.sceneId)) setUndo(undefined); }, [props.draft, props.disabled, props.sceneId, undo]);
  const current = () => alive.current && !live.current.disabled && owner.current.token === token && revision.current === capturedRevision;
  const invalidate = () => { revision.current++; renderRevision(revision.current); setPreview(undefined); setError(''); };
  const visible = preview && preview.token === token && preview.revision === revision.current && !props.disabled ? preview : undefined;
  return <section aria-label={`${subject}批量时长`}><h3>{subject}节奏与批量时长</h3>
    <p>只调整作者草稿秒数，不剪切已有视频、不改时间线；保存后需重新核对生成请求和下游版本。{director && '调度秒数相加仅为规划，不代表成片时长；嵌入场景的备注不参与分配。'}</p>
    <label>时长调整范围<select value={scope} disabled={props.disabled} onChange={event => { if (current()) { invalidate(); setScope(event.target.value as 'scene' | 'all'); } }}><option value="scene">当前场景{unit}</option><option value="all">全部{unit}</option></select></label>
    <label>时长分配方式<select value={mode} disabled={props.disabled} onChange={event => { if (current()) { invalidate(); setMode(event.target.value as StoryboardTimingMode); } }}><option value="uniform">每个{unit}使用相同秒数</option><option value="total">分配指定总秒数</option></select></label>
    <label>批量时长秒数<input ref={input} value={amount} inputMode="numeric" maxLength={6} disabled={props.disabled}
      onChange={event => { if (current()) { invalidate(); setAmount(event.target.value); } }}
      onCompositionStart={() => { composing.current = true; invalidate(); }} onCompositionEnd={event => { composing.current = false; invalidate(); setAmount(event.currentTarget.value); }} /></label>
    {mode === 'total' && <p>每个{unit}先保留 1 秒，其余按原时长权重分配；余秒按最大余数及原{unit}顺序分配，达到 600 秒的{unit}停止分配，其余继续分配，合计精确等于目标。</p>}
    <Button disabled={props.disabled || !itemCount} onClick={() => {
      if (!current() || composing.current || input.current?.value !== amount) return;
      invalidate(); try { if (scope === 'scene' && !props.sceneId) throw new Error('请先选择场景。');
        const value = (director ? previewDirectorTiming : previewStoryboardTiming)(props.draft, scope === 'scene' ? props.sceneId : undefined, mode, amount);
        if (value.changes.every(row => row.before === row.after)) { setError('时长未变化，草稿保持不变。'); return; }
        setPreview({ token, revision: revision.current, value });
      } catch (reason) { setError(reason instanceof Error ? reason.message : '无法预览时长。'); }
    }}>预览{subject}时长调整</Button>
    {error && <StatusMessage tone="warning">{error}</StatusMessage>}
    {visible && <section aria-label={`${subject}时长调整预览`}><p>{visible.value.changes.length} 个{unit}：{visible.value.before} → {visible.value.after} 秒</p>
      <ol>{visible.value.changes.map(row => <li key={row.id}>{director ? '调度' : 'SHOT'} {row.number}：{row.before} → {row.after} 秒</li>)}</ol>
      <Button disabled={props.disabled} onClick={() => {
        if (!current() || composing.current || input.current?.value !== amount || consumed.current === visible) return;
        consumed.current = visible; invalidate(); setUndo({ before: props.draft, after: visible.value.draft, sceneId: props.sceneId }); props.onChange(visible.value.draft);
      }}>确认应用{subject}时长（尚未保存）</Button></section>}
    <Button disabled={props.disabled || !undo || undo.after !== props.draft || undo.sceneId !== props.sceneId} onClick={() => {
      if (!current() || !undo || undo.after !== live.current.draft || undo.sceneId !== live.current.sceneId) return;
      invalidate(); setUndo(undefined); props.onChange(undo.before);
    }}>撤销本次{subject}时长调整</Button>
  </section>;
}
